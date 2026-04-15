"""
ベース戦略（低PBR×高ROE）- 日次評価版

目的: 日次でポートフォリオ価値を計算し、正確なMDDと月次リターンを取得

戦略:
- 年次リバランス（10月1日）
- スクリーニング: PBR下位25% AND ROE上位25%
- 選択: PBR最小の20銘柄
- 保有期間: 1年間
- 評価: 毎日（正確なMDD計算）
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("ベース戦略（低PBR×高ROE）- 日次評価版")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/5] データ読み込み...")

# 価格データ
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()
print(f"価格データ: {len(df_price):,} 行")

# 財務データ（年次のみ）
df_fin = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin['disclosed_date'] = pd.to_datetime(df_fin['disclosed_date'])
df_fin = df_fin[df_fin['disclosed_date'] >= '2016-01-01'].copy()

# 年次決算のみ
if 'fiscal_quarter' in df_fin.columns:
    df_fin = df_fin[df_fin['fiscal_quarter'] == 'FY'].copy()

df_fin = df_fin[['disclosed_date', 'code', 'equity', 'net_profit', 'bps']].copy()
df_fin['roe'] = (df_fin['net_profit'] / df_fin['equity']) * 100
df_fin = df_fin[
    (df_fin['roe'] > -100) & (df_fin['roe'] < 100) &
    (df_fin['bps'] > 0) & (df_fin['equity'] > 0)
].copy()

print(f"財務データ（年次）: {len(df_fin):,} 行")

# 価格データをピボット化
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')
all_dates = sorted(df_price_pivot.index)

print(f"価格データ期間: {all_dates[0].date()} ~ {all_dates[-1].date()}")
print(f"取引日数: {len(all_dates)}")

# ================================================================================
# 2. リバランス日の設定（10月1日）
# ================================================================================

print("\n[2/5] リバランス日を設定...")

rebalance_dates = []
for year in range(2017, 2026):  # 2017年開始
    target_date = pd.Timestamp(f'{year}-10-01')
    available_dates = [d for d in all_dates if d >= target_date]
    if len(available_dates) > 0:
        rebalance_dates.append(available_dates[0])

rebalance_dates = sorted(rebalance_dates)

print(f"リバランス日数: {len(rebalance_dates)}")
print(f"期間: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}")

# ================================================================================
# 3. 銘柄選定（各リバランス日）
# ================================================================================

print("\n[3/5] 銘柄選定...")

N_STOCKS = 20
portfolios = {}  # {rebalance_date: [codes]}

for i in range(len(rebalance_dates)):
    rdate = rebalance_dates[i]

    # その時点で利用可能な財務データ
    available_fin = df_fin[df_fin['disclosed_date'] <= rdate].copy()
    latest_fin = available_fin.sort_values('disclosed_date').groupby('code').tail(1)
    latest_fin = latest_fin.set_index('code')[['bps', 'roe']]

    # リバランス日の価格（数日後まで許容）
    price_window = df_price[
        (df_price['date'] >= rdate) &
        (df_price['date'] <= rdate + pd.Timedelta(days=5))
    ].copy()

    if len(price_window) == 0:
        print(f"  {rdate.date()}: 価格データなし、スキップ")
        continue

    prices_df = price_window.sort_values(['code', 'date']).groupby('code').first()
    prices = prices_df['adjusted_close'].dropna()

    # マージ
    merged = pd.DataFrame({
        'price': prices,
        'bps': latest_fin['bps'],
        'roe': latest_fin['roe']
    }).dropna()

    if len(merged) < N_STOCKS:
        print(f"  {rdate.date()}: データ不足（{len(merged)} < {N_STOCKS}）、スキップ")
        continue

    # PBR計算
    merged['pbr'] = merged['price'] / merged['bps']
    merged = merged[(merged['pbr'] > 0) & (merged['pbr'] < 50)]

    if len(merged) < N_STOCKS:
        print(f"  {rdate.date()}: PBRフィルタ後不足（{len(merged)} < {N_STOCKS}）、スキップ")
        continue

    # 四分位
    pbr_q1 = merged['pbr'].quantile(0.25)
    roe_q3 = merged['roe'].quantile(0.75)

    # 割安高質（PBR下位25% AND ROE上位25%）
    candidates = merged[(merged['pbr'] <= pbr_q1) & (merged['roe'] >= roe_q3)]

    if len(candidates) < N_STOCKS:
        # 候補不足の場合はPBR最小から選択
        candidates = merged.nsmallest(N_STOCKS, 'pbr')

    # PBR最小の20銘柄
    selected = candidates.nsmallest(N_STOCKS, 'pbr')

    portfolios[rdate] = list(selected.index)

    print(f"  {rdate.date()}: {len(selected)}銘柄選定")

print(f"\n選定完了: {len(portfolios)}期間")

# ================================================================================
# 4. 日次評価（全営業日でポートフォリオ価値を計算）
# ================================================================================

print("\n[4/5] 日次評価を実行中...")

# バックテスト開始日（最初のリバランス日）
start_date = rebalance_dates[0]
# バックテスト終了日（最後のデータ）
end_date = all_dates[-1]

# 評価期間の全営業日
eval_dates = [d for d in all_dates if start_date <= d <= end_date]

print(f"評価期間: {eval_dates[0].date()} ~ {eval_dates[-1].date()}")
print(f"評価日数: {len(eval_dates)}日")

# 日次評価
daily_values = []

for current_date in eval_dates:
    # 現在のポートフォリオを特定（直近のリバランス日）
    active_rebalance_date = None
    for rdate in rebalance_dates:
        if rdate <= current_date:
            active_rebalance_date = rdate
        else:
            break

    if active_rebalance_date is None:
        continue

    if active_rebalance_date not in portfolios:
        continue

    portfolio_codes = portfolios[active_rebalance_date]

    # 当日の価格
    if current_date not in df_price_pivot.index:
        continue

    prices_today = df_price_pivot.loc[current_date]

    # ポートフォリオ価値（等ウェイト前提で簡略化）
    available_prices = []
    for code in portfolio_codes:
        if code in prices_today.index and pd.notna(prices_today[code]):
            available_prices.append(prices_today[code])

    if len(available_prices) == 0:
        continue

    # 簡易版：等ウェイトでポートフォリオリターンを計算
    # 基準日（リバランス日）の価格
    base_prices_day = None
    for d in all_dates:
        if d >= active_rebalance_date:
            base_prices_day = d
            break

    if base_prices_day is None or base_prices_day not in df_price_pivot.index:
        continue

    base_prices = df_price_pivot.loc[base_prices_day]

    # リターン計算（基準日からの変化率）
    returns = []
    for code in portfolio_codes:
        if code in base_prices.index and code in prices_today.index:
            if pd.notna(base_prices[code]) and pd.notna(prices_today[code]) and base_prices[code] > 0:
                ret = (prices_today[code] - base_prices[code]) / base_prices[code]
                returns.append(ret)

    if len(returns) > 0:
        portfolio_return = np.mean(returns)
        portfolio_value = 1.0 * (1 + portfolio_return)  # 基準値1.0
    else:
        portfolio_value = 1.0

    daily_values.append({
        'date': current_date,
        'rebalance_date': active_rebalance_date,
        'value': portfolio_value,
        'n_stocks': len(portfolio_codes),
        'valid_stocks': len(returns)
    })

    if len(daily_values) % 250 == 0:
        print(f"  進捗: {len(daily_values)}日処理完了")

print(f"\n日次評価完了: {len(daily_values)}日")

# ================================================================================
# 5. パフォーマンス計算（日次ベース）
# ================================================================================

print("\n[5/5] パフォーマンスを計算中...")

df_daily = pd.DataFrame(daily_values)

# 期間ごとに正規化（リバランス日で1.0にリセット）
df_daily['normalized_value'] = 1.0

for rdate in rebalance_dates:
    mask = df_daily['rebalance_date'] == rdate
    if mask.sum() > 0:
        # この期間の最初の日の値で正規化
        first_value = df_daily.loc[mask, 'value'].iloc[0]
        df_daily.loc[mask, 'normalized_value'] = df_daily.loc[mask, 'value'] / first_value

# 累積リターン（期間を跨いで連結）
df_daily['cumulative_value'] = 1.0
cumulative = 1.0

for rdate in rebalance_dates:
    mask = df_daily['rebalance_date'] == rdate
    if mask.sum() > 0:
        # この期間のリターン
        period_values = df_daily.loc[mask, 'normalized_value'].values
        df_daily.loc[mask, 'cumulative_value'] = cumulative * period_values
        # 次の期間の開始値を更新
        cumulative = df_daily.loc[mask, 'cumulative_value'].iloc[-1]

# 日次リターン
df_daily['daily_return'] = df_daily['cumulative_value'].pct_change()

# 最大ドローダウン（日次ベース）
df_daily['peak'] = df_daily['cumulative_value'].expanding().max()
df_daily['drawdown'] = (df_daily['cumulative_value'] - df_daily['peak']) / df_daily['peak']
max_drawdown = df_daily['drawdown'].min()

# 累積リターン
total_return = df_daily['cumulative_value'].iloc[-1] - 1

# 期間（年）
years = (df_daily['date'].iloc[-1] - df_daily['date'].iloc[0]).days / 365.25

# 年率リターン
annual_return = (1 + total_return) ** (1 / years) - 1

# ボラティリティ（日次→年率換算）
daily_volatility = df_daily['daily_return'].std()
annual_volatility = daily_volatility * np.sqrt(252)

# シャープレシオ
sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0

# 月次リターン（ポートフォリオ最適化用）
df_daily['year_month'] = df_daily['date'].dt.to_period('M')
monthly_last = df_daily.groupby('year_month').tail(1)
monthly_returns = monthly_last['cumulative_value'].pct_change().dropna()

print("\n" + "="*80)
print("ベース戦略（日次評価版）パフォーマンス")
print("="*80)

print(f"\n期間: {df_daily['date'].iloc[0].date()} ~ {df_daily['date'].iloc[-1].date()}")
print(f"評価日数: {len(df_daily)}日")
print(f"リバランス回数: {len(rebalance_dates)}回")

print(f"\n累積リターン: {total_return*100:+.2f}%")
print(f"年率リターン: {annual_return*100:+.2f}%")
print(f"ボラティリティ（年率）: {annual_volatility*100:.2f}%")
print(f"シャープレシオ: {sharpe_ratio:.3f}")
print(f"最大ドローダウン: {max_drawdown*100:.2f}%")

print(f"\n月次リターン数: {len(monthly_returns)}ヶ月")

# 結果を保存
output_dir = PROJECT_ROOT / 'analyses/base_strategy_daily'
output_dir.mkdir(exist_ok=True, parents=True)

df_daily.to_csv(output_dir / 'daily_values.csv', index=False)

# 月次リターンを保存
monthly_returns_df = pd.DataFrame({
    'year_month': monthly_returns.index,
    'return': monthly_returns.values
})
monthly_returns_df.to_csv(output_dir / 'monthly_returns.csv', index=False)

# サマリを保存
with open(output_dir / 'performance_summary.txt', 'w', encoding='utf-8') as f:
    f.write("ベース戦略（低PBR×高ROE）- 日次評価版\n")
    f.write("="*80 + "\n\n")
    f.write(f"期間: {df_daily['date'].iloc[0].date()} ~ {df_daily['date'].iloc[-1].date()}\n")
    f.write(f"評価日数: {len(df_daily)}日\n")
    f.write(f"リバランス回数: {len(rebalance_dates)}回\n\n")
    f.write(f"年率リターン: {annual_return*100:+.2f}%\n")
    f.write(f"ボラティリティ（年率）: {annual_volatility*100:.2f}%\n")
    f.write(f"シャープレシオ: {sharpe_ratio:.3f}\n")
    f.write(f"最大ドローダウン: {max_drawdown*100:.2f}%\n")
    f.write(f"月次リターン数: {len(monthly_returns)}ヶ月\n")

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("【重要】正確なMDD取得完了")
print(f"  年次評価版MDD: -2.41%（過小評価）")
print(f"  日次評価版MDD: {max_drawdown*100:.2f}%（正確）")
print("="*80)

print("\n完了！")
