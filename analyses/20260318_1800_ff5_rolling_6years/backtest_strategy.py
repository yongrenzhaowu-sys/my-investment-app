"""
FF5大型グロース戦略のバックテスト

204銘柄を対象に月次リバランス戦略を実施
期間: 2021-03 ~ 2026-03
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data/processed/jquants_historical_6years"
SCREEN_PATH = Path(__file__).parent / "results/screened_stocks_corrected.csv"
OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("="*80)
print("FF5大型グロース戦略バックテスト")
print("="*80)

# パラメータ
PORTFOLIO_SIZE = 20  # ポートフォリオサイズ
REBALANCE_FREQ = 'M'  # 月次リバランス

print(f"\nパラメータ:")
print(f"  ポートフォリオサイズ: {PORTFOLIO_SIZE}銘柄")
print(f"  リバランス頻度: 月次")

# データ読み込み
print("\n[1] データ読み込み")
df_prices = pd.read_parquet(DATA_DIR / "daily_bars_2021_2026.parquet")
df_fins = pd.read_parquet(DATA_DIR / "financials_2021_2026.parquet")

print(f"  株価: {len(df_prices):,}レコード")
print(f"  財務: {len(df_fins):,}レコード")

# 日付型に変換
df_prices['Date'] = pd.to_datetime(df_prices['Date'])
df_fins['DiscDate'] = pd.to_datetime(df_fins['DiscDate'])

# Codeを4桁に統一
df_prices['Code'] = df_prices['Code'].str[:4]
df_fins['Code'] = df_fins['Code'].str[:4]

# 調整済み株価を計算
df_prices['AdjC_Correct'] = df_prices['C'] * df_prices['AdjFactor']
df_prices['Price'] = df_prices['AdjC_Correct']

# 重複除外
df_prices = df_prices.sort_values(['Code', 'Date', 'Vo'], ascending=[True, True, False])
df_prices = df_prices.drop_duplicates(subset=['Code', 'Date'], keep='first')

print(f"  重複除外後: {len(df_prices):,}レコード")

# 数値型に変換
for col in ['Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS', 'ShOutFY', 'TrShFY', 'AvgSh']:
    df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

# BPS代替計算
df_fins['SharesOut'] = df_fins['ShOutFY'].fillna(df_fins['TrShFY']).fillna(df_fins['AvgSh'])
df_fins['BPS_Calc'] = df_fins['Eq'] / df_fins['SharesOut']
df_fins['BPS_Final'] = df_fins['BPS'].fillna(df_fins['BPS_Calc'])

# バックテスト期間
start_date = pd.to_datetime('2021-03-01')
end_date = pd.to_datetime('2026-03-31')

# 月初日のリスト（リバランス日）
rebalance_dates = pd.date_range(start=start_date, end=end_date, freq='MS')
print(f"\n[2] リバランス日")
print(f"  期間: {start_date.date()} ~ {end_date.date()}")
print(f"  リバランス回数: {len(rebalance_dates)}回")

# バックテスト実行
print("\n[3] バックテスト実行")
portfolio_returns = []
portfolio_dates = []
rebalance_log = []

for i in range(len(rebalance_dates) - 1):
    rebal_date = rebalance_dates[i]
    next_rebal_date = rebalance_dates[i + 1]

    # リバランス日の銘柄選択
    # 6ヶ月前の日付
    six_months_ago = rebal_date - timedelta(days=180)

    # リバランス日時点で利用可能なデータ
    available_prices = df_prices[df_prices['Date'] <= rebal_date].copy()
    available_fins = df_fins[df_fins['DiscDate'] <= rebal_date].copy()

    # 6ヶ月前の価格
    past_prices = df_prices[
        (df_prices['Date'] >= six_months_ago - timedelta(days=7)) &
        (df_prices['Date'] <= six_months_ago + timedelta(days=7))
    ].copy()
    past_prices = past_prices.sort_values(['Code', 'Date']).groupby('Code').first().reset_index()
    past_prices = past_prices[['Code', 'Price']].rename(columns={'Price': 'Price_6M'})

    # 最新価格
    latest_prices = available_prices.sort_values('Date').groupby('Code').last().reset_index()
    latest_prices = latest_prices[['Code', 'Price']].rename(columns={'Price': 'Price_Now'})

    # マージ
    stock_data = latest_prices.merge(past_prices, on='Code', how='inner')
    stock_data['Return_6M'] = (stock_data['Price_Now'] / stock_data['Price_6M'] - 1) * 100

    # 最新財務データ
    latest_fins = available_fins.sort_values('DiscDate').groupby('Code').last().reset_index()
    stock_data = stock_data.merge(
        latest_fins[['Code', 'Eq', 'BPS_Final', 'Sales', 'OP']],
        on='Code',
        how='left'
    )

    # 時価総額・PBR計算
    stock_data['MarketCap'] = stock_data['Price_Now'] * (stock_data['Eq'] / stock_data['BPS_Final'])
    stock_data['PBR'] = stock_data['Price_Now'] / stock_data['BPS_Final']

    # 欠損値除外
    valid_data = stock_data.dropna(subset=['MarketCap', 'Return_6M', 'PBR']).copy()

    # スクリーニング条件
    mc_threshold = valid_data['MarketCap'].quantile(0.70)
    return_threshold = valid_data['Return_6M'].median()

    condition1 = valid_data['MarketCap'] >= mc_threshold
    condition2 = valid_data['Return_6M'] >= return_threshold
    condition3 = valid_data['PBR'] >= 2.0

    screened = valid_data[condition1 & condition2 & condition3].copy()

    # 時価総額上位N銘柄を選択
    screened = screened.sort_values('MarketCap', ascending=False).head(PORTFOLIO_SIZE)
    selected_codes = screened['Code'].tolist()

    if len(selected_codes) == 0:
        print(f"  {rebal_date.date()}: スクリーニング結果0銘柄、スキップ")
        continue

    # 次回リバランスまでの期間のリターン計算
    period_prices = df_prices[
        (df_prices['Date'] > rebal_date) &
        (df_prices['Date'] <= next_rebal_date) &
        (df_prices['Code'].isin(selected_codes))
    ].copy()

    # 銘柄ごとに期間リターンを計算
    returns_dict = {}
    for code in selected_codes:
        code_prices = period_prices[period_prices['Code'] == code].sort_values('Date')
        if len(code_prices) >= 2:
            start_price = code_prices.iloc[0]['Price']
            end_price = code_prices.iloc[-1]['Price']
            period_return = (end_price / start_price) - 1
            returns_dict[code] = period_return
        else:
            returns_dict[code] = 0.0

    # 等ウェイトポートフォリオリターン
    if len(returns_dict) > 0:
        portfolio_return = np.mean(list(returns_dict.values()))
        portfolio_returns.append(portfolio_return)
        portfolio_dates.append(next_rebal_date)

        rebalance_log.append({
            'Date': rebal_date,
            'N_Stocks': len(selected_codes),
            'Return': portfolio_return * 100
        })

        if (i + 1) % 12 == 0:
            print(f"  {rebal_date.date()}: {len(selected_codes)}銘柄、リターン={portfolio_return*100:.2f}%")

# 結果
print(f"\n[4] バックテスト結果")
print(f"  リバランス回数: {len(portfolio_returns)}回")
print(f"  期間: {portfolio_dates[0].date()} ~ {portfolio_dates[-1].date()}")

portfolio_returns = np.array(portfolio_returns)

# 評価指標
cumulative_return = (np.prod(1 + portfolio_returns) - 1) * 100
annual_return = (np.prod(1 + portfolio_returns) ** (12 / len(portfolio_returns)) - 1) * 100
annual_volatility = np.std(portfolio_returns) * np.sqrt(12) * 100
sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0

# 最大ドローダウン
cumulative = np.cumprod(1 + portfolio_returns)
running_max = np.maximum.accumulate(cumulative)
drawdown = (cumulative / running_max) - 1
max_drawdown = np.min(drawdown) * 100

print(f"\n[5] パフォーマンス指標")
print(f"  累積リターン: {cumulative_return:.2f}%")
print(f"  年率リターン: {annual_return:.2f}%")
print(f"  年率ボラティリティ: {annual_volatility:.2f}%")
print(f"  シャープレシオ: {sharpe_ratio:.2f}")
print(f"  最大ドローダウン: {max_drawdown:.2f}%")
print(f"  勝率: {(portfolio_returns > 0).sum() / len(portfolio_returns) * 100:.1f}%")

# 結果保存
results_df = pd.DataFrame({
    'Date': portfolio_dates,
    'Return': portfolio_returns * 100,
    'Cumulative': cumulative
})

output_path = OUTPUT_DIR / "backtest_ff5_strategy.csv"
results_df.to_csv(output_path, index=False)
print(f"\n[6] 保存完了: {output_path}")

# リバランスログ保存
rebal_log_df = pd.DataFrame(rebalance_log)
rebal_log_path = OUTPUT_DIR / "rebalance_log.csv"
rebal_log_df.to_csv(rebal_log_path, index=False)
print(f"  リバランスログ: {rebal_log_path}")

# サマリー保存
summary = {
    'Strategy': 'FF5_Large_Growth',
    'Portfolio_Size': PORTFOLIO_SIZE,
    'Cumulative_Return': cumulative_return,
    'Annual_Return': annual_return,
    'Annual_Volatility': annual_volatility,
    'Sharpe_Ratio': sharpe_ratio,
    'Max_Drawdown': max_drawdown,
    'Win_Rate': (portfolio_returns > 0).sum() / len(portfolio_returns) * 100,
    'N_Rebalances': len(portfolio_returns),
    'Period_Start': portfolio_dates[0],
    'Period_End': portfolio_dates[-1]
}

summary_df = pd.DataFrame([summary])
summary_path = OUTPUT_DIR / "summary_ff5_strategy.csv"
summary_df.to_csv(summary_path, index=False)
print(f"  サマリー: {summary_path}")

print("\n完了")
