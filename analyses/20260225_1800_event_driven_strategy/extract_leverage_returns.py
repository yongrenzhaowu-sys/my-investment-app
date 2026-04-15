"""
レバレッジ戦略（Target25_LB3）の月次リターンを抽出

目的: ポートフォリオ最適化で使用するため、Target25_LB3の月次リターンをCSVに保存
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("レバレッジ戦略（Target25_LB3）月次リターン抽出")
print("="*80)

# データ読み込み
print("\n[1/3] データ読み込み中...")

df_growth = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_by_marketcap/growth_rate_by_marketcap.csv',
    parse_dates=['disclosed_date']
)
df_growth = df_growth[['code', 'disclosed_date', 'custom_growth_rate', 'market_cap']].copy()
df_growth = df_growth.dropna()

# 四分位を計算
df_growth['growth_quartile'] = pd.qcut(df_growth['custom_growth_rate'], 4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')
df_growth['mcap_quartile'] = pd.qcut(df_growth['market_cap'], 4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')

df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2017-01-01'].copy()
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

print(f"成長率データ: {len(df_growth):,}行")
print(f"価格データ: {len(df_price):,}行")

# 月次リバランス日
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

# 基本戦略リターン計算
print("\n[2/3] 基本戦略の月次リターンを計算中...")

base_strategy_returns = []
month_labels = []

for i in range(len(rebalance_dates) - 1):
    current_month = rebalance_dates[i]
    next_month = rebalance_dates[i + 1]

    # データ準備
    available_data = df_growth[df_growth['disclosed_date'] <= current_month].copy()
    latest_data = available_data.sort_values('disclosed_date').groupby('code').tail(1)

    # 小型株（Q1）× 高成長（Q4）
    strategy_portfolio = latest_data[
        (latest_data['mcap_quartile'] == 'Q1') &
        (latest_data['growth_quartile'] == 'Q4')
    ].copy()

    if len(strategy_portfolio) == 0:
        continue

    # エントリー日とエグジット日
    entry_dates = [d for d in df_price_pivot.index if d >= current_month and d < next_month]
    exit_dates = [d for d in df_price_pivot.index if d >= next_month]

    if len(entry_dates) == 0 or len(exit_dates) == 0:
        continue

    entry_date = entry_dates[0]
    exit_date = exit_dates[0]

    # リターン計算
    strategy_returns = []
    for code in strategy_portfolio['code']:
        if code not in df_price_pivot.columns:
            continue

        entry_price = df_price_pivot.loc[entry_date, code]
        exit_price = df_price_pivot.loc[exit_date, code]

        if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
            ret = (exit_price - entry_price) / entry_price
            strategy_returns.append(ret)

    if len(strategy_returns) == 0:
        continue

    portfolio_return = np.mean(strategy_returns)
    base_strategy_returns.append(portfolio_return)
    month_labels.append(current_month)

print(f"基本戦略の月次リターン: {len(base_strategy_returns)}ヶ月")

# Target25_LB3を適用
print("\n[3/3] Target25_LB3を適用中...")

TARGET_VOL = 0.25
LOOKBACK_MONTHS = 3
MAX_LEVERAGE = 2.0

adjusted_returns = []
month_labels_final = []

for i in range(len(base_strategy_returns)):
    if i < LOOKBACK_MONTHS:
        # 初期期間はフルポジション
        adjusted_returns.append(base_strategy_returns[i])
    else:
        # 過去ボラティリティを計算
        past_returns = base_strategy_returns[i-LOOKBACK_MONTHS:i]
        realized_vol = np.std(past_returns) * np.sqrt(12)

        # ポジションサイズを計算
        if realized_vol > 0:
            position_size = TARGET_VOL / realized_vol
            position_size = np.clip(position_size, 0.20, MAX_LEVERAGE)
        else:
            position_size = 1.0

        # リターンを調整
        adjusted_return = base_strategy_returns[i] * position_size
        adjusted_returns.append(adjusted_return)

    month_labels_final.append(month_labels[i])

# DataFrameに変換
df_leverage_returns = pd.DataFrame({
    'year_month': month_labels_final,
    'return': adjusted_returns
})

print(f"Target25_LB3の月次リターン: {len(df_leverage_returns)}ヶ月")

# パフォーマンス確認
cumulative_return = (1 + df_leverage_returns['return']).cumprod().iloc[-1] - 1
years = len(df_leverage_returns) / 12
cagr = (1 + cumulative_return) ** (1 / years) - 1

cumulative_series = (1 + df_leverage_returns['return']).cumprod()
peak = cumulative_series.expanding(min_periods=1).max()
drawdown = (cumulative_series - peak) / peak
mdd = drawdown.min()

volatility = df_leverage_returns['return'].std() * np.sqrt(12)
sharpe = cagr / volatility if volatility > 0 else 0

print(f"\nパフォーマンス:")
print(f"  年率リターン: {cagr*100:+.2f}%")
print(f"  最大DD: {mdd*100:.2f}%")
print(f"  ボラティリティ: {volatility*100:.2f}%")
print(f"  シャープレシオ: {sharpe:.3f}")

# 保存
output_dir = PROJECT_ROOT / 'analyses/20260225_1800_event_driven_strategy/results_leverage'
output_dir.mkdir(exist_ok=True, parents=True)

df_leverage_returns.to_csv(output_dir / 'monthly_returns_target25_lb3.csv', index=False)

print(f"\n保存先: {output_dir / 'monthly_returns_target25_lb3.csv'}")
print("\n完了！")
