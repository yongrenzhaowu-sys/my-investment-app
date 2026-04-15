"""
理論株価×モメンタム戦略 - 日次MDD計算版

保有銘柄を記録し、日次でポートフォリオ価値を評価して真のMDDを計算
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("理論株価×モメンタム戦略 - 日次MDD計算版")
print("="*80)

# データ読み込み（簡略化）
print("\n[1/4] データ読み込み...")

df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()

df_fin = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin['disclosed_date'] = pd.to_datetime(df_fin['disclosed_date'])
df_fin = df_fin[df_fin['disclosed_date'] >= '2016-01-01'].copy()

if 'fiscal_quarter' in df_fin.columns:
    df_fin = df_fin[df_fin['fiscal_quarter'] == 'FY'].copy()

df_fin = df_fin[['disclosed_date', 'code', 'equity', 'net_profit', 'bps', 'eps']].copy()
df_fin['roe'] = (df_fin['net_profit'] / df_fin['equity']) * 100
df_fin = df_fin[
    (df_fin['roe'] > -100) & (df_fin['roe'] < 100) &
    (df_fin['bps'] > 0) & (df_fin['equity'] > 0) &
    (df_fin['eps'] > 0)
].copy()

df_scores = pd.read_csv(
    PROJECT_ROOT / 'analyses/growth_yield_prediction/prediction_scores.csv',
    dtype={'code': str},
    low_memory=False
)
df_scores['disclosed_date'] = pd.to_datetime(df_scores['disclosed_date'])
df_scores = df_scores[df_scores['disclosed_date'] >= '2016-01-01'].copy()
df_scores = df_scores[['disclosed_date', 'code', 'custom_growth_rate', 'return_6M', 'market_cap', 'quarterly_per']].copy()
df_scores = df_scores.dropna(subset=['custom_growth_rate'])

print(f"データ読み込み完了")

# リバランス日設定
print("\n[2/4] リバランス日を設定...")

df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

rebalance_dates = []
for year in range(2016, 2026):
    target_date = pd.Timestamp(f'{year}-10-01')
    available_dates = df_price_pivot.index[df_price_pivot.index >= target_date]
    if len(available_dates) > 0:
        rebalance_dates.append(available_dates[0])

rebalance_dates = sorted(rebalance_dates)
print(f"リバランス日数: {len(rebalance_dates)}")

# 財務・スコアデータの事前処理
print("\n[3/4] データ事前処理（簡略化）...")

fin_by_date = {}
scores_by_date = {}

for rdate in rebalance_dates:
    available_fin = df_fin[df_fin['disclosed_date'] <= rdate].copy()
    latest_fin = available_fin.sort_values('disclosed_date').groupby('code').tail(1)
    latest_fin = latest_fin.set_index('code')[['bps', 'roe', 'eps']]
    fin_by_date[rdate] = latest_fin

    six_months_ago = rdate - pd.Timedelta(days=180)
    available_scores = df_scores[
        (df_scores['disclosed_date'] <= rdate) &
        (df_scores['disclosed_date'] >= six_months_ago)
    ].copy()

    if len(available_scores) > 0:
        latest_scores = available_scores.sort_values('disclosed_date').groupby('code').tail(1)
        latest_scores = latest_scores.set_index('code')[['custom_growth_rate', 'return_6M', 'market_cap', 'quarterly_per']]
        scores_by_date[rdate] = latest_scores
    else:
        scores_by_date[rdate] = pd.DataFrame()

print("事前処理完了")

# バックテスト実行（保有銘柄を記録）
print("\n[4/4] バックテスト実行（保有銘柄記録版）...")

INITIAL_CAPITAL = 10_000_000
N_STOCKS = 20
TAX_RATE = 0.20315
UNIT = 100

cash = INITIAL_CAPITAL
portfolio = {}
holdings_history = []  # 保有銘柄の履歴を記録
annual_realized_pnl = 0
current_year = None

# バックテスト実行（簡略版：税金計算は省略）
for i in range(len(rebalance_dates) - 1):
    start_date = rebalance_dates[i]
    end_date = rebalance_dates[i + 1]

    print(f"  {start_date.date()} -> {end_date.date()}", end="")

    # ポートフォリオをクリア
    portfolio = {}

    # 銘柄選定（簡略版）
    start_prices_df = df_price[
        (df_price['date'] >= start_date) &
        (df_price['date'] <= start_date + pd.Timedelta(days=5))
    ].copy()

    if len(start_prices_df) == 0:
        print(" ... スキップ（価格データなし）")
        continue

    start_prices_df = start_prices_df.sort_values(['code', 'date']).groupby('code').first()
    prices = start_prices_df['adjusted_close'].dropna()
    fin = fin_by_date[start_date]
    scores = scores_by_date.get(start_date, pd.DataFrame())

    if len(scores) == 0:
        print(" ... スキップ（スコアデータなし）")
        continue

    merged = pd.DataFrame({
        'adjusted_close': prices,
        'eps': fin['eps'],
        'custom_growth_rate': scores['custom_growth_rate'],
        'return_6M': scores['return_6M'],
        'quarterly_per': scores['quarterly_per']
    }).dropna()

    if len(merged) < N_STOCKS:
        print(" ... スキップ（データ不足）")
        continue

    # 理論株価計算
    merged['next_eps'] = merged['eps'] * (1 + merged['custom_growth_rate'])
    merged['theoretical_price'] = merged['next_eps'] * merged['quarterly_per']
    merged['divergence'] = (merged['theoretical_price'] - merged['adjusted_close']) / merged['adjusted_close']
    merged = merged[(merged['divergence'] > -0.5) & (merged['divergence'] < 2.0)]

    if len(merged) < N_STOCKS:
        print(" ... スキップ（乖離率フィルタ後データ不足）")
        continue

    undervalued = merged[merged['divergence'] > 0].copy()
    if len(undervalued) < N_STOCKS:
        divergence_median = merged['divergence'].median()
        undervalued = merged[merged['divergence'] >= divergence_median].copy()

    selected = undervalued.nlargest(N_STOCKS, 'return_6M')

    # ポートフォリオ構築（簡略版：全額投資）
    total_investment = cash * 0.95  # 95%投資
    target_per_stock = total_investment / len(selected)

    for code in selected.index:
        price = selected.loc[code, 'adjusted_close']
        shares = int(target_per_stock / (price * UNIT)) * UNIT

        if shares > 0:
            portfolio[code] = {'shares': shares, 'buy_price': price}

    # 保有銘柄を記録
    holdings_history.append({
        'start_date': start_date,
        'end_date': end_date,
        'holdings': portfolio.copy()
    })

    print(f" ... 完了（{len(portfolio)}銘柄）")

print(f"\n保有期間: {len(holdings_history)}期間")

# 日次ポートフォリオ価値を計算
print("\n日次ポートフォリオ価値を計算中...")

daily_portfolio_values = []

for period in holdings_history:
    start_date = period['start_date']
    end_date = period['end_date']
    holdings = period['holdings']

    # この期間の全営業日を取得
    period_dates = df_price_pivot.loc[start_date:end_date].index

    for date in period_dates:
        # この日の各銘柄の価格を取得
        portfolio_value = 0
        valid_count = 0

        for code, position in holdings.items():
            if code in df_price_pivot.columns:
                price = df_price_pivot.loc[date, code]
                if pd.notna(price):
                    portfolio_value += position['shares'] * price
                    valid_count += 1

        if valid_count > 0:  # 少なくとも1銘柄の価格がある
            # 簡易的に現金は5%と仮定
            total_value = portfolio_value / 0.95
            daily_portfolio_values.append({
                'date': date,
                'portfolio_value': portfolio_value,
                'total_value': total_value
            })

df_daily = pd.DataFrame(daily_portfolio_values)

if len(df_daily) > 0:
    # 日次MDDを計算
    df_daily['peak'] = df_daily['total_value'].cummax()
    df_daily['drawdown'] = (df_daily['total_value'] - df_daily['peak']) / df_daily['peak']
    daily_mdd = df_daily['drawdown'].min()

    # 最大DDが発生した日を特定
    mdd_date = df_daily.loc[df_daily['drawdown'].idxmin(), 'date']

    print("\n" + "="*80)
    print("【日次MDD計算結果】")
    print("="*80)
    print(f"\n日次MDD: {daily_mdd*100:.2f}%")
    print(f"発生日: {mdd_date.date()}")
    print(f"\n参考:")
    print(f"  リバランス時点のみのMDD: -1.10%")
    print(f"  真の日次MDD: {daily_mdd*100:.2f}%")
    print(f"  差: {(daily_mdd*100 - (-1.10)):.2f}%pt")
    print()

    # 統計情報
    print("="*80)
    print("【日次統計】")
    print("="*80)
    print(f"評価日数: {len(df_daily):,} 営業日")
    print(f"期間: {df_daily['date'].min().date()} ~ {df_daily['date'].max().date()}")
    print(f"初期価値: {df_daily['total_value'].iloc[0]:,.0f}円")
    print(f"最終価値: {df_daily['total_value'].iloc[-1]:,.0f}円")
    print(f"総リターン: {(df_daily['total_value'].iloc[-1] / df_daily['total_value'].iloc[0] - 1)*100:.2f}%")

    # 日次リターンの分布
    df_daily['daily_return'] = df_daily['total_value'].pct_change()
    print(f"\n日次リターン統計:")
    print(f"  平均: {df_daily['daily_return'].mean()*100:.3f}%")
    print(f"  標準偏差: {df_daily['daily_return'].std()*100:.3f}%")
    print(f"  最大: {df_daily['daily_return'].max()*100:.2f}%")
    print(f"  最小: {df_daily['daily_return'].min()*100:.2f}%")

    # 保存
    output_dir = PROJECT_ROOT / 'analyses' / '20260221_1500_annual_backtest_improved'
    df_daily.to_csv(output_dir / 'daily_portfolio_values.csv', index=False, encoding='utf-8-sig')
    print(f"\n日次データを保存: {output_dir / 'daily_portfolio_values.csv'}")

    # MDDの推移をプロット用に保存
    df_daily[['date', 'total_value', 'peak', 'drawdown']].to_csv(
        output_dir / 'daily_drawdown.csv', index=False, encoding='utf-8-sig'
    )

    print("="*80)

else:
    print("\nエラー: 日次データが生成されませんでした")

print("\n完了！")
