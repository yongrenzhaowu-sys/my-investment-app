"""
ポートフォリオ最適化（修正版）: ベース戦略 + レバレッジ戦略

目的: MDDを-30%以下に抑えつつ、高リターンを実現

修正点:
- ベース戦略の正確な月次リターンを使用（日次評価版から）
- ベース戦略の実際のMDD: -27.70%（-2.41%ではない）

戦略:
- ベース戦略（低PBR×高ROE、年次リバランス）
  - 年率: +24.27%, MDD: -27.70%, Sharpe: 1.010
- レバレッジ戦略（小型×高成長、月次リバランス、Target25_LB3）
  - 年率: +31.92%, MDD: -40.62%, Sharpe: 1.138

配分比率テスト:
- Base20_Lev80, Base30_Lev70, Base40_Lev60, Base50_Lev50, Base60_Lev40, Base70_Lev30, Base80_Lev20
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("ポートフォリオ最適化（修正版）: ベース戦略 + レバレッジ戦略")
print("="*80)

# ================================================================================
# 1. ベース戦略の月次リターンを読み込み（日次評価版から）
# ================================================================================

print("\n[1/4] ベース戦略の月次リターンを準備中...")

# 日次評価版から日次データを読み込み
df_daily = pd.read_csv(PROJECT_ROOT / 'analyses/base_strategy_daily/daily_values.csv')
df_daily['date'] = pd.to_datetime(df_daily['date'])
df_daily = df_daily.sort_values('date')

print(f"ベース戦略の日次データ: {len(df_daily)}日")

# 月次リターンを計算
df_daily['year_month'] = df_daily['date'].dt.to_period('M').dt.to_timestamp()

# 各月の最終日の累積値を取得
monthly_last = df_daily.groupby('year_month')['cumulative_value'].last()

# 月次リターンを計算
monthly_returns = monthly_last.pct_change().dropna()

df_base = pd.DataFrame({
    'year_month': monthly_returns.index,
    'return': monthly_returns.values
})

print(f"ベース戦略の月次リターン: {len(df_base)}ヶ月")
print(f"期間: {df_base['year_month'].iloc[0].date()} ~ {df_base['year_month'].iloc[-1].date()}")

# パフォーマンス確認
base_cumulative = (1 + df_base['return']).cumprod().iloc[-1] - 1
base_years = len(df_base) / 12
base_cagr = (1 + base_cumulative) ** (1 / base_years) - 1

# MDDを計算（確認）
base_cum_series = (1 + df_base['return']).cumprod()
base_peak = base_cum_series.expanding().max()
base_dd = (base_cum_series - base_peak) / base_peak
base_mdd = base_dd.min()

print(f"ベース戦略の年率リターン: {base_cagr*100:+.2f}%")
print(f"ベース戦略のMDD: {base_mdd*100:.2f}%")

# ================================================================================
# 2. レバレッジ戦略の月次リターンを計算
# ================================================================================

print("\n[2/4] レバレッジ戦略（Target25_LB3）を計算中...")

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

# 月次リバランス日を生成
all_dates = sorted(df_price_pivot.index)
rebalance_dates = []
for year in range(2017, 2026):
    for month in range(1, 13):
        target_date = pd.Timestamp(f'{year}-{month:02d}-01')
        available_dates = [d for d in all_dates if d >= target_date]
        if len(available_dates) > 0:
            rebalance_dates.append(available_dates[0])

rebalance_dates = sorted(list(set(rebalance_dates)))
rebalance_dates = [d for d in rebalance_dates if d <= pd.Timestamp('2025-12-31')]

print(f"リバランス日数: {len(rebalance_dates)}")

# パラメータ: Target25_LB3
TARGET_VOL = 0.25
LOOKBACK_MONTHS = 3
N_STOCKS = 20

# 戦略リターンを計算
strategy_returns = []

for i in range(len(rebalance_dates)):
    rdate = rebalance_dates[i]

    # 次のリバランス日
    if i + 1 < len(rebalance_dates):
        next_rdate = rebalance_dates[i + 1]
    else:
        # 最後の期間: 次のリバランス日がないので期間終了まで
        next_rdate = all_dates[-1]

    # 小型株（時価総額下位25%）＆高成長（成長率上位25%）を選定
    available_growth = df_growth[df_growth['disclosed_date'] <= rdate].copy()
    latest_growth = available_growth.sort_values('disclosed_date').groupby('code').tail(1)

    # 時価総額と成長率でフィルター
    if len(latest_growth) < N_STOCKS:
        continue

    mcap_q1 = latest_growth['market_cap'].quantile(0.25)
    growth_q3 = latest_growth['custom_growth_rate'].quantile(0.75)

    candidates = latest_growth[
        (latest_growth['market_cap'] <= mcap_q1) &
        (latest_growth['custom_growth_rate'] >= growth_q3)
    ]

    if len(candidates) < N_STOCKS:
        candidates = latest_growth.nlargest(N_STOCKS, 'custom_growth_rate')

    selected = candidates.nlargest(N_STOCKS, 'custom_growth_rate')
    selected_codes = list(selected['code'])

    # エントリー価格
    entry_prices_day = None
    for d in all_dates:
        if d >= rdate:
            entry_prices_day = d
            break

    if entry_prices_day is None or entry_prices_day not in df_price_pivot.index:
        continue

    entry_prices = df_price_pivot.loc[entry_prices_day, selected_codes].dropna()

    if len(entry_prices) < N_STOCKS * 0.8:
        continue

    # イグジット価格
    exit_prices_day = None
    for d in all_dates:
        if d >= next_rdate:
            exit_prices_day = d
            break

    if exit_prices_day is None or exit_prices_day not in df_price_pivot.index:
        continue

    exit_prices = df_price_pivot.loc[exit_prices_day, entry_prices.index].dropna()

    # リターン計算
    common_codes = entry_prices.index.intersection(exit_prices.index)
    if len(common_codes) < N_STOCKS * 0.5:
        continue

    returns = (exit_prices[common_codes] - entry_prices[common_codes]) / entry_prices[common_codes]
    strategy_return = returns.mean()

    # ボラティリティターゲティング
    if i >= LOOKBACK_MONTHS:
        past_returns = [r['return'] for r in strategy_returns[-LOOKBACK_MONTHS:]]
        realized_vol = np.std(past_returns) * np.sqrt(12)

        if realized_vol > 0:
            position_size = TARGET_VOL / realized_vol
            position_size = np.clip(position_size, 0.20, 2.00)
            adjusted_return = strategy_return * position_size
        else:
            adjusted_return = strategy_return
    else:
        adjusted_return = strategy_return

    strategy_returns.append({
        'date': rdate,
        'return': adjusted_return
    })

df_leverage = pd.DataFrame(strategy_returns)
df_leverage['year_month'] = df_leverage['date'].dt.to_period('M')

# 月次に集約
leverage_monthly = df_leverage.groupby('year_month')['return'].apply(
    lambda x: (1 + x).prod() - 1
).reset_index()
leverage_monthly['year_month'] = leverage_monthly['year_month'].dt.to_timestamp()

print(f"レバレッジ戦略の月次リターン: {len(leverage_monthly)}ヶ月")
print(f"期間: {leverage_monthly['year_month'].iloc[0].date()} ~ {leverage_monthly['year_month'].iloc[-1].date()}")

# パフォーマンス確認
leverage_cumulative = (1 + leverage_monthly['return']).cumprod().iloc[-1] - 1
leverage_years = len(leverage_monthly) / 12
leverage_cagr = (1 + leverage_cumulative) ** (1 / leverage_years) - 1

leverage_cum_series = (1 + leverage_monthly['return']).cumprod()
leverage_peak = leverage_cum_series.expanding().max()
leverage_dd = (leverage_cum_series - leverage_peak) / leverage_peak
leverage_mdd = leverage_dd.min()

print(f"レバレッジ戦略の年率リターン: {leverage_cagr*100:+.2f}%")
print(f"レバレッジ戦略のMDD: {leverage_mdd*100:.2f}%")

# ================================================================================
# 3. 期間を合わせる
# ================================================================================

print("\n[3/4] 期間を合わせて月次リターンを整列中...")

# 共通期間を特定
df_base['year_month_ts'] = df_base['year_month']
leverage_monthly['year_month_ts'] = leverage_monthly['year_month']

merged = pd.merge(
    df_base[['year_month_ts', 'return']],
    leverage_monthly[['year_month_ts', 'return']],
    on='year_month_ts',
    how='inner',
    suffixes=('_base', '_leverage')
)

print(f"共通期間: {len(merged)}ヶ月")
print(f"期間: {merged['year_month_ts'].iloc[0].date()} ~ {merged['year_month_ts'].iloc[-1].date()}")

# ================================================================================
# 4. ポートフォリオ最適化（複数の配分比率でテスト）
# ================================================================================

print("\n[4/4] ポートフォリオ最適化を実行中...")

allocations = [
    (0.20, 0.80),
    (0.30, 0.70),
    (0.40, 0.60),
    (0.50, 0.50),
    (0.60, 0.40),
    (0.70, 0.30),
    (0.80, 0.20),
]

results = []

for weight_base, weight_leverage in allocations:
    # ポートフォリオリターン
    portfolio_returns = (
        merged['return_base'] * weight_base +
        merged['return_leverage'] * weight_leverage
    )

    # 累積リターン
    cumulative = (1 + portfolio_returns).cumprod()
    total_return = cumulative.iloc[-1] - 1

    # 年率リターン
    years = len(portfolio_returns) / 12
    cagr = (1 + total_return) ** (1 / years) - 1

    # MDD
    peak = cumulative.expanding().max()
    drawdown = (cumulative - peak) / peak
    mdd = drawdown.min()

    # ボラティリティ
    volatility = portfolio_returns.std() * np.sqrt(12)

    # シャープレシオ
    sharpe = cagr / volatility if volatility > 0 else 0

    # MDD判定
    mdd_status = "✅ OK" if mdd >= -0.30 else "❌ NG"

    results.append({
        'allocation': f"Base{int(weight_base*100)}_Lev{int(weight_leverage*100)}",
        'weight_base': weight_base,
        'weight_leverage': weight_leverage,
        'cagr': cagr,
        'mdd': mdd,
        'volatility': volatility,
        'sharpe': sharpe,
        'mdd_status': mdd_status,
    })

    print(f"  {results[-1]['allocation']}: 年率{cagr*100:+.2f}%, MDD {mdd*100:.2f}%, Sharpe {sharpe:.3f} [{mdd_status}]")

# 結果をDataFrameに変換
df_results = pd.DataFrame(results)

# ================================================================================
# 5. 最適ポートフォリオの特定
# ================================================================================

print("\n" + "="*80)
print("ポートフォリオ最適化結果")
print("="*80)

# MDD -30%以下の設定
optimal_candidates = df_results[df_results['mdd'] >= -0.30]

if len(optimal_candidates) > 0:
    # リターンが最も高い設定
    best = optimal_candidates.loc[optimal_candidates['cagr'].idxmax()]

    print(f"\n【推奨ポートフォリオ】 {best['allocation']}")
    print(f"  配分: ベース{best['weight_base']*100:.0f}% + レバレッジ{best['weight_leverage']*100:.0f}%")
    print(f"  年率リターン: {best['cagr']*100:+.2f}%")
    print(f"  最大DD: {best['mdd']*100:.2f}%")
    print(f"  ボラティリティ: {best['volatility']*100:.2f}%")
    print(f"  シャープレシオ: {best['sharpe']:.3f}")
    print(f"\n  ✅ MDD -30%以下を達成！")
else:
    print("\n【重要】MDD -30%以下を達成できる配分が見つかりませんでした")
    print("\nMDDが最も低い設定:")
    best = df_results.loc[df_results['mdd'].idxmax()]

    print(f"  {best['allocation']}")
    print(f"  配分: ベース{best['weight_base']*100:.0f}% + レバレッジ{best['weight_leverage']*100:.0f}%")
    print(f"  年率リターン: {best['cagr']*100:+.2f}%")
    print(f"  最大DD: {best['mdd']*100:.2f}%")
    print(f"  ボラティリティ: {best['volatility']*100:.2f}%")
    print(f"  シャープレシオ: {best['sharpe']:.3f}")

# ================================================================================
# 6. 結果を保存
# ================================================================================

output_dir = PROJECT_ROOT / 'analyses/20260225_1800_event_driven_strategy/results_portfolio_mix_corrected'
output_dir.mkdir(exist_ok=True, parents=True)

# 全結果を保存
df_results.to_csv(output_dir / 'performance_summary.csv', index=False)

# 最適ポートフォリオを保存
with open(output_dir / 'optimal_portfolio.txt', 'w', encoding='utf-8') as f:
    if len(optimal_candidates) > 0:
        f.write(f"最適ポートフォリオ: {best['allocation']}\n")
        f.write("="*80 + "\n\n")
        f.write(f"配分:\n")
        f.write(f"  ベース戦略（低PBR×高ROE）: {best['weight_base']*100:.0f}%\n")
        f.write(f"  レバレッジ戦略（Target25_LB3）: {best['weight_leverage']*100:.0f}%\n\n")
        f.write(f"パフォーマンス:\n")
        f.write(f"  年率リターン: {best['cagr']*100:+.2f}%\n")
        f.write(f"  最大DD: {best['mdd']*100:.2f}%\n")
        f.write(f"  ボラティリティ: {best['volatility']*100:.2f}%\n")
        f.write(f"  シャープレシオ: {best['sharpe']:.3f}\n\n")
        f.write(f"評価: ✅ MDD -30%以下を達成\n")
    else:
        f.write("【重要】MDD -30%以下を達成できる配分が見つかりませんでした\n")
        f.write("="*80 + "\n\n")
        f.write(f"MDDが最も低い設定: {best['allocation']}\n\n")
        f.write(f"配分:\n")
        f.write(f"  ベース戦略（低PBR×高ROE）: {best['weight_base']*100:.0f}%\n")
        f.write(f"  レバレッジ戦略（Target25_LB3）: {best['weight_leverage']*100:.0f}%\n\n")
        f.write(f"パフォーマンス:\n")
        f.write(f"  年率リターン: {best['cagr']*100:+.2f}%\n")
        f.write(f"  最大DD: {best['mdd']*100:.2f}%\n")
        f.write(f"  ボラティリティ: {best['volatility']*100:.2f}%\n")
        f.write(f"  シャープレシオ: {best['sharpe']:.3f}\n\n")
        f.write(f"評価: ❌ MDD -30%を超過（{best['mdd']*100:.2f}%）\n")

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("全結果（配分 / 年率 / MDD / Sharpe）:")
print("="*80)
for _, row in df_results.iterrows():
    print(f"  {row['allocation']:15s}: {row['cagr']*100:+6.2f}%  {row['mdd']*100:7.2f}%  {row['sharpe']:.3f}  [{row['mdd_status']}]")

print("\n完了！")
