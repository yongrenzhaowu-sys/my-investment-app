"""
月次リバランス戦略 + トレンドフィルター（200日MA）

戦略: 小型株（時価総額Q1）× 高成長率（カスタム成長率Q4）
フィルター: ベンチマーク（全銘柄平均）が200日MA以上の時のみエントリー
エントリー: 月初
エグジット: 翌月初
保有期間: 約1ヶ月

目的: 最大ドローダウンを削減し、シャープレシオを改善
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
import json
warnings.filterwarnings('ignore')

# プロジェクトルート
PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("月次リバランス戦略 + トレンドフィルター（200日MA）")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/5] データ読み込み中...")

# 既存の成長率データを読み込む
df_growth = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_by_marketcap/growth_rate_by_marketcap.csv',
    parse_dates=['disclosed_date']
)

print(f"成長率データ: {len(df_growth):,} レコード")

# 必要な列のみ抽出
df_growth = df_growth[['code', 'disclosed_date', 'custom_growth_rate', 'market_cap']].copy()
df_growth = df_growth.dropna()

print(f"欠損値除外後: {len(df_growth):,} レコード")
print(f"期間: {df_growth['disclosed_date'].min().date()} ~ {df_growth['disclosed_date'].max().date()}")

# 価格データを読み込み
print("\n価格データを読み込み中...")
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2017-01-01'].copy()

print(f"価格データ: {len(df_price):,} 行")

# 価格データをピボット化（高速化）
print("価格データをピボット化中...")
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')
print(f"ピボットテーブル: {df_price_pivot.shape[0]} 日 × {df_price_pivot.shape[1]} 銘柄")

# ================================================================================
# 2. ベンチマークと200日移動平均の計算
# ================================================================================

print("\n[2/5] ベンチマーク（全銘柄平均）と200日移動平均を計算中...")

# 日次のベンチマーク（全銘柄の平均価格）を計算
daily_benchmark = df_price_pivot.mean(axis=1)

# 200日移動平均を計算
ma_200 = daily_benchmark.rolling(window=200, min_periods=200).mean()

print(f"ベンチマーク計算完了: {len(daily_benchmark)} 日")
print(f"200日MA計算完了: {len(ma_200.dropna())} 日（有効）")

# ================================================================================
# 3. 月次リストの作成
# ================================================================================

print("\n[3/5] 月次リストを作成中...")

# 2017年1月～2025年12月
months = pd.period_range(start='2017-01', end='2025-12', freq='M')

print(f"月数: {len(months)}")
print(f"期間: {months[0]} ~ {months[-1]}")

# ================================================================================
# 4. バックテストの実行（トレンドフィルター付き）
# ================================================================================

print("\n[4/5] バックテストを実行中...")
print("\n【重要】200日MA以上の時のみエントリー、それ以外は現金保有")

portfolio_returns = []
benchmark_all_returns = []
benchmark_small_returns = []
portfolio_sizes = []
month_records = []
filter_status_list = []  # フィルター状態の記録

for i in range(len(months) - 1):  # 最後の月はエグジットできないのでスキップ
    current_month = months[i]
    next_month = months[i + 1]

    # エントリー日: その月の最初の営業日
    current_month_start = pd.Timestamp(f"{current_month}-01")

    # 利用可能なデータのみ（disclosed_date < 月初）
    available_data = df_growth[df_growth['disclosed_date'] < current_month_start].copy()

    if len(available_data) == 0:
        print(f"  {current_month}: 利用可能なデータなし、スキップ")
        continue

    # 各銘柄の最新データのみを使用
    latest_data = available_data.sort_values('disclosed_date').groupby('code').last().reset_index()

    print(f"\n  {current_month}: 利用可能データ {len(available_data):,}件 → 最新データ {len(latest_data)}銘柄")

    # サンプル数が少ない月はスキップ
    if len(latest_data) < 20:
        print(f"    サンプル数不足（{len(latest_data)}件）、スキップ")
        continue

    # 時価総額の四分位を計算
    try:
        latest_data['marketcap_quartile'] = pd.qcut(
            latest_data['market_cap'],
            q=4,
            labels=['Q1', 'Q2', 'Q3', 'Q4'],
            duplicates='drop'
        )
    except ValueError:
        print(f"    時価総額四分位計算失敗、スキップ")
        continue

    # カスタム成長率の四分位を計算
    try:
        latest_data['growth_quartile'] = pd.qcut(
            latest_data['custom_growth_rate'],
            q=4,
            labels=['Q1', 'Q2', 'Q3', 'Q4'],
            duplicates='drop'
        )
    except ValueError:
        print(f"    成長率四分位計算失敗、スキップ")
        continue

    # 戦略: 小型株（Q1）× 高成長率（Q4）
    strategy_portfolio = latest_data[
        (latest_data['marketcap_quartile'] == 'Q1') &
        (latest_data['growth_quartile'] == 'Q4')
    ].copy()

    # ベンチマーク1: 全銘柄
    benchmark_all = latest_data.copy()

    # ベンチマーク2: 小型株
    benchmark_small = latest_data[latest_data['marketcap_quartile'] == 'Q1'].copy()

    print(f"    選定: 戦略={len(strategy_portfolio)}銘柄, 小型株={len(benchmark_small)}銘柄")

    if len(strategy_portfolio) == 0:
        print(f"    戦略銘柄なし、スキップ")
        continue

    # エントリー日: その月の最初の営業日
    entry_dates = df_price_pivot.index[df_price_pivot.index >= current_month_start]
    if len(entry_dates) == 0:
        print(f"    エントリー日なし、スキップ")
        continue
    entry_date = entry_dates[0]

    # エグジット日: 翌月の最初の営業日
    next_month_start = pd.Timestamp(f"{next_month}-01")
    exit_dates = df_price_pivot.index[df_price_pivot.index >= next_month_start]
    if len(exit_dates) == 0:
        print(f"    エグジット日なし、スキップ")
        continue
    exit_date = exit_dates[0]

    # ===== トレンドフィルターの判定 =====
    # エントリー日のベンチマークと200日MAを取得
    if entry_date not in ma_200.index or pd.isna(ma_200.loc[entry_date]):
        print(f"    200日MAデータなし、スキップ")
        continue

    current_benchmark = daily_benchmark.loc[entry_date]
    current_ma200 = ma_200.loc[entry_date]
    trend_filter_pass = current_benchmark >= current_ma200

    if trend_filter_pass:
        print(f"    [OK] トレンドフィルターOK: ベンチマーク {current_benchmark:.2f} >= 200MA {current_ma200:.2f}")
        print(f"    エントリー: {entry_date.date()}, エグジット: {exit_date.date()}")
    else:
        print(f"    [NG] トレンドフィルターNG: ベンチマーク {current_benchmark:.2f} < 200MA {current_ma200:.2f}")
        print(f"    -> 現金保有（リターン0%）")

    filter_status_list.append({
        'month': str(current_month),
        'filter_pass': trend_filter_pass,
        'benchmark': current_benchmark,
        'ma_200': current_ma200
    })

    # フィルターOKの時のみエントリー
    if trend_filter_pass:
        # 戦略ポートフォリオのリターンを計算
        strategy_returns = []
        for code in strategy_portfolio['code']:
            if code not in df_price_pivot.columns:
                continue
            entry_price = df_price_pivot.loc[entry_date, code]
            exit_price = df_price_pivot.loc[exit_date, code]
            if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
                ret = (exit_price - entry_price) / entry_price
                strategy_returns.append(ret)

        # ベンチマーク1（全銘柄）のリターンを計算
        benchmark_all_rets = []
        for code in benchmark_all['code']:
            if code not in df_price_pivot.columns:
                continue
            entry_price = df_price_pivot.loc[entry_date, code]
            exit_price = df_price_pivot.loc[exit_date, code]
            if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
                ret = (exit_price - entry_price) / entry_price
                benchmark_all_rets.append(ret)

        # ベンチマーク2（小型株）のリターンを計算
        benchmark_small_rets = []
        for code in benchmark_small['code']:
            if code not in df_price_pivot.columns:
                continue
            entry_price = df_price_pivot.loc[entry_date, code]
            exit_price = df_price_pivot.loc[exit_date, code]
            if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
                ret = (exit_price - entry_price) / entry_price
                benchmark_small_rets.append(ret)

        # 等ウェイトポートフォリオの平均リターン
        portfolio_return = np.mean(strategy_returns) if len(strategy_returns) > 0 else 0.0
        benchmark_all_return = np.mean(benchmark_all_rets) if len(benchmark_all_rets) > 0 else 0.0
        benchmark_small_return = np.mean(benchmark_small_rets) if len(benchmark_small_rets) > 0 else 0.0
        portfolio_size = len(strategy_returns)
    else:
        # フィルターNGの時は現金保有（リターン0%）
        portfolio_return = 0.0
        benchmark_all_return = 0.0
        benchmark_small_return = 0.0
        portfolio_size = 0

    portfolio_returns.append(portfolio_return)
    benchmark_all_returns.append(benchmark_all_return)
    benchmark_small_returns.append(benchmark_small_return)
    portfolio_sizes.append(portfolio_size)

    month_records.append({
        'month': str(current_month),
        'entry_date': entry_date if trend_filter_pass else None,
        'exit_date': exit_date if trend_filter_pass else None,
        'portfolio_return': portfolio_return,
        'benchmark_all_return': benchmark_all_return,
        'benchmark_small_return': benchmark_small_return,
        'portfolio_size': portfolio_size,
        'filter_pass': trend_filter_pass
    })

    print(f"    戦略={portfolio_return*100:+6.2f}%, 全銘柄={benchmark_all_return*100:+6.2f}%, 小型株={benchmark_small_return*100:+6.2f}%")

# ================================================================================
# 5. パフォーマンス指標の計算
# ================================================================================

print("\n[5/5] パフォーマンス指標を計算中...")

# DataFrameに変換
df_backtest = pd.DataFrame(month_records)

# フィルター通過率
filter_pass_rate = df_backtest['filter_pass'].mean()
print(f"\nフィルター通過率: {filter_pass_rate*100:.1f}%（{df_backtest['filter_pass'].sum()}/{len(df_backtest)}ヶ月）")

# 累積リターンの計算
df_backtest['cumulative_return_strategy'] = (1 + df_backtest['portfolio_return']).cumprod()
df_backtest['cumulative_return_all'] = (1 + df_backtest['benchmark_all_return']).cumprod()
df_backtest['cumulative_return_small'] = (1 + df_backtest['benchmark_small_return']).cumprod()

# 最終的な累積リターン
final_return_strategy = df_backtest['cumulative_return_strategy'].iloc[-1] - 1
final_return_all = df_backtest['cumulative_return_all'].iloc[-1] - 1
final_return_small = df_backtest['cumulative_return_small'].iloc[-1] - 1

# 年率リターン（CAGR）
months_count = len(df_backtest)
years = months_count / 12
cagr_strategy = (df_backtest['cumulative_return_strategy'].iloc[-1] ** (1 / years)) - 1
cagr_all = (df_backtest['cumulative_return_all'].iloc[-1] ** (1 / years)) - 1
cagr_small = (df_backtest['cumulative_return_small'].iloc[-1] ** (1 / years)) - 1

# ボラティリティ（年率）
volatility_strategy = df_backtest['portfolio_return'].std() * np.sqrt(12)
volatility_all = df_backtest['benchmark_all_return'].std() * np.sqrt(12)
volatility_small = df_backtest['benchmark_small_return'].std() * np.sqrt(12)

# シャープレシオ
sharpe_strategy = cagr_strategy / volatility_strategy if volatility_strategy > 0 else 0
sharpe_all = cagr_all / volatility_all if volatility_all > 0 else 0
sharpe_small = cagr_small / volatility_small if volatility_small > 0 else 0

# 最大ドローダウンの計算
def calculate_max_drawdown(cumulative_returns):
    peak = cumulative_returns.expanding(min_periods=1).max()
    drawdown = (cumulative_returns - peak) / peak
    return drawdown.min()

mdd_strategy = calculate_max_drawdown(df_backtest['cumulative_return_strategy'])
mdd_all = calculate_max_drawdown(df_backtest['cumulative_return_all'])
mdd_small = calculate_max_drawdown(df_backtest['cumulative_return_small'])

# 勝率
win_rate_strategy = (df_backtest['portfolio_return'] > 0).mean()
win_rate_all = (df_backtest['benchmark_all_return'] > 0).mean()
win_rate_small = (df_backtest['benchmark_small_return'] > 0).mean()

# 相関係数
corr_with_all = df_backtest['portfolio_return'].corr(df_backtest['benchmark_all_return'])
corr_with_small = df_backtest['portfolio_return'].corr(df_backtest['benchmark_small_return'])

# アウトパフォーマンス
outperformance_vs_all = cagr_strategy - cagr_all
outperformance_vs_small = cagr_strategy - cagr_small

# 平均銘柄数（フィルター通過時のみ）
avg_portfolio_size = df_backtest[df_backtest['filter_pass'] == True]['portfolio_size'].mean()

# ================================================================================
# 結果の出力
# ================================================================================

print("\n" + "="*80)
print("パフォーマンスサマリ（トレンドフィルター付き）")
print("="*80)

print(f"\nバックテスト期間: {df_backtest['month'].iloc[0]} ~ {df_backtest['month'].iloc[-1]}")
print(f"月数: {months_count}")
print(f"年数: {years:.1f}年")
print(f"\nフィルター通過率: {filter_pass_rate*100:.1f}%（{df_backtest['filter_pass'].sum()}/{len(df_backtest)}ヶ月）")

print(f"\n【累積リターン】")
print(f"  戦略（フィルター付き）: {final_return_strategy*100:+.2f}%")
print(f"  ベンチマーク（全銘柄）: {final_return_all*100:+.2f}%")
print(f"  ベンチマーク（小型株）: {final_return_small*100:+.2f}%")

print(f"\n【年率リターン（CAGR）】")
print(f"  戦略（フィルター付き）: {cagr_strategy*100:+6.2f}%")
print(f"  ベンチマーク（全銘柄）: {cagr_all*100:+6.2f}%")
print(f"  ベンチマーク（小型株）: {cagr_small*100:+6.2f}%")

print(f"\n【ボラティリティ（年率）】")
print(f"  戦略（フィルター付き）: {volatility_strategy*100:6.2f}%")
print(f"  ベンチマーク（全銘柄）: {volatility_all*100:6.2f}%")
print(f"  ベンチマーク（小型株）: {volatility_small*100:6.2f}%")

print(f"\n【シャープレシオ】")
print(f"  戦略（フィルター付き）: {sharpe_strategy:6.3f}")
print(f"  ベンチマーク（全銘柄）: {sharpe_all:6.3f}")
print(f"  ベンチマーク（小型株）: {sharpe_small:6.3f}")

print(f"\n【最大ドローダウン】")
print(f"  戦略（フィルター付き）: {mdd_strategy*100:6.2f}%")
print(f"  ベンチマーク（全銘柄）: {mdd_all*100:6.2f}%")
print(f"  ベンチマーク（小型株）: {mdd_small*100:6.2f}%")

print(f"\n【勝率】")
print(f"  戦略（フィルター付き）: {win_rate_strategy*100:6.2f}%")
print(f"  ベンチマーク（全銘柄）: {win_rate_all*100:6.2f}%")
print(f"  ベンチマーク（小型株）: {win_rate_small*100:6.2f}%")

print(f"\n【アウトパフォーマンス】")
print(f"  vs 全銘柄: {outperformance_vs_all*100:+6.2f}% (年率)")
print(f"  vs 小型株: {outperformance_vs_small*100:+6.2f}% (年率)")

print(f"\n【平均銘柄数】")
print(f"  {avg_portfolio_size:.1f} 銘柄/月（エントリー時のみ）")

# 保存
output_dir = PROJECT_ROOT / 'analyses/20260225_1800_event_driven_strategy/results_trend_filter'
output_dir.mkdir(parents=True, exist_ok=True)

df_backtest.to_csv(output_dir / 'monthly_returns.csv', index=False)

summary = {
    'filter_pass_rate': float(filter_pass_rate),
    'strategy': {
        'cagr': float(cagr_strategy),
        'volatility': float(volatility_strategy),
        'sharpe_ratio': float(sharpe_strategy),
        'max_drawdown': float(mdd_strategy),
        'win_rate': float(win_rate_strategy)
    }
}

with open(output_dir / 'summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("バックテスト完了（トレンドフィルター付き）")
print("="*80)

print("\n【フィルターなし版との比較】")
print("  フィルターなし: 年率+21.21%, MDD -31.32%, シャープ 1.122")
print(f"  フィルター付き: 年率{cagr_strategy*100:+.2f}%, MDD {mdd_strategy*100:.2f}%, シャープ {sharpe_strategy:.3f}")
print(f"\n  MDD改善: {(mdd_strategy - (-0.3132))*100:+.2f}%")
print(f"  シャープ改善: {sharpe_strategy - 1.122:+.3f}")
