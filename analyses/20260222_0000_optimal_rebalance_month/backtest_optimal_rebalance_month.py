# -*- coding: utf-8 -*-
"""
理論株価×モメンタム複合戦略 - 最適リバランス月の特定

12ヶ月全てをリバランス月として設定し、パフォーマンスを比較
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import io

# 標準出力をUTF-8に設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("理論株価×モメンタム複合戦略 - 最適リバランス月の特定")
print("="*80)

# ================================================================================
# データ読み込み
# ================================================================================

print("\n[1/3] データ読み込み...")

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

# ================================================================================
# バックテスト関数
# ================================================================================

def run_backtest(rebalance_month, df_price, df_fin, df_scores):
    """
    指定された月でリバランスするバックテストを実行

    Parameters:
    - rebalance_month: 1-12（1=1月、12=12月）
    """

    INITIAL_CAPITAL = 10_000_000
    N_STOCKS = 20
    TAX_RATE = 0.20315
    UNIT = 100

    # リバランス日の設定
    df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

    rebalance_dates = []
    for year in range(2016, 2026):  # 2016年スタート（元スクリプトと同じ）
        target_date = pd.Timestamp(f'{year}-{rebalance_month:02d}-01')
        available_dates = df_price_pivot.index[df_price_pivot.index >= target_date]
        if len(available_dates) > 0:
            rebalance_dates.append(available_dates[0])

    rebalance_dates = sorted(rebalance_dates)

    print(f"  リバランス日数: {len(rebalance_dates)}")
    if len(rebalance_dates) > 0:
        print(f"  期間: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}")

    # 財務・スコアデータの事前処理
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

    # バックテスト実行
    cash = INITIAL_CAPITAL
    portfolio = {}
    results = []
    annual_realized_pnl = 0
    current_year = None

    for i in range(len(rebalance_dates) - 1):
        start_date = rebalance_dates[i]
        end_date = rebalance_dates[i + 1]

        # 既存ポートフォリオを売却
        if len(portfolio) > 0:
            sell_prices_df = df_price[
                (df_price['date'] >= start_date) &
                (df_price['date'] <= start_date + pd.Timedelta(days=5))
            ].copy()

            if len(sell_prices_df) > 0:
                sell_prices_df = sell_prices_df.sort_values(['code', 'date']).groupby('code').first()
                sell_prices = sell_prices_df['adjusted_close']

                realized_pnl = 0
                for code, position in portfolio.items():
                    if code in sell_prices.index:
                        sell_price = sell_prices.loc[code]
                        if pd.notna(sell_price):
                            pnl = (sell_price - position['buy_price']) * position['shares']
                            realized_pnl += pnl

                # 税金計算（年度ごと）
                year = start_date.year
                if year != current_year:
                    if annual_realized_pnl > 0:
                        tax = annual_realized_pnl * TAX_RATE
                        cash -= tax
                    annual_realized_pnl = 0
                    current_year = year

                annual_realized_pnl += realized_pnl
                cash += realized_pnl

        portfolio = {}

        # 銘柄選定
        start_prices_df = df_price[
            (df_price['date'] >= start_date) &
            (df_price['date'] <= start_date + pd.Timedelta(days=5))
        ].copy()

        if len(start_prices_df) == 0:
            continue

        start_prices_df = start_prices_df.sort_values(['code', 'date']).groupby('code').first()
        prices = start_prices_df['adjusted_close'].dropna()
        fin = fin_by_date[start_date]
        scores = scores_by_date.get(start_date, pd.DataFrame())

        if len(scores) == 0:
            continue

        merged = pd.DataFrame({
            'adjusted_close': prices,
            'eps': fin['eps'],
            'custom_growth_rate': scores['custom_growth_rate'],
            'return_6M': scores['return_6M'],
            'quarterly_per': scores['quarterly_per']
        }).dropna()

        if len(merged) < N_STOCKS:
            continue

        # 理論株価計算
        merged['next_eps'] = merged['eps'] * (1 + merged['custom_growth_rate'])
        merged['theoretical_price'] = merged['next_eps'] * merged['quarterly_per']
        merged['divergence'] = (merged['theoretical_price'] - merged['adjusted_close']) / merged['adjusted_close']
        merged = merged[(merged['divergence'] > -0.5) & (merged['divergence'] < 2.0)]

        if len(merged) < N_STOCKS:
            continue

        undervalued = merged[merged['divergence'] > 0].copy()
        if len(undervalued) < N_STOCKS:
            divergence_median = merged['divergence'].median()
            undervalued = merged[merged['divergence'] >= divergence_median].copy()

        selected = undervalued.nlargest(N_STOCKS, 'return_6M')

        # ポートフォリオ構築（元のスクリプトと同じロジック）
        target_per_stock = cash / len(selected)  # 全額投資
        total_invested = 0

        for code in selected.index:
            price = selected.loc[code, 'adjusted_close']

            if pd.notna(price) and price > 0:
                shares = int(target_per_stock / (price * UNIT)) * UNIT

                if shares > 0:
                    invest_amount = shares * price
                    if invest_amount <= cash - total_invested:
                        portfolio[code] = {'shares': shares, 'buy_price': price}
                        total_invested += invest_amount

        cash -= total_invested
        invested = total_invested
        valid_stocks = len(portfolio)

        # ポートフォリオ評価
        eval_prices_df = df_price[
            (df_price['date'] >= end_date) &
            (df_price['date'] <= end_date + pd.Timedelta(days=5))
        ].copy()

        if len(eval_prices_df) > 0:
            eval_prices_df = eval_prices_df.sort_values(['code', 'date']).groupby('code').first()
            eval_prices = eval_prices_df['adjusted_close']

            portfolio_value = 0
            for code, position in portfolio.items():
                if code in eval_prices.index:
                    eval_price = eval_prices.loc[code]
                    if pd.notna(eval_price):
                        portfolio_value += position['shares'] * eval_price

            total_value = cash + portfolio_value

            if len(results) == 0:
                period_return = (total_value - INITIAL_CAPITAL) / INITIAL_CAPITAL
                cumulative_return = period_return
            else:
                prev_total = results[-1]['total_value']
                period_return = (total_value - prev_total) / prev_total
                cumulative_return = (total_value - INITIAL_CAPITAL) / INITIAL_CAPITAL

            results.append({
                'start_date': start_date,
                'end_date': end_date,
                'cash': cash,
                'portfolio_value': portfolio_value,
                'total_value': total_value,
                'invested': invested,
                'n_stocks': len(selected),
                'valid_stocks': valid_stocks,
                'return': period_return,
                'cumulative_return': cumulative_return
            })

    # 最終税金処理
    if annual_realized_pnl > 0:
        tax = annual_realized_pnl * TAX_RATE
        cash -= tax

    # 結果の集計
    if len(results) > 0:
        df_results = pd.DataFrame(results)

        df_results['peak'] = df_results['total_value'].cummax()
        df_results['drawdown'] = (df_results['total_value'] - df_results['peak']) / df_results['peak']

        final_value = df_results['total_value'].iloc[-1]
        total_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL
        n_periods = len(df_results)
        n_years = n_periods

        annual_return = (1 + total_return) ** (1 / n_years) - 1

        period_returns = df_results['return']
        sharpe_ratio = period_returns.mean() / period_returns.std() if period_returns.std() > 0 else 0

        max_dd = df_results['drawdown'].min()
        win_rate = (period_returns > 0).mean()

        first_date = df_results['start_date'].iloc[0]
        last_date = df_results['end_date'].iloc[-1]

        return {
            'rebalance_month': rebalance_month,
            'n_periods': n_periods,
            'n_years': n_years,
            'first_date': first_date,
            'last_date': last_date,
            'initial_capital': INITIAL_CAPITAL,
            'final_value': final_value,
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe_ratio,
            'max_dd': max_dd,
            'win_rate': win_rate,
            'avg_return': period_returns.mean(),
            'std_return': period_returns.std()
        }
    else:
        return None

# ================================================================================
# 全12ヶ月のバックテスト実行
# ================================================================================

print("\n[2/3] 全12ヶ月のバックテスト実行...")

month_names = ['1月', '2月', '3月', '4月', '5月', '6月',
               '7月', '8月', '9月', '10月', '11月', '12月']

all_results = []

for month in range(1, 13):
    print(f"\n{month_names[month-1]}リバランスを実行中...")
    result = run_backtest(month, df_price, df_fin, df_scores)

    if result:
        result['month_name'] = month_names[month-1]
        all_results.append(result)
        print(f"  年率: {result['annual_return']*100:+.2f}%, シャープ: {result['sharpe_ratio']:.2f}, MDD: {result['max_dd']*100:.2f}%")
        print(f"  期間: {result['first_date'].date()} ~ {result['last_date'].date()}, リバランス回数: {result['n_periods']}")
    else:
        print(f"  失敗（データ不足）")

# ================================================================================
# 結果の比較
# ================================================================================

print("\n" + "="*80)
print("[3/3] 結果の比較")
print("="*80)

df_comparison = pd.DataFrame(all_results)

# ランキング表
print("\n【年率リターン順】")
df_sorted_return = df_comparison.sort_values('annual_return', ascending=False)
for idx, row in df_sorted_return.iterrows():
    print(f"{row['month_name']:>4s}: {row['annual_return']*100:+6.2f}%  (シャープ: {row['sharpe_ratio']:5.2f}, MDD: {row['max_dd']*100:6.2f}%)")

print("\n【シャープレシオ順】")
df_sorted_sharpe = df_comparison.sort_values('sharpe_ratio', ascending=False)
for idx, row in df_sorted_sharpe.iterrows():
    print(f"{row['month_name']:>4s}: {row['sharpe_ratio']:5.2f}  (年率: {row['annual_return']*100:+6.2f}%, MDD: {row['max_dd']*100:6.2f}%)")

print("\n【最大DD（小さい順）】")
df_sorted_mdd = df_comparison.sort_values('max_dd', ascending=False)
for idx, row in df_sorted_mdd.iterrows():
    print(f"{row['month_name']:>4s}: {row['max_dd']*100:6.2f}%  (年率: {row['annual_return']*100:+6.2f}%, シャープ: {row['sharpe_ratio']:5.2f})")

# 統計サマリー
print("\n【統計サマリー】")
print(f"平均年率リターン: {df_comparison['annual_return'].mean()*100:.2f}%")
print(f"標準偏差: {df_comparison['annual_return'].std()*100:.2f}%")
print(f"最大: {df_comparison['annual_return'].max()*100:.2f}% ({df_comparison.loc[df_comparison['annual_return'].idxmax(), 'month_name']})")
print(f"最小: {df_comparison['annual_return'].min()*100:.2f}% ({df_comparison.loc[df_comparison['annual_return'].idxmin(), 'month_name']})")

# 最適月の推奨
best_return_month = df_comparison.loc[df_comparison['annual_return'].idxmax(), 'month_name']
best_sharpe_month = df_comparison.loc[df_comparison['sharpe_ratio'].idxmax(), 'month_name']
best_mdd_month = df_comparison.loc[df_comparison['max_dd'].idxmax(), 'month_name']

print("\n【最適月の推奨】")
print(f"リターン重視: {best_return_month} (年率{df_comparison['annual_return'].max()*100:.2f}%)")
print(f"リスク調整後重視: {best_sharpe_month} (シャープ{df_comparison['sharpe_ratio'].max():.2f})")
print(f"安定性重視: {best_mdd_month} (MDD{df_comparison['max_dd'].max()*100:.2f}%)")

# 結果保存
output_dir = PROJECT_ROOT / 'analyses' / '20260222_0000_optimal_rebalance_month'
df_comparison.to_csv(output_dir / 'comparison_summary.csv', index=False, encoding='utf-8-sig')

with open(output_dir / 'optimal_month_summary.txt', 'w', encoding='utf-8') as f:
    f.write("="*80 + "\n")
    f.write("理論株価×モメンタム複合戦略 - 最適リバランス月\n")
    f.write("="*80 + "\n\n")
    f.write("【年率リターン順】\n")
    for idx, row in df_sorted_return.iterrows():
        f.write(f"{row['month_name']:>4s}: {row['annual_return']*100:+6.2f}%  (シャープ: {row['sharpe_ratio']:5.2f}, MDD: {row['max_dd']*100:6.2f}%)\n")
    f.write("\n【最適月の推奨】\n")
    f.write(f"リターン重視: {best_return_month} (年率{df_comparison['annual_return'].max()*100:.2f}%)\n")
    f.write(f"リスク調整後重視: {best_sharpe_month} (シャープ{df_comparison['sharpe_ratio'].max():.2f})\n")
    f.write(f"安定性重視: {best_mdd_month} (MDD{df_comparison['max_dd'].max()*100:.2f}%)\n")

print(f"\n結果を保存: {output_dir / 'comparison_summary.csv'}")
print("完了!")
