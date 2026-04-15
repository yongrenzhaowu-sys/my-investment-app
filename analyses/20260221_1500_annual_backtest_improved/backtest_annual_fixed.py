"""
年次リバランス（10月）改善戦略バックテスト - 修正版

【修正内容】
1. 最終ポートフォリオの評価を1年後（または現在の最新日）で実施
2. 日次MDD計算を追加
3. バックテストロジックを簡素化
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("年次リバランス（10月）改善戦略バックテスト - 修正版")
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

# ================================================================================
# 2. リバランス日の設定（10月1日）
# ================================================================================

print("\n[2/5] リバランス日を設定...")

df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

rebalance_dates = []
for year in range(2016, 2026):
    target_date = pd.Timestamp(f'{year}-10-01')
    available_dates = df_price_pivot.index[df_price_pivot.index >= target_date]
    if len(available_dates) > 0:
        rebalance_dates.append(available_dates[0])

rebalance_dates = sorted(rebalance_dates)

print(f"リバランス日数: {len(rebalance_dates)}")
print(f"期間: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}")

# ================================================================================
# 3. 財務データの事前処理
# ================================================================================

print("\n[3/5] 財務データの事前処理...")

fin_by_date = {}
for rdate in rebalance_dates:
    available = df_fin[df_fin['disclosed_date'] <= rdate].copy()
    latest = available.sort_values('disclosed_date').groupby('code').tail(1)
    latest = latest.set_index('code')[['bps', 'roe']]
    fin_by_date[rdate] = latest

print("財務データ事前処理完了")

# ================================================================================
# 4. バックテスト実行（ベースラインのみ）
# ================================================================================

print("\n[4/5] バックテストを実行（ベースライン：低PBR × 高ROE）...")

INITIAL_CASH = 10_000_000
N_STOCKS = 20
TAX_RATE = 0.20315
UNIT = 100

cash = INITIAL_CASH
portfolio = {}
annual_realized_pnl = 0
current_year = None
results = []

for i in range(len(rebalance_dates) - 1):  # legacy版に合わせて最後を除外
    rebalance_date = rebalance_dates[i]
    next_rebalance_date = rebalance_dates[i + 1]

    print(f"  {rebalance_date.date()}")

    # 年の切り替わり（税金処理）
    if current_year != rebalance_date.year:
        if current_year is not None and annual_realized_pnl > 0:
            tax = annual_realized_pnl * TAX_RATE
            cash -= tax
        annual_realized_pnl = 0
        current_year = rebalance_date.year

    # 既存ポートフォリオを売却
    sell_value = 0
    if len(portfolio) > 0:
        for code, position in portfolio.items():
            if code in df_price_pivot.columns and rebalance_date in df_price_pivot.index:
                sell_price = df_price_pivot.loc[rebalance_date, code]
                if pd.notna(sell_price):
                    sell_amount = position['shares'] * sell_price
                    sell_value += sell_amount
                    pnl = (sell_price - position['buy_price']) * position['shares']
                    annual_realized_pnl += pnl

    cash += sell_value
    portfolio = {}

    # 銘柄選定
    if rebalance_date not in df_price_pivot.index:
        continue

    prices = df_price_pivot.loc[rebalance_date].dropna()
    fin = fin_by_date[rebalance_date]

    merged = pd.DataFrame({
        'adjusted_close': prices,
        'bps': fin['bps'],
        'roe': fin['roe']
    }).dropna()

    if len(merged) < N_STOCKS:
        continue

    # PBR計算
    merged['pbr'] = merged['adjusted_close'] / merged['bps']
    merged = merged[(merged['pbr'] > 0) & (merged['pbr'] < 50)]

    if len(merged) < N_STOCKS:
        continue

    # 四分位
    pbr_q1 = merged['pbr'].quantile(0.25)
    roe_q3 = merged['roe'].quantile(0.75)

    # 割安高質
    candidates = merged[(merged['pbr'] <= pbr_q1) & (merged['roe'] >= roe_q3)]

    if len(candidates) < N_STOCKS:
        candidates = merged.nsmallest(N_STOCKS, 'pbr')

    selected = candidates.nsmallest(N_STOCKS, 'pbr')

    # 購入
    target_per_stock = cash / len(selected)
    total_invested = 0

    for code in selected.index:
        price = selected.loc[code, 'adjusted_close']
        shares = int(target_per_stock / (price * UNIT)) * UNIT

        if shares > 0:
            invest_amount = shares * price
            total_invested += invest_amount
            portfolio[code] = {'shares': shares, 'buy_price': price}

    cash -= total_invested

    results.append({
        'date': rebalance_date,
        'cash': cash,
        'invested': total_invested,
        'n_stocks': len(portfolio),
        'portfolio': portfolio.copy()
    })

# 最終税金
if annual_realized_pnl > 0:
    tax = annual_realized_pnl * TAX_RATE
    cash -= tax

# 【重要】最終ポートフォリオを最新の営業日で評価
final_eval_date = df_price_pivot.index.max()
final_portfolio_value = 0

print(f"\n最終リバランス日: {results[-1]['date'].date()}")
print(f"最終評価日: {final_eval_date.date()}")

if len(portfolio) > 0:
    for code, position in portfolio.items():
        if code in df_price_pivot.columns:
            final_price = df_price_pivot.loc[final_eval_date, code]
            if pd.notna(final_price):
                final_portfolio_value += position['shares'] * final_price

print(f"最終保有株式時価: {final_portfolio_value:,.0f}円")
print(f"最終現金（税引後）: {cash:,.0f}円")

# 結果DataFrameに追加
df_results = pd.DataFrame(results)
df_results['total_value'] = df_results['cash'] + df_results['invested']

# 最終行の invested を更新
df_results.loc[len(df_results)-1, 'invested'] = final_portfolio_value
df_results.loc[len(df_results)-1, 'cash'] = cash
df_results.loc[len(df_results)-1, 'total_value'] = cash + final_portfolio_value

# ================================================================================
# 5. パフォーマンス分析
# ================================================================================

print("\n[5/5] パフォーマンス分析...")

df_results['return'] = df_results['total_value'].pct_change()
df_results['cumulative_return'] = (1 + df_results['return']).cumprod() - 1

# 年率リターン
total_return = df_results['cumulative_return'].iloc[-1]
years = (df_results['date'].iloc[-1] - df_results['date'].iloc[0]).days / 365.25
annual_return = (1 + total_return) ** (1 / years) - 1

# MDD
df_results['peak'] = df_results['total_value'].cummax()
df_results['drawdown'] = (df_results['total_value'] - df_results['peak']) / df_results['peak']
max_drawdown = df_results['drawdown'].min()

# シャープレシオ
volatility = df_results['return'].std() * np.sqrt(1)
sharpe_ratio = (annual_return - 0.03) / volatility if volatility > 0 else 0

print("\n" + "="*80)
print("【年次リバランス結果】")
print("="*80)
print(f"\n期間: {df_results['date'].iloc[0].date()} ~ {df_results['date'].iloc[-1].date()}")
print(f"初期資本: {INITIAL_CASH:,}円")
print(f"最終資産: {df_results['total_value'].iloc[-1]:,.0f}円")
print(f"総リターン: {total_return*100:.2f}%")
print(f"年率リターン: {annual_return*100:.2f}%")
print(f"シャープレシオ: {sharpe_ratio:.2f}")
print(f"最大DD: {max_drawdown*100:.2f}%")
print(f"勝率: {(df_results['return'] > 0).sum() / len(df_results['return'])*100:.1f}%")

# ================================================================================
# 6. 日次MDD計算
# ================================================================================

print("\n日次MDD計算を開始...")

# 全営業日を取得
all_dates = sorted(df_price_pivot.index[(df_price_pivot.index >= rebalance_dates[0]) &
                                         (df_price_pivot.index <= final_eval_date)])

daily_values = []

for date in all_dates:
    # この日時点での保有ポートフォリオを特定
    current_portfolio = None
    current_cash = INITIAL_CASH

    for result in results:
        if result['date'] <= date:
            current_portfolio = result['portfolio']
            current_cash = result['cash']

    if current_portfolio is None:
        continue

    # 保有株式の時価評価
    portfolio_value = 0
    for code, position in current_portfolio.items():
        if code in df_price_pivot.columns and date in df_price_pivot.index:
            price = df_price_pivot.loc[date, code]
            if pd.notna(price):
                portfolio_value += position['shares'] * price

    total_value = current_cash + portfolio_value
    daily_values.append({'date': date, 'total_value': total_value})

df_daily = pd.DataFrame(daily_values)
df_daily['peak'] = df_daily['total_value'].cummax()
df_daily['drawdown'] = (df_daily['total_value'] - df_daily['peak']) / df_daily['peak']

max_dd_daily = df_daily['drawdown'].min()
max_dd_date = df_daily.loc[df_daily['drawdown'].idxmin(), 'date']

print(f"日次最大DD: {max_dd_daily*100:.2f}% ({max_dd_date.date()})")

# 保存
output_dir = PROJECT_ROOT / 'analyses' / '20260221_1500_annual_backtest_improved'
output_dir.mkdir(exist_ok=True, parents=True)

df_results.to_csv(output_dir / 'annual_results.csv', index=False, encoding='utf-8-sig')
df_daily.to_csv(output_dir / 'daily_results.csv', index=False, encoding='utf-8-sig')

with open(output_dir / 'summary_fixed.txt', 'w', encoding='utf-8') as f:
    f.write("年次リバランス（10月）バックテスト - 修正版\n")
    f.write("="*80 + "\n\n")
    f.write(f"期間: {df_results['date'].iloc[0].date()} ~ {df_results['date'].iloc[-1].date()}\n")
    f.write(f"初期資本: {INITIAL_CASH:,}円\n")
    f.write(f"最終資産: {df_results['total_value'].iloc[-1]:,.0f}円\n\n")
    f.write(f"年率リターン: {annual_return*100:.2f}%\n")
    f.write(f"シャープレシオ: {sharpe_ratio:.2f}\n")
    f.write(f"最大DD（年次）: {max_drawdown*100:.2f}%\n")
    f.write(f"最大DD（日次）: {max_dd_daily*100:.2f}%\n")
    f.write(f"勝率: {(df_results['return'] > 0).sum() / len(df_results['return'])*100:.1f}%\n")

print(f"\n保存先: {output_dir}")
print("\n" + "="*80)
print("Legacy版（年率+28.52%）との比較:")
print(f"  今回: 年率{annual_return*100:+.2f}%")
print("  差分: {:.2f}%pt".format(annual_return*100 - 28.52))
print("="*80)

print("\n完了！")
