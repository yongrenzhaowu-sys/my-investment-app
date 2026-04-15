"""
ポートフォリオ最適化: ベース戦略 + レバレッジ戦略

目的: MDDを-30%以下に抑えつつ、年率+30%前後を実現

戦略:
- ベース戦略（低PBR×高ROE、年次リバランス）
- レバレッジ戦略（小型×高成長、月次リバランス、Target25_LB3）

アプローチ:
- 複数の配分比率でテスト（30/70, 40/60, 50/50, 60/40, 70/30）
- MDD -30%以下の最適設定を特定
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# プロジェクトルート
PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("ポートフォリオ最適化: ベース戦略 + レバレッジ戦略")
print("="*80)

# ================================================================================
# 1. ベース戦略のリターンを準備
# ================================================================================

print("\n[1/4] ベース戦略の月次リターンを準備中...")

# ベース戦略（低PBR×高ROE）の年次リターン
# 期間: 2017-10-01 ~ 2025-09-30（各年10月1日リバランス）
base_annual_returns = {
    '2017-10': 0.5211,  # 2017-10-01 ~ 2018-09-30
    '2018-10': 0.0979,  # 2018-10-01 ~ 2019-09-30
    '2019-10': 0.2799,  # 2019-10-01 ~ 2020-09-30
    '2020-10': 0.1585,  # 2020-10-01 ~ 2021-09-30
    '2021-10': 0.0722,  # 2021-10-01 ~ 2022-09-30
    '2022-10': 0.1862,  # 2022-10-01 ~ 2023-09-30
    '2023-10': 0.4143,  # 2023-10-01 ~ 2024-09-30
    '2024-10': 0.0000,  # 2024-10-01 ~ 2025-09-30（進行中、仮0%）
}

# 月次リターンに変換（簡易版: 年次リターンを12ヶ月で等分）
base_monthly_returns = []
base_monthly_labels = []

for year_start, annual_return in base_annual_returns.items():
    year_month = pd.Period(year_start, freq='M')

    # 12ヶ月分の月次リターンを生成
    # (1 + annual_return)^(1/12) - 1
    monthly_return = (1 + annual_return) ** (1/12) - 1

    for i in range(12):
        month = year_month + i
        base_monthly_returns.append(monthly_return)
        base_monthly_labels.append(month)

print(f"ベース戦略の月次リターン: {len(base_monthly_returns)}ヶ月")
print(f"期間: {base_monthly_labels[0]} ~ {base_monthly_labels[-1]}")

# 年率換算（確認）
base_series = pd.Series(base_monthly_returns)
base_cumulative = (1 + base_series).cumprod().iloc[-1] - 1
base_years = len(base_monthly_returns) / 12
base_cagr = (1 + base_cumulative) ** (1 / base_years) - 1
print(f"ベース戦略の年率リターン（再計算）: {base_cagr*100:+.2f}%")

# ================================================================================
# 2. レバレッジ戦略のリターンを取得
# ================================================================================

print("\n[2/4] レバレッジ戦略の月次リターンを読み込み中...")

# レバレッジ戦略（Target25_LB3）の結果をロード
# 注: backtest_07_leverage.pyから月次リターンを再計算

# 既存のロジックを再利用してレバレッジ戦略のリターンを計算
# （簡略化のため、ここではbacktest_07の結果を直接使用）

print("レバレッジ戦略（Target25_LB3）を再計算中...")

# データ読み込み
df_growth = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_by_marketcap/growth_rate_by_marketcap.csv',
    parse_dates=['disclosed_date']
)
df_growth = df_growth[['code', 'disclosed_date', 'custom_growth_rate', 'market_cap']].copy()
df_growth = df_growth.dropna()

df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2017-01-01'].copy()
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

# 月次リバランス戦略のリターンを計算
months = pd.period_range(start='2017-01', end='2025-12', freq='M')
strategy_returns = []
strategy_labels = []

for i in range(len(months) - 1):
    current_month = months[i]
    next_month = months[i + 1]

    current_month_start = pd.Timestamp(f"{current_month}-01")
    next_month_start = pd.Timestamp(f"{next_month}-01")

    available_data = df_growth[df_growth['disclosed_date'] < current_month_start].copy()
    if len(available_data) == 0:
        continue

    latest_data = available_data.sort_values('disclosed_date').groupby('code').last().reset_index()
    if len(latest_data) < 20:
        continue

    try:
        latest_data['marketcap_quartile'] = pd.qcut(
            latest_data['market_cap'], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop'
        )
        latest_data['growth_quartile'] = pd.qcut(
            latest_data['custom_growth_rate'], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop'
        )
    except ValueError:
        continue

    strategy_portfolio = latest_data[
        (latest_data['marketcap_quartile'] == 'Q1') &
        (latest_data['growth_quartile'] == 'Q4')
    ].copy()

    if len(strategy_portfolio) == 0:
        continue

    entry_dates = [d for d in df_price_pivot.index if d >= current_month_start and d < next_month_start]
    exit_dates = [d for d in df_price_pivot.index if d >= next_month_start]

    if len(entry_dates) == 0 or len(exit_dates) == 0:
        continue

    entry_date = entry_dates[0]
    exit_date = exit_dates[0]

    stock_returns = []
    for code in strategy_portfolio['code']:
        if code not in df_price_pivot.columns:
            continue

        entry_price = df_price_pivot.loc[entry_date, code]
        exit_price = df_price_pivot.loc[exit_date, code]

        if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
            ret = (exit_price - entry_price) / entry_price
            stock_returns.append(ret)

    if len(stock_returns) == 0:
        continue

    portfolio_return = np.mean(stock_returns)
    strategy_returns.append(portfolio_return)
    strategy_labels.append(current_month)

print(f"戦略リターン計算完了: {len(strategy_returns)}ヶ月")

# ボラティリティターゲティング（Target25_LB3）を適用
target_vol = 0.25
lookback_months = 3

leverage_returns = []
for i in range(len(strategy_returns)):
    if i < lookback_months:
        leverage_returns.append(strategy_returns[i])
    else:
        past_returns = strategy_returns[i-lookback_months:i]
        realized_vol = np.std(past_returns) * np.sqrt(12)

        if realized_vol > 0:
            position_size = target_vol / realized_vol
            position_size = np.clip(position_size, 0.20, 2.00)
        else:
            position_size = 1.0

        adjusted_return = strategy_returns[i] * position_size
        leverage_returns.append(adjusted_return)

print(f"レバレッジ戦略の月次リターン: {len(leverage_returns)}ヶ月")
print(f"期間: {strategy_labels[0]} ~ {strategy_labels[-1]}")

# ================================================================================
# 3. ポートフォリオ最適化（複数の配分比率でテスト）
# ================================================================================

print("\n[3/4] ポートフォリオ最適化中...")

# 共通期間を抽出（2017-10 ~ 2025-09）
common_start = pd.Period('2017-10', freq='M')
common_end = pd.Period('2025-09', freq='M')

# ベース戦略のリターンをフィルター
base_returns_filtered = []
for i, month in enumerate(base_monthly_labels):
    if common_start <= month <= common_end:
        base_returns_filtered.append(base_monthly_returns[i])

# レバレッジ戦略のリターンをフィルター
leverage_returns_filtered = []
for i, month in enumerate(strategy_labels):
    if common_start <= month <= common_end:
        leverage_returns_filtered.append(leverage_returns[i])

# 長さを合わせる（短い方に合わせる）
min_length = min(len(base_returns_filtered), len(leverage_returns_filtered))
base_returns_filtered = base_returns_filtered[:min_length]
leverage_returns_filtered = leverage_returns_filtered[:min_length]

print(f"共通期間: {min_length}ヶ月")

# 配分比率のテスト
allocations = [
    (0.2, 0.8, 'Base20_Lev80'),
    (0.3, 0.7, 'Base30_Lev70'),
    (0.4, 0.6, 'Base40_Lev60'),
    (0.5, 0.5, 'Base50_Lev50'),
    (0.6, 0.4, 'Base60_Lev40'),
    (0.7, 0.3, 'Base70_Lev30'),
    (0.8, 0.2, 'Base80_Lev20'),
]

results = []

for weight_base, weight_leverage, name in allocations:
    print(f"\n--- {name}: ベース{weight_base*100:.0f}% + レバレッジ{weight_leverage*100:.0f}% ---")

    # ポートフォリオリターン
    portfolio_returns = [
        base_returns_filtered[i] * weight_base + leverage_returns_filtered[i] * weight_leverage
        for i in range(min_length)
    ]

    portfolio_series = pd.Series(portfolio_returns)

    # パフォーマンス計算
    cumulative_return = (1 + portfolio_series).cumprod().iloc[-1] - 1
    years = len(portfolio_returns) / 12
    cagr = (1 + cumulative_return) ** (1 / years) - 1
    volatility = portfolio_series.std() * np.sqrt(12)
    sharpe = cagr / volatility if volatility > 0 else 0

    cumulative_series = (1 + portfolio_series).cumprod()
    peak = cumulative_series.expanding(min_periods=1).max()
    drawdown = (cumulative_series - peak) / peak
    max_drawdown = drawdown.min()

    win_rate = (portfolio_series > 0).mean()

    result = {
        'name': name,
        'weight_base': weight_base,
        'weight_leverage': weight_leverage,
        'cagr': cagr,
        'volatility': volatility,
        'sharpe': sharpe,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
    }
    results.append(result)

    print(f"  年率リターン: {cagr*100:+.2f}%")
    print(f"  ボラティリティ: {volatility*100:.2f}%")
    print(f"  シャープレシオ: {sharpe:.3f}")
    print(f"  最大DD: {max_drawdown*100:.2f}%")

# ================================================================================
# 4. 最適ポートフォリオの特定（MDD -30%以下）
# ================================================================================

print("\n[4/4] 最適ポートフォリオを特定中...")

# MDD -30%以下をフィルター
feasible = [r for r in results if r['max_drawdown'] >= -0.30]

if len(feasible) > 0:
    # リターンが最も高い設定を推奨
    optimal = max(feasible, key=lambda x: x['cagr'])

    print(f"\n【最適ポートフォリオ（MDD -30%以下）】")
    print(f"  配分: {optimal['name']}")
    print(f"  年率リターン: {optimal['cagr']*100:+.2f}%")
    print(f"  最大DD: {optimal['max_drawdown']*100:.2f}%")
    print(f"  シャープレシオ: {optimal['sharpe']:.3f}")
else:
    print("\n【警告】MDD -30%以下の設定が見つかりません")
    optimal = None

# 結果サマリ
print("\n" + "="*80)
print("ポートフォリオ最適化結果")
print("="*80)

print(f"\n{'配分':<20} {'年率':>8} {'MDD':>8} {'Sharpe':>8} {'判定':>10}")
print("-" * 80)

for result in results:
    mdd_check = "[OK]" if result['max_drawdown'] >= -0.30 else "[NG]"
    print(f"{result['name']:<20} "
          f"{result['cagr']*100:>7.2f}% "
          f"{result['max_drawdown']*100:>7.2f}% "
          f"{result['sharpe']:>8.3f} "
          f"{mdd_check:>10}")

if optimal:
    print(f"\n【推奨設定】: {optimal['name']}")
    print(f"  ベース戦略: {optimal['weight_base']*100:.0f}%")
    print(f"  レバレッジ戦略: {optimal['weight_leverage']*100:.0f}%")
    print(f"  年率リターン: {optimal['cagr']*100:+.2f}%")
    print(f"  最大DD: {optimal['max_drawdown']*100:.2f}%")
    print(f"  シャープレシオ: {optimal['sharpe']:.3f}")

# 参考: 単体戦略
print(f"\n【参考: 単体戦略】")
print(f"  ベース戦略: 年率+28.52%, MDD -2.41%, Sharpe 1.48")
print(f"  レバレッジ戦略: 年率+31.92%, MDD -40.62%, Sharpe 1.138")

# 結果を保存
output_dir = PROJECT_ROOT / 'analyses/20260225_1800_event_driven_strategy/results_portfolio_mix'
output_dir.mkdir(exist_ok=True, parents=True)

df_results = pd.DataFrame(results)
df_results.to_csv(output_dir / 'performance_summary.csv', index=False)

if optimal:
    with open(output_dir / 'optimal_portfolio.txt', 'w', encoding='utf-8') as f:
        f.write("最適ポートフォリオ（MDD -30%以下）\n")
        f.write("="*80 + "\n\n")
        f.write(f"配分: {optimal['name']}\n")
        f.write(f"ベース戦略: {optimal['weight_base']*100:.0f}%\n")
        f.write(f"レバレッジ戦略: {optimal['weight_leverage']*100:.0f}%\n\n")
        f.write(f"年率リターン: {optimal['cagr']*100:+.2f}%\n")
        f.write(f"ボラティリティ: {optimal['volatility']*100:.2f}%\n")
        f.write(f"シャープレシオ: {optimal['sharpe']:.3f}\n")
        f.write(f"最大ドローダウン: {optimal['max_drawdown']*100:.2f}%\n")
        f.write(f"勝率: {optimal['win_rate']*100:.2f}%\n")

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("ポートフォリオ最適化完了")
print("="*80)

print("\n【結論】")
if optimal:
    if optimal['max_drawdown'] >= -0.25:
        print(f"- MDD {optimal['max_drawdown']*100:.2f}%を達成（目標-30%以下）")
        print(f"- 年率リターン {optimal['cagr']*100:+.2f}%を維持")
        print(f"- シャープレシオ {optimal['sharpe']:.3f}（良好）")
    else:
        print(f"- MDD {optimal['max_drawdown']*100:.2f}%（目標-30%ギリギリ）")
        print(f"- より保守的な配分を検討する余地あり")
else:
    print("- MDD -30%以下の設定が見つかりませんでした")
    print("- ベース戦略の配分を増やす必要があります")
