"""
イベントドリブン戦略のバックテスト（簡易版・月次集計）

戦略: 小型株（時価総額Q1）× 高成長率（カスタム成長率Q4）
エントリー: 決算発表があった月の月初
エグジット: 翌月初
保有期間: 約1ヶ月
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
print("イベントドリブン戦略のバックテスト（簡易版・月次集計）")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/4] データ読み込み中...")

# 既存の成長率データを読み込む
df_growth = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_by_marketcap/growth_rate_by_marketcap.csv',
    parse_dates=['disclosed_date']
)

print(f"成長率データ: {len(df_growth):,} レコード")

# 必要な列のみ抽出
df_growth = df_growth[['code', 'disclosed_date', 'custom_growth_rate', 'market_cap']].copy()
df_growth = df_growth.dropna()

# 年月列を追加（月次集計用）
df_growth['year_month'] = df_growth['disclosed_date'].dt.to_period('M')

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
# 2. 月次リストの作成
# ================================================================================

print("\n[2/4] 月次リストを作成中...")

# 2017年1月～2025年12月
months = pd.period_range(start='2017-01', end='2025-12', freq='M')

print(f"月数: {len(months)}")
print(f"期間: {months[0]} ~ {months[-1]}")

# ================================================================================
# 3. バックテストの実行（月次エントリー）
# ================================================================================

print("\n[3/4] バックテストを実行中...")

portfolio_returns = []
benchmark_all_returns = []
benchmark_small_returns = []
portfolio_sizes = []
month_records = []

for i in range(len(months) - 1):  # 最後の月はエグジットできないのでスキップ
    current_month = months[i]
    next_month = months[i + 1]

    # その月に決算発表があった銘柄を取得
    disclosed_this_month = df_growth[df_growth['year_month'] == current_month].copy()

    if len(disclosed_this_month) == 0:
        print(f"  {current_month}: 決算発表なし、スキップ")
        continue

    print(f"\n  {current_month}: 決算発表 {len(disclosed_this_month)} 件")

    # 各銘柄の最新データのみを使用（その月時点で）
    latest_data = disclosed_this_month.sort_values('disclosed_date').groupby('code').last().reset_index()

    # サンプル数が少ない月はスキップ（四分位計算に最低20件必要）
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
        print(f"    四分位計算失敗、スキップ")
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
    current_month_start = pd.Timestamp(f"{current_month}-01")
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

    print(f"    エントリー: {entry_date.date()}, エグジット: {exit_date.date()}")

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

    portfolio_returns.append(portfolio_return)
    benchmark_all_returns.append(benchmark_all_return)
    benchmark_small_returns.append(benchmark_small_return)
    portfolio_sizes.append(portfolio_size)

    month_records.append({
        'month': str(current_month),
        'entry_date': entry_date,
        'exit_date': exit_date,
        'portfolio_return': portfolio_return,
        'benchmark_all_return': benchmark_all_return,
        'benchmark_small_return': benchmark_small_return,
        'portfolio_size': portfolio_size
    })

    print(f"    戦略={portfolio_return*100:+6.2f}%, 全銘柄={benchmark_all_return*100:+6.2f}%, 小型株={benchmark_small_return*100:+6.2f}%")

# ================================================================================
# 4. パフォーマンス指標の計算
# ================================================================================

print("\n[4/4] パフォーマンス指標を計算中...")

# DataFrameに変換
df_backtest = pd.DataFrame(month_records)

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

# 最大ドローダウン
def calculate_max_drawdown(cumulative_returns):
    running_max = cumulative_returns.cummax()
    drawdown = (cumulative_returns - running_max) / running_max
    return drawdown.min()

mdd_strategy = calculate_max_drawdown(df_backtest['cumulative_return_strategy'])
mdd_all = calculate_max_drawdown(df_backtest['cumulative_return_all'])
mdd_small = calculate_max_drawdown(df_backtest['cumulative_return_small'])

# 勝率
win_rate_strategy = (df_backtest['portfolio_return'] > 0).sum() / len(df_backtest)
win_rate_all = (df_backtest['benchmark_all_return'] > 0).sum() / len(df_backtest)
win_rate_small = (df_backtest['benchmark_small_return'] > 0).sum() / len(df_backtest)

# 相関
correlation_vs_all = df_backtest['portfolio_return'].corr(df_backtest['benchmark_all_return'])
correlation_vs_small = df_backtest['portfolio_return'].corr(df_backtest['benchmark_small_return'])

# ================================================================================
# 5. 結果の表示
# ================================================================================

print("\n" + "="*80)
print("パフォーマンスサマリ")
print("="*80)

print(f"\nバックテスト期間: {df_backtest['month'].iloc[0]} ~ {df_backtest['month'].iloc[-1]}")
print(f"月数: {len(df_backtest)}")
print(f"運用期間: {years:.1f}年")

print("\n【累積リターン】")
print(f"  戦略（小型株×高成長）: {final_return_strategy*100:+7.2f}%")
print(f"  ベンチマーク（全銘柄）: {final_return_all*100:+7.2f}%")
print(f"  ベンチマーク（小型株）: {final_return_small*100:+7.2f}%")

print("\n【年率リターン（CAGR）】")
print(f"  戦略（小型株×高成長）: {cagr_strategy*100:+7.2f}%")
print(f"  ベンチマーク（全銘柄）: {cagr_all*100:+7.2f}%")
print(f"  ベンチマーク（小型株）: {cagr_small*100:+7.2f}%")

print("\n【ボラティリティ（年率）】")
print(f"  戦略（小型株×高成長）: {volatility_strategy*100:7.2f}%")
print(f"  ベンチマーク（全銘柄）: {volatility_all*100:7.2f}%")
print(f"  ベンチマーク（小型株）: {volatility_small*100:7.2f}%")

print("\n【シャープレシオ】")
print(f"  戦略（小型株×高成長）: {sharpe_strategy:7.3f}")
print(f"  ベンチマーク（全銘柄）: {sharpe_all:7.3f}")
print(f"  ベンチマーク（小型株）: {sharpe_small:7.3f}")

print("\n【最大ドローダウン】")
print(f"  戦略（小型株×高成長）: {mdd_strategy*100:+7.2f}%")
print(f"  ベンチマーク（全銘柄）: {mdd_all*100:+7.2f}%")
print(f"  ベンチマーク（小型株）: {mdd_small*100:+7.2f}%")

print("\n【勝率】")
print(f"  戦略（小型株×高成長）: {win_rate_strategy*100:7.2f}%")
print(f"  ベンチマーク（全銘柄）: {win_rate_all*100:7.2f}%")
print(f"  ベンチマーク（小型株）: {win_rate_small*100:7.2f}%")

print("\n【相関係数】")
print(f"  vs 全銘柄: {correlation_vs_all:+7.3f}")
print(f"  vs 小型株: {correlation_vs_small:+7.3f}")

print("\n【アウトパフォーマンス】")
print(f"  vs 全銘柄: {(cagr_strategy - cagr_all)*100:+7.2f}% (年率)")
print(f"  vs 小型株: {(cagr_strategy - cagr_small)*100:+7.2f}% (年率)")

print("\n【平均銘柄数】")
print(f"  {df_backtest['portfolio_size'].mean():.1f} 銘柄/月")

# ================================================================================
# 6. 結果の保存
# ================================================================================

print("\n[保存中...]")

output_dir = PROJECT_ROOT / 'analyses' / '20260225_1800_event_driven_strategy' / 'results'
output_dir.mkdir(exist_ok=True, parents=True)

# 詳細データ
df_backtest.to_csv(output_dir / 'backtest_results_simple.csv', index=False, encoding='utf-8-sig')

# サマリ
summary = {
    'strategy_name': 'Event Driven (Monthly Entry)',
    'backtest_period': {
        'start': df_backtest['month'].iloc[0],
        'end': df_backtest['month'].iloc[-1],
        'months': int(months_count),
        'years': float(years)
    },
    'performance': {
        'strategy': {
            'cumulative_return': float(final_return_strategy),
            'cagr': float(cagr_strategy),
            'volatility': float(volatility_strategy),
            'sharpe_ratio': float(sharpe_strategy),
            'max_drawdown': float(mdd_strategy),
            'win_rate': float(win_rate_strategy)
        },
        'benchmark_all': {
            'cumulative_return': float(final_return_all),
            'cagr': float(cagr_all),
            'volatility': float(volatility_all),
            'sharpe_ratio': float(sharpe_all),
            'max_drawdown': float(mdd_all),
            'win_rate': float(win_rate_all)
        },
        'benchmark_small': {
            'cumulative_return': float(final_return_small),
            'cagr': float(cagr_small),
            'volatility': float(volatility_small),
            'sharpe_ratio': float(sharpe_small),
            'max_drawdown': float(mdd_small),
            'win_rate': float(win_rate_small)
        }
    },
    'correlation': {
        'vs_all': float(correlation_vs_all),
        'vs_small': float(correlation_vs_small)
    },
    'outperformance': {
        'vs_all_cagr': float(cagr_strategy - cagr_all),
        'vs_small_cagr': float(cagr_strategy - cagr_small)
    },
    'portfolio_stats': {
        'avg_size_per_month': float(df_backtest['portfolio_size'].mean()),
        'min_size': int(df_backtest['portfolio_size'].min()),
        'max_size': int(df_backtest['portfolio_size'].max())
    }
}

with open(output_dir / 'summary_simple.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("バックテスト完了")
print("="*80)

print("\n【主要な発見】")
print(f"\n1. 年率リターン: {cagr_strategy*100:+.2f}%")
print(f"   - ベース戦略（+28.52%）との比較:")
print(f"   - 差分: {(cagr_strategy - 0.2852)*100:+.2f}%")

print(f"\n2. リスク調整後リターン:")
print(f"   - シャープレシオ: {sharpe_strategy:.3f}")
print(f"   - 最大ドローダウン: {mdd_strategy*100:.2f}%")

print(f"\n3. 相関係数:")
print(f"   - vs 全銘柄: {correlation_vs_all:+.3f}")
print(f"   - vs 小型株: {correlation_vs_small:+.3f}")

print(f"\n4. 平均銘柄数: {df_backtest['portfolio_size'].mean():.1f} 銘柄/月")

if cagr_strategy > cagr_all and cagr_strategy > cagr_small:
    print("\n✅ 戦略は両方のベンチマークを上回りました！")
else:
    print("\n⚠️ 戦略はベンチマークを下回りました")

if cagr_strategy > 0.15:
    print(f"✅ 年率リターン {cagr_strategy*100:.2f}% は目標（+15%）を達成しました")
else:
    print(f"⚠️ 年率リターン {cagr_strategy*100:.2f}% は目標（+15%）を下回りました")
