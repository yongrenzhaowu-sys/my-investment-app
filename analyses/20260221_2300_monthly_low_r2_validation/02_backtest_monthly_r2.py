# -*- coding: utf-8 -*-
"""
月足最安値R2戦略のバックテスト

戦略:
- 毎月月初にリバランス
- 過去3ヶ月の月足最安値でR2 >= 0.98の銘柄を選択
- 上位20銘柄に均等配分
- 1ヶ月保有
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
print("月足最安値R2戦略のバックテスト")
print("="*80)

# ================================================================================
# パラメータ
# ================================================================================

INITIAL_CAPITAL = 10_000_000
N_STOCKS = 20
R2_THRESHOLD = 0.98
TAX_RATE = 0.20315
UNIT = 100

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/4] データ読み込み...")

df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()

# 月次最安値の集計
df_price['year_month'] = df_price['date'].dt.to_period('M')

df_monthly_low = df_price.groupby(['code', 'year_month']).agg({
    'low': 'min',
    'adjusted_close': 'last'
}).reset_index()

df_monthly_low = df_monthly_low.sort_values(['code', 'year_month'])

print(f"月次データ: {len(df_monthly_low):,} 行")

# ================================================================================
# 2. R2を事前計算
# ================================================================================

print("\n[2/4] R2を事前計算...")

# R2計算結果を読み込み（既に計算済み）
df_r2 = pd.read_csv(
    PROJECT_ROOT / 'analyses/20260221_2300_monthly_low_r2_validation/r2_analysis_results.csv',
    dtype={'code': str}
)
df_r2['year_month'] = pd.to_datetime(df_r2['year_month']).dt.to_period('M')

print(f"R2データ: {len(df_r2):,} 行")

# ================================================================================
# 3. リバランス日の設定
# ================================================================================

print("\n[3/4] リバランス日を設定...")

# 月次リバランス（各月の最初の営業日）
all_dates = pd.Series(sorted(df_price['date'].unique()))

rebalance_dates = []
for year_month in df_r2['year_month'].unique():
    # その月の最初の営業日を取得
    month_start = year_month.to_timestamp()
    available_dates = all_dates[all_dates >= month_start]

    if len(available_dates) > 0:
        rebalance_dates.append(available_dates.iloc[0])

rebalance_dates = sorted(rebalance_dates)

# バックテスト期間: 2016年4月～2025年12月（過去3ヶ月データが必要）
rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp('2016-04-01')]

print(f"リバランス日数: {len(rebalance_dates)}")

# ================================================================================
# 4. バックテスト実行
# ================================================================================

print("\n[4/4] バックテスト実行...")

cash = INITIAL_CAPITAL
portfolio = {}
results = []

for i in range(len(rebalance_dates) - 1):
    start_date = rebalance_dates[i]
    end_date = rebalance_dates[i + 1]

    year_month = pd.Period(start_date, freq='M')

    print(f"  {start_date.date()} -> {end_date.date()}", end="")

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

            # 税金計算（利益のみ課税）
            if realized_pnl > 0:
                tax = realized_pnl * TAX_RATE
                cash += realized_pnl - tax
            else:
                cash += realized_pnl

    # ポートフォリオをクリア
    portfolio = {}

    # R2 >= 0.98の銘柄を抽出
    prev_month = year_month - 1
    r2_data = df_r2[df_r2['year_month'] == prev_month].copy()

    if len(r2_data) == 0:
        print(" ... スキップ（R2データなし）")
        continue

    high_r2 = r2_data[r2_data['r_squared'] >= R2_THRESHOLD].copy()

    if len(high_r2) < N_STOCKS:
        print(f" ... スキップ（該当銘柄{len(high_r2)}件のみ）")
        continue

    # slope（傾き）の大きい順に上位20銘柄を選択
    selected = high_r2.nlargest(N_STOCKS, 'slope')

    # 購入価格を取得
    buy_prices_df = df_price[
        (df_price['date'] >= start_date) &
        (df_price['date'] <= start_date + pd.Timedelta(days=5))
    ].copy()

    if len(buy_prices_df) == 0:
        print(" ... スキップ（価格データなし）")
        continue

    buy_prices_df = buy_prices_df.sort_values(['code', 'date']).groupby('code').first()
    buy_prices = buy_prices_df['adjusted_close']

    # ポートフォリオ構築
    total_investment = cash * 0.95
    target_per_stock = total_investment / len(selected)

    invested = 0
    valid_stocks = 0

    for code in selected['code']:
        if code in buy_prices.index:
            price = buy_prices.loc[code]

            if pd.notna(price) and price > 0:
                shares = int(target_per_stock / (price * UNIT)) * UNIT

                if shares > 0:
                    cost = shares * price
                    if cost <= cash:
                        portfolio[code] = {'shares': shares, 'buy_price': price}
                        cash -= cost
                        invested += cost
                        valid_stocks += 1

    # ポートフォリオ評価（月末時点）
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

        # リターン計算
        if i == 0:
            period_return = (total_value - INITIAL_CAPITAL) / INITIAL_CAPITAL
        else:
            prev_total = results[-1]['total_value']
            period_return = (total_value - prev_total) / prev_total

        results.append({
            'start_date': start_date,
            'end_date': end_date,
            'cash': cash,
            'portfolio_value': portfolio_value,
            'total_value': total_value,
            'invested': invested,
            'n_stocks': len(selected),
            'valid_stocks': valid_stocks,
            'return': period_return
        })

        print(f" ... リターン: {period_return*100:+.2f}% (銘柄数: {valid_stocks})")
    else:
        print(" ... スキップ（評価価格なし）")

# ================================================================================
# 結果の分析
# ================================================================================

print("\n" + "="*80)
print("バックテスト結果")
print("="*80)

if len(results) > 0:
    df_results = pd.DataFrame(results)

    # 累積リターンの計算
    df_results['cumulative_return'] = (1 + df_results['return']).cumprod() - 1

    # ピークとドローダウン
    df_results['peak'] = df_results['total_value'].cummax()
    df_results['drawdown'] = (df_results['total_value'] - df_results['peak']) / df_results['peak']

    # 最終成績
    final_value = df_results['total_value'].iloc[-1]
    total_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL
    n_months = len(df_results)
    n_years = n_months / 12

    # 年率リターン
    annual_return = (1 + total_return) ** (1 / n_years) - 1

    # シャープレシオ
    monthly_returns = df_results['return']
    sharpe_ratio = monthly_returns.mean() / monthly_returns.std() * np.sqrt(12) if monthly_returns.std() > 0 else 0

    # 最大ドローダウン
    max_dd = df_results['drawdown'].min()

    # 勝率
    win_rate = (monthly_returns > 0).mean()

    print(f"\n期間: {df_results['start_date'].min().date()} ~ {df_results['end_date'].max().date()}")
    print(f"月数: {n_months} ヶ月 ({n_years:.1f}年)")
    print(f"\n初期資本: ¥{INITIAL_CAPITAL:,}")
    print(f"最終資産: ¥{int(final_value):,}")
    print(f"\n総リターン: {total_return*100:.2f}%")
    print(f"年率リターン: {annual_return*100:.2f}%")
    print(f"シャープレシオ: {sharpe_ratio:.2f}")
    print(f"最大DD: {max_dd*100:.2f}%")
    print(f"勝率: {win_rate*100:.1f}%")

    # 月次リターンの分布
    print(f"\n月次リターン統計:")
    print(f"  平均: {monthly_returns.mean()*100:.2f}%")
    print(f"  標準偏差: {monthly_returns.std()*100:.2f}%")
    print(f"  最大: {monthly_returns.max()*100:.2f}%")
    print(f"  最小: {monthly_returns.min()*100:.2f}%")

    # 結果保存
    output_dir = PROJECT_ROOT / 'analyses' / '20260221_2300_monthly_low_r2_validation'
    df_results.to_csv(output_dir / 'backtest_results.csv', index=False, encoding='utf-8-sig')

    # サマリー保存
    with open(output_dir / 'backtest_summary.txt', 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("月足最安値R2戦略 - バックテスト結果\n")
        f.write("="*80 + "\n\n")
        f.write(f"戦略: R2 >= {R2_THRESHOLD}, 月次リバランス, 上位{N_STOCKS}銘柄\n\n")
        f.write(f"期間: {df_results['start_date'].min().date()} ~ {df_results['end_date'].max().date()}\n")
        f.write(f"月数: {n_months} ヶ月 ({n_years:.1f}年)\n\n")
        f.write(f"初期資本: ¥{INITIAL_CAPITAL:,}\n")
        f.write(f"最終資産: ¥{int(final_value):,}\n\n")
        f.write(f"総リターン: {total_return*100:.2f}%\n")
        f.write(f"年率リターン: {annual_return*100:.2f}%\n")
        f.write(f"シャープレシオ: {sharpe_ratio:.2f}\n")
        f.write(f"最大DD: {max_dd*100:.2f}%\n")
        f.write(f"勝率: {win_rate*100:.1f}%\n\n")
        f.write(f"月次リターン統計:\n")
        f.write(f"  平均: {monthly_returns.mean()*100:.2f}%\n")
        f.write(f"  標準偏差: {monthly_returns.std()*100:.2f}%\n")
        f.write(f"  最大: {monthly_returns.max()*100:.2f}%\n")
        f.write(f"  最小: {monthly_returns.min()*100:.2f}%\n")

    print(f"\n結果を保存:")
    print(f"  - {output_dir / 'backtest_results.csv'}")
    print(f"  - {output_dir / 'backtest_summary.txt'}")

else:
    print("\nエラー: 結果が生成されませんでした")

print("\n完了!")
