"""
大型株×低ボラティリティ戦略のバックテスト

戦略: 大型株（時価総額Q4）× 低ボラティリティ（過去6ヶ月標準偏差Q1）
リバランス: 年次（10月1日）
ウェイト: 等ウェイト
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
print("大型株×低ボラティリティ戦略のバックテスト")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/5] データ読み込み中...")

# 既存の時価総額データを読み込む
df_marketcap = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_by_marketcap/growth_rate_by_marketcap.csv',
    parse_dates=['disclosed_date']
)

print(f"時価総額データ: {len(df_marketcap):,} レコード")

# 必要な列のみ抽出
df_marketcap = df_marketcap[['code', 'disclosed_date', 'market_cap']].copy()
df_marketcap = df_marketcap.dropna()

print(f"欠損値除外後: {len(df_marketcap):,} レコード")

# 価格データを読み込み
print("\n価格データを読み込み中...")
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()

print(f"価格データ: {len(df_price):,} 行")

# 価格データをピボット化（高速化）
print("価格データをピボット化中...")
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')
print(f"ピボットテーブル: {df_price_pivot.shape[0]} 日 × {df_price_pivot.shape[1]} 銘柄")

# ================================================================================
# 2. リバランス日の設定
# ================================================================================

print("\n[2/5] リバランス日を設定中...")

# 年次リバランス日（10月1日）
rebalance_dates = pd.date_range(
    start='2016-10-01',
    end='2025-10-01',
    freq='YS-OCT'  # 10月開始の年次
)

print(f"リバランス回数: {len(rebalance_dates)}")
print(f"リバランス日: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}")

# ================================================================================
# 3. バックテストの実行
# ================================================================================

print("\n[3/5] バックテストを実行中...")

portfolio_returns = []
benchmark_all_returns = []
benchmark_large_returns = []
portfolio_sizes = []
rebalance_records = []

for i in range(len(rebalance_dates)):
    rebalance_date = rebalance_dates[i]

    # 次回リバランス日（エグジット日）
    if i < len(rebalance_dates) - 1:
        next_rebalance_date = rebalance_dates[i + 1]
    else:
        print(f"  {rebalance_date.date()}: 最後のリバランス、スキップ")
        continue

    print(f"\n  {rebalance_date.date()}: 銘柄選定中...")

    # リバランス日時点で利用可能な最新の財務データを使用
    available_data = df_marketcap[df_marketcap['disclosed_date'] < rebalance_date].copy()

    if len(available_data) == 0:
        print(f"    データなし、スキップ")
        continue

    # 各銘柄の最新の財務データのみを使用
    latest_data = available_data.sort_values('disclosed_date').groupby('code').last().reset_index()

    # 時価総額の四分位を再計算
    latest_data['marketcap_quartile'] = pd.qcut(
        latest_data['market_cap'],
        q=4,
        labels=['Q1', 'Q2', 'Q3', 'Q4'],
        duplicates='drop'
    )

    # 大型株（Q4）を抽出
    large_cap = latest_data[latest_data['marketcap_quartile'] == 'Q4'].copy()

    print(f"    大型株候補: {len(large_cap)} 銘柄")

    # 過去6ヶ月のボラティリティを計算
    volatilities = []
    codes_with_vol = []

    # 6ヶ月前の日付
    six_months_ago = rebalance_date - pd.Timedelta(days=180)

    for code in large_cap['code']:
        if code not in df_price_pivot.columns:
            continue

        # 過去6ヶ月の価格データを取得
        past_prices = df_price_pivot.loc[
            (df_price_pivot.index >= six_months_ago) &
            (df_price_pivot.index < rebalance_date),
            code
        ]

        if len(past_prices) < 60:  # 最低60営業日必要
            continue

        # 日次リターンを計算
        returns = past_prices.pct_change().dropna()

        if len(returns) < 60:
            continue

        # ボラティリティ（標準偏差）
        volatility = returns.std()

        volatilities.append(volatility)
        codes_with_vol.append(code)

    print(f"    ボラティリティ計算完了: {len(codes_with_vol)} 銘柄")

    if len(codes_with_vol) == 0:
        print(f"    ボラティリティ計算失敗、スキップ")
        continue

    # ボラティリティデータフレーム
    vol_df = pd.DataFrame({
        'code': codes_with_vol,
        'volatility': volatilities
    })

    # ボラティリティの四分位を計算
    vol_df['vol_quartile'] = pd.qcut(
        vol_df['volatility'],
        q=4,
        labels=['Q1', 'Q2', 'Q3', 'Q4'],
        duplicates='drop'
    )

    # 低ボラティリティ（Q1）を選定
    low_vol = vol_df[vol_df['vol_quartile'] == 'Q1'].copy()

    print(f"    低ボラティリティ銘柄: {len(low_vol)} 銘柄")

    # 上位20銘柄を選定（ボラティリティの低い順）
    strategy_portfolio = low_vol.nsmallest(20, 'volatility')

    # ベンチマーク1: 全銘柄
    benchmark_all = latest_data.copy()

    # ベンチマーク2: 大型株
    benchmark_large = large_cap.copy()

    print(f"    選定完了: 戦略={len(strategy_portfolio)}銘柄, 大型株BM={len(benchmark_large)}銘柄")

    # エントリー価格を取得
    entry_dates = df_price_pivot.index[df_price_pivot.index >= rebalance_date]
    if len(entry_dates) == 0:
        print(f"    エントリー日なし、スキップ")
        continue
    entry_date = entry_dates[0]

    # エグジット価格を取得
    exit_dates = df_price_pivot.index[df_price_pivot.index >= next_rebalance_date]
    if len(exit_dates) == 0:
        print(f"    エグジット日なし、スキップ")
        continue
    exit_date = exit_dates[0]

    print(f"    エントリー日: {entry_date.date()}, エグジット日: {exit_date.date()}")

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

    # ベンチマーク2（大型株）のリターンを計算
    benchmark_large_rets = []
    for code in benchmark_large['code']:
        if code not in df_price_pivot.columns:
            continue
        entry_price = df_price_pivot.loc[entry_date, code]
        exit_price = df_price_pivot.loc[exit_date, code]
        if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
            ret = (exit_price - entry_price) / entry_price
            benchmark_large_rets.append(ret)

    # 等ウェイトポートフォリオの平均リターン
    portfolio_return = np.mean(strategy_returns) if len(strategy_returns) > 0 else 0.0
    benchmark_all_return = np.mean(benchmark_all_rets) if len(benchmark_all_rets) > 0 else 0.0
    benchmark_large_return = np.mean(benchmark_large_rets) if len(benchmark_large_rets) > 0 else 0.0
    portfolio_size = len(strategy_returns)

    portfolio_returns.append(portfolio_return)
    benchmark_all_returns.append(benchmark_all_return)
    benchmark_large_returns.append(benchmark_large_return)
    portfolio_sizes.append(portfolio_size)

    rebalance_records.append({
        'rebalance_date': rebalance_date,
        'entry_date': entry_date,
        'exit_date': exit_date,
        'portfolio_return': portfolio_return,
        'benchmark_all_return': benchmark_all_return,
        'benchmark_large_return': benchmark_large_return,
        'portfolio_size': portfolio_size
    })

    print(f"    戦略={portfolio_return*100:+6.2f}%, 全銘柄={benchmark_all_return*100:+6.2f}%, 大型株={benchmark_large_return*100:+6.2f}%")

# ================================================================================
# 4. パフォーマンス指標の計算
# ================================================================================

print("\n[4/5] パフォーマンス指標を計算中...")

# DataFrameに変換
df_backtest = pd.DataFrame(rebalance_records)
df_backtest['rebalance_date'] = pd.to_datetime(df_backtest['rebalance_date'])

# 累積リターンの計算
df_backtest['cumulative_return_strategy'] = (1 + df_backtest['portfolio_return']).cumprod()
df_backtest['cumulative_return_all'] = (1 + df_backtest['benchmark_all_return']).cumprod()
df_backtest['cumulative_return_large'] = (1 + df_backtest['benchmark_large_return']).cumprod()

# 最終的な累積リターン
final_return_strategy = df_backtest['cumulative_return_strategy'].iloc[-1] - 1
final_return_all = df_backtest['cumulative_return_all'].iloc[-1] - 1
final_return_large = df_backtest['cumulative_return_large'].iloc[-1] - 1

# 年率リターン（CAGR）
years = len(df_backtest)  # 年次リバランスなので回数=年数
cagr_strategy = (df_backtest['cumulative_return_strategy'].iloc[-1] ** (1 / years)) - 1
cagr_all = (df_backtest['cumulative_return_all'].iloc[-1] ** (1 / years)) - 1
cagr_large = (df_backtest['cumulative_return_large'].iloc[-1] ** (1 / years)) - 1

# ボラティリティ（年率）
volatility_strategy = df_backtest['portfolio_return'].std()
volatility_all = df_backtest['benchmark_all_return'].std()
volatility_large = df_backtest['benchmark_large_return'].std()

# シャープレシオ
sharpe_strategy = cagr_strategy / volatility_strategy if volatility_strategy > 0 else 0
sharpe_all = cagr_all / volatility_all if volatility_all > 0 else 0
sharpe_large = cagr_large / volatility_large if volatility_large > 0 else 0

# 最大ドローダウン
def calculate_max_drawdown(cumulative_returns):
    running_max = cumulative_returns.cummax()
    drawdown = (cumulative_returns - running_max) / running_max
    return drawdown.min()

mdd_strategy = calculate_max_drawdown(df_backtest['cumulative_return_strategy'])
mdd_all = calculate_max_drawdown(df_backtest['cumulative_return_all'])
mdd_large = calculate_max_drawdown(df_backtest['cumulative_return_large'])

# 勝率
win_rate_strategy = (df_backtest['portfolio_return'] > 0).sum() / len(df_backtest)
win_rate_all = (df_backtest['benchmark_all_return'] > 0).sum() / len(df_backtest)
win_rate_large = (df_backtest['benchmark_large_return'] > 0).sum() / len(df_backtest)

# ベース戦略との相関（仮のデータ、実際にはベース戦略のリターンデータが必要）
# ここでは全銘柄ベンチマークとの相関を計算
correlation_vs_all = df_backtest['portfolio_return'].corr(df_backtest['benchmark_all_return'])
correlation_vs_large = df_backtest['portfolio_return'].corr(df_backtest['benchmark_large_return'])

# ================================================================================
# 5. 結果の表示
# ================================================================================

print("\n" + "="*80)
print("パフォーマンスサマリ")
print("="*80)

print(f"\nバックテスト期間: {df_backtest['rebalance_date'].iloc[0].date()} ~ {df_backtest['rebalance_date'].iloc[-1].date()}")
print(f"リバランス回数: {len(df_backtest)}")
print(f"運用期間: {years}年")

print("\n【累積リターン】")
print(f"  戦略（大型株×低Vol）: {final_return_strategy*100:+7.2f}%")
print(f"  ベンチマーク（全銘柄）: {final_return_all*100:+7.2f}%")
print(f"  ベンチマーク（大型株）: {final_return_large*100:+7.2f}%")

print("\n【年率リターン（CAGR）】")
print(f"  戦略（大型株×低Vol）: {cagr_strategy*100:+7.2f}%")
print(f"  ベンチマーク（全銘柄）: {cagr_all*100:+7.2f}%")
print(f"  ベンチマーク（大型株）: {cagr_large*100:+7.2f}%")

print("\n【ボラティリティ（年率）】")
print(f"  戦略（大型株×低Vol）: {volatility_strategy*100:7.2f}%")
print(f"  ベンチマーク（全銘柄）: {volatility_all*100:7.2f}%")
print(f"  ベンチマーク（大型株）: {volatility_large*100:7.2f}%")

print("\n【シャープレシオ】")
print(f"  戦略（大型株×低Vol）: {sharpe_strategy:7.3f}")
print(f"  ベンチマーク（全銘柄）: {sharpe_all:7.3f}")
print(f"  ベンチマーク（大型株）: {sharpe_large:7.3f}")

print("\n【最大ドローダウン】")
print(f"  戦略（大型株×低Vol）: {mdd_strategy*100:+7.2f}%")
print(f"  ベンチマーク（全銘柄）: {mdd_all*100:+7.2f}%")
print(f"  ベンチマーク（大型株）: {mdd_large*100:+7.2f}%")

print("\n【勝率】")
print(f"  戦略（大型株×低Vol）: {win_rate_strategy*100:7.2f}%")
print(f"  ベンチマーク（全銘柄）: {win_rate_all*100:7.2f}%")
print(f"  ベンチマーク（大型株）: {win_rate_large*100:7.2f}%")

print("\n【相関係数】")
print(f"  vs 全銘柄: {correlation_vs_all:+7.3f}")
print(f"  vs 大型株: {correlation_vs_large:+7.3f}")

print("\n【アウトパフォーマンス】")
print(f"  vs 全銘柄: {(cagr_strategy - cagr_all)*100:+7.2f}% (年率)")
print(f"  vs 大型株: {(cagr_strategy - cagr_large)*100:+7.2f}% (年率)")

print("\n【平均銘柄数】")
print(f"  {df_backtest['portfolio_size'].mean():.1f} 銘柄")

# ================================================================================
# 6. 結果の保存
# ================================================================================

print("\n[5/5] 結果を保存中...")

output_dir = PROJECT_ROOT / 'analyses' / '20260225_1700_large_cap_low_vol' / 'results'
output_dir.mkdir(exist_ok=True, parents=True)

# 詳細データ
df_backtest.to_csv(output_dir / 'backtest_results.csv', index=False, encoding='utf-8-sig')

# サマリ
summary = {
    'strategy_name': 'Large Cap × Low Volatility',
    'backtest_period': {
        'start': str(df_backtest['rebalance_date'].iloc[0].date()),
        'end': str(df_backtest['rebalance_date'].iloc[-1].date()),
        'years': int(years)
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
        'benchmark_large': {
            'cumulative_return': float(final_return_large),
            'cagr': float(cagr_large),
            'volatility': float(volatility_large),
            'sharpe_ratio': float(sharpe_large),
            'max_drawdown': float(mdd_large),
            'win_rate': float(win_rate_large)
        }
    },
    'correlation': {
        'vs_all': float(correlation_vs_all),
        'vs_large': float(correlation_vs_large)
    },
    'outperformance': {
        'vs_all_cagr': float(cagr_strategy - cagr_all),
        'vs_large_cagr': float(cagr_strategy - cagr_large)
    },
    'portfolio_stats': {
        'avg_size': float(df_backtest['portfolio_size'].mean()),
        'min_size': int(df_backtest['portfolio_size'].min()),
        'max_size': int(df_backtest['portfolio_size'].max())
    }
}

with open(output_dir / 'summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("バックテスト完了")
print("="*80)

print("\n【主要な発見】")
print(f"\n1. 年率リターン: {cagr_strategy*100:+.2f}%")
print(f"   - ベース戦略（想定+28.52%）との比較は別途必要")

print(f"\n2. リスク調整後リターン:")
print(f"   - シャープレシオ: {sharpe_strategy:.3f}")
print(f"   - 最大ドローダウン: {mdd_strategy*100:.2f}%")

print(f"\n3. 相関係数:")
print(f"   - vs 全銘柄: {correlation_vs_all:+.3f}")
print(f"   - vs 大型株: {correlation_vs_large:+.3f}")

print(f"\n4. 平均銘柄数: {df_backtest['portfolio_size'].mean():.1f} 銘柄")

print("\n注: ベース戦略（低PBR×高ROE）との相関は、ベース戦略のリターンデータが必要です")
