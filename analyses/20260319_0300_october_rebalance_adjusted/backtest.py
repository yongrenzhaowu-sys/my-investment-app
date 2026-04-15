"""
10月リバランス戦略 - 調整済み株価版バックテスト

Legacy版の再現 + 調整済み株価の適用
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data/processed/jquants_historical_6years"
OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("="*80)
print("10月リバランス戦略 - 調整済み株価版バックテスト")
print("="*80)

# パラメータ
INITIAL_CAPITAL = 10_000_000  # 初期資金
TARGET_POSITIONS = 20  # 目標銘柄数
TAX_RATE = 0.20315  # 税率（所得税15% + 住民税5% + 復興税0.315%）

print(f"\nParameters:")
print(f"  Initial Capital: {INITIAL_CAPITAL:,} JPY")
print(f"  Target Positions: {TARGET_POSITIONS} stocks")
print(f"  Tax Rate: {TAX_RATE*100:.3f}%")

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

# 調整済み株価を計算（CRITICAL）
df_prices['AdjC_Correct'] = df_prices['C'] * df_prices['AdjFactor']
df_prices['Price'] = df_prices['AdjC_Correct']

# 重複除外（同じCode×Dateで最も取引量が多いレコード）
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

# Profit列の作成（NP = 当期純利益）
df_fins['Profit'] = df_fins['NP']

# バックテスト期間（10月1日のリバランス日）
rebalance_dates = pd.to_datetime([
    '2017-10-01',
    '2018-10-01',
    '2019-10-01',
    '2020-10-01',
    '2021-10-01',
    '2022-10-01',
    '2023-10-01',
    '2024-10-01',
    '2025-10-01',
])

print(f"\n[2] リバランス日")
print(f"  期間: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}")
print(f"  リバランス回数: {len(rebalance_dates)}回")

# バックテスト実行
print("\n[3] バックテスト実行")

annual_returns = []
portfolio_history = []

for i in range(len(rebalance_dates) - 1):
    rebal_date = rebalance_dates[i]
    next_rebal_date = rebalance_dates[i + 1]

    print(f"\n  --- {rebal_date.date()} ---")

    # リバランス日時点で利用可能なデータ
    available_prices = df_prices[df_prices['Date'] <= rebal_date].copy()
    available_fins = df_fins[df_fins['DiscDate'] <= rebal_date].copy()

    # 最新価格（リバランス日の終値）
    latest_prices = available_prices.sort_values('Date').groupby('Code').last().reset_index()
    latest_prices = latest_prices[['Code', 'Price']].rename(columns={'Price': 'Close'})

    # 最新財務データ
    latest_fins = available_fins.sort_values('DiscDate').groupby('Code').last().reset_index()

    # マージ
    merged = latest_prices.merge(
        latest_fins[['Code', 'Profit', 'Eq', 'SharesOut']],
        on='Code',
        how='inner'
    )

    # 数値型確認
    merged['Profit'] = pd.to_numeric(merged['Profit'], errors='coerce')
    merged['Eq'] = pd.to_numeric(merged['Eq'], errors='coerce')
    merged['SharesOut'] = pd.to_numeric(merged['SharesOut'], errors='coerce')

    # 時価総額・PBR・ROE計算
    merged['MarketCap'] = merged['Close'] * merged['SharesOut']
    merged['PBR'] = merged['MarketCap'] / merged['Eq']
    merged['ROE'] = (merged['Profit'] / merged['Eq']) * 100

    # 異常値除去（Legacy版の条件を踏襲）
    valid_data = merged[
        (merged['PBR'] > 0) &
        (merged['PBR'] < 50) &
        (merged['ROE'] > -100) &
        (merged['ROE'] < 100) &
        (merged['MarketCap'] > 1_000_000_000)
    ].copy()

    print(f"    有効データ: {len(valid_data)}銘柄")

    if len(valid_data) < 100:
        print(f"    ⚠️ データ不足（最低100銘柄必要）")
        continue

    # ランキング（Legacy版を踏襲）
    valid_data['PBR_Rank'] = valid_data['PBR'].rank(method='first', ascending=True)
    valid_data['ROE_Rank'] = valid_data['ROE'].rank(method='first', ascending=False)

    # 四分位分割
    valid_data['PBR_Quartile'] = pd.qcut(valid_data['PBR_Rank'], q=4, labels=[1, 2, 3, 4], duplicates='drop')
    valid_data['ROE_Quartile'] = pd.qcut(valid_data['ROE_Rank'], q=4, labels=[1, 2, 3, 4], duplicates='drop')

    # スクリーニング条件：低PBR（Q1）× 高ROE（Q4）
    candidates = valid_data[
        (valid_data['PBR_Quartile'] == 1) &
        (valid_data['ROE_Quartile'] == 4)
    ].copy()

    # PBR最小上位50銘柄
    candidates = candidates.nsmallest(50, 'PBR')

    print(f"    候補銘柄: {len(candidates)}銘柄")

    if len(candidates) < TARGET_POSITIONS:
        print(f"    ⚠️ 候補不足（目標{TARGET_POSITIONS}銘柄）")
        continue

    # ポートフォリオ構築（上位20銘柄、100株単位、等ウェイト）
    selected = candidates.head(TARGET_POSITIONS).copy()
    capital_per_stock = INITIAL_CAPITAL / TARGET_POSITIONS

    portfolio = []
    for _, row in selected.iterrows():
        price = row['Close']
        shares = int(capital_per_stock / price / 100) * 100  # 100株単位
        if shares > 0:
            portfolio.append({
                'Code': row['Code'],
                'Shares': shares,
                'EntryPrice': price,
                'Amount': shares * price
            })

    portfolio_df = pd.DataFrame(portfolio)
    total_investment = portfolio_df['Amount'].sum()

    print(f"    ポートフォリオ: {len(portfolio_df)}銘柄")
    print(f"    投資額: ¥{total_investment:,.0f} ({total_investment/INITIAL_CAPITAL*100:.1f}%)")

    # 保有期間中のリターン計算
    # エントリー: 翌営業日始値、エグジット: 翌年10月翌営業日始値
    entry_start = rebal_date + timedelta(days=1)
    exit_start = next_rebal_date + timedelta(days=1)

    # 翌営業日を探す（±5営業日以内）
    entry_dates = df_prices[
        (df_prices['Date'] >= entry_start) &
        (df_prices['Date'] <= entry_start + timedelta(days=5))
    ]['Date'].unique()

    exit_dates = df_prices[
        (df_prices['Date'] >= exit_start) &
        (df_prices['Date'] <= exit_start + timedelta(days=5))
    ]['Date'].unique()

    if len(entry_dates) == 0 or len(exit_dates) == 0:
        print(f"    ⚠️ エントリー/エグジット日が見つかりません")
        continue

    entry_date = min(entry_dates)
    exit_date = min(exit_dates)

    # エントリー価格（始値 = Oを使用）
    entry_prices_data = df_prices[
        (df_prices['Date'] == entry_date) &
        (df_prices['Code'].isin(portfolio_df['Code']))
    ][['Code', 'O']].rename(columns={'O': 'EntryPriceActual'})

    # エグジット価格（始値 = Oを使用）
    exit_prices_data = df_prices[
        (df_prices['Date'] == exit_date) &
        (df_prices['Code'].isin(portfolio_df['Code']))
    ][['Code', 'O']].rename(columns={'O': 'ExitPrice'})

    # マージ
    portfolio_df = portfolio_df.merge(entry_prices_data, on='Code', how='left')
    portfolio_df = portfolio_df.merge(exit_prices_data, on='Code', how='left')

    # 欠損値は前日終値で代替
    portfolio_df['EntryPriceActual'] = portfolio_df['EntryPriceActual'].fillna(portfolio_df['EntryPrice'])
    portfolio_df['ExitPrice'] = portfolio_df['ExitPrice'].fillna(portfolio_df['EntryPrice'])

    # 銘柄ごとのリターン計算
    portfolio_df['Return'] = (portfolio_df['ExitPrice'] / portfolio_df['EntryPriceActual']) - 1
    portfolio_df['PnL'] = portfolio_df['Shares'] * (portfolio_df['ExitPrice'] - portfolio_df['EntryPriceActual'])

    # ポートフォリオリターン（等ウェイト）
    portfolio_return_gross = portfolio_df['Return'].mean()

    # 税金計算（利益が出た場合のみ）
    total_pnl = portfolio_df['PnL'].sum()
    tax = max(0, total_pnl * TAX_RATE)
    portfolio_return_net = (total_pnl - tax) / total_investment

    print(f"    エントリー: {entry_date.date()}")
    print(f"    エグジット: {exit_date.date()}")
    print(f"    グロスリターン: {portfolio_return_gross*100:.2f}%")
    print(f"    ネットリターン（税引き後）: {portfolio_return_net*100:.2f}%")
    print(f"    税金: ¥{tax:,.0f}")

    # 記録
    annual_returns.append({
        'Year': rebal_date.year,
        'RebalanceDate': rebal_date,
        'EntryDate': entry_date,
        'ExitDate': exit_date,
        'N_Stocks': len(portfolio_df),
        'Investment': total_investment,
        'GrossReturn': portfolio_return_gross,
        'NetReturn': portfolio_return_net,
        'Tax': tax
    })

    portfolio_history.append(portfolio_df)

# 結果をDataFrameに変換
annual_returns_df = pd.DataFrame(annual_returns)

print(f"\n[4] バックテスト結果")
print(f"  実行回数: {len(annual_returns_df)}回")

if len(annual_returns_df) == 0:
    print("❌ バックテスト失敗（データ不足）")
    exit(1)

# 評価指標計算
net_returns = annual_returns_df['NetReturn'].values
cumulative_return = (np.prod(1 + net_returns) - 1) * 100
n_years = len(net_returns)
annual_return = ((1 + cumulative_return/100) ** (1/n_years) - 1) * 100
annual_volatility = np.std(net_returns) * 100
sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0

# 最大ドローダウン
cumulative_series = np.cumprod(1 + net_returns)
running_max = np.maximum.accumulate(cumulative_series)
drawdown = (cumulative_series / running_max) - 1
max_drawdown = np.min(drawdown) * 100

# 勝率
win_rate = (net_returns > 0).sum() / len(net_returns) * 100

print(f"\n[5] パフォーマンス指標（税引き後）")
print(f"  累積リターン: {cumulative_return:.2f}%")
print(f"  年率リターン: {annual_return:.2f}%")
print(f"  年率ボラティリティ: {annual_volatility:.2f}%")
print(f"  シャープレシオ: {sharpe_ratio:.2f}")
print(f"  最大ドローダウン: {max_drawdown:.2f}%")
print(f"  勝率: {win_rate:.1f}% ({(net_returns > 0).sum()}/{len(net_returns)})")

# 結果保存
annual_returns_path = OUTPUT_DIR / "annual_returns.csv"
annual_returns_df.to_csv(annual_returns_path, index=False)
print(f"\n[6] 保存完了")
print(f"  年次リターン: {annual_returns_path}")

# サマリー保存
summary = {
    'Strategy': 'October_Rebalance_Adjusted',
    'Period': f"{annual_returns_df['RebalanceDate'].min().date()} ~ {annual_returns_df['RebalanceDate'].max().date()}",
    'N_Years': n_years,
    'Cumulative_Return': cumulative_return,
    'Annual_Return': annual_return,
    'Annual_Volatility': annual_volatility,
    'Sharpe_Ratio': sharpe_ratio,
    'Max_Drawdown': max_drawdown,
    'Win_Rate': win_rate,
    'N_Rebalances': len(annual_returns_df)
}

summary_df = pd.DataFrame([summary])
summary_path = OUTPUT_DIR / "performance_summary.csv"
summary_df.to_csv(summary_path, index=False)
print(f"  サマリー: {summary_path}")

# 年次リターン詳細表示
print(f"\n[7] 年次リターン詳細")
for _, row in annual_returns_df.iterrows():
    print(f"  {row['Year']}: {row['NetReturn']*100:>6.2f}% ({row['N_Stocks']}銘柄、税金 ¥{row['Tax']:,.0f})")

print("\n完了")
