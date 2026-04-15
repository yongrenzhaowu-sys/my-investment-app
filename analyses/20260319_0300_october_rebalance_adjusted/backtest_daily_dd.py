# -*- coding: utf-8 -*-
"""
October Rebalance Strategy - Daily Drawdown Version

Tracks daily portfolio value to calculate daily drawdown
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Path setup
PROJECT_ROOT = Path('C:/Users/yongr/claude project/workspace')
DATA_DIR = PROJECT_ROOT / 'data/processed/jquants_historical_6years'
OUTPUT_DIR = Path('results')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print('='*80)
print('October Rebalance Strategy - Daily Drawdown Version')
print('='*80)

# Parameters
INITIAL_CAPITAL = 10_000_000
TARGET_POSITIONS = 20
TAX_RATE = 0.20315

print(f'\nParameters:')
print(f'  Initial Capital: {INITIAL_CAPITAL:,} JPY')
print(f'  Target Positions: {TARGET_POSITIONS} stocks')
print(f'  Tax Rate: {TAX_RATE*100:.3f}%')

# Load data
print('\n[1] Loading Data')
df_prices = pd.read_parquet(DATA_DIR / 'daily_bars_2021_2026.parquet')
df_fins = pd.read_parquet(DATA_DIR / 'financials_2021_2026.parquet')

print(f'  Prices: {len(df_prices):,} records')
print(f'  Financials: {len(df_fins):,} records')

# Date conversion
df_prices['Date'] = pd.to_datetime(df_prices['Date'])
df_fins['DiscDate'] = pd.to_datetime(df_fins['DiscDate'])

# Code standardization
df_prices['Code'] = df_prices['Code'].str[:4]
df_fins['Code'] = df_fins['Code'].str[:4]

# Adjusted price calculation
df_prices['AdjC_Correct'] = df_prices['C'] * df_prices['AdjFactor']
df_prices['Price'] = df_prices['AdjC_Correct']

# Remove duplicates
df_prices = df_prices.sort_values(['Code', 'Date', 'Vo'], ascending=[True, True, False])
df_prices = df_prices.drop_duplicates(subset=['Code', 'Date'], keep='first')

print(f'  After deduplication: {len(df_prices):,} records')

# Convert to numeric
for col in ['Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS', 'ShOutFY', 'TrShFY', 'AvgSh']:
    df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

# BPS calculation
df_fins['SharesOut'] = df_fins['ShOutFY'].fillna(df_fins['TrShFY']).fillna(df_fins['AvgSh'])
df_fins['BPS_Calc'] = df_fins['Eq'] / df_fins['SharesOut']
df_fins['BPS_Final'] = df_fins['BPS'].fillna(df_fins['BPS_Calc'])
df_fins['Profit'] = df_fins['NP']

# Rebalance dates
rebalance_dates = pd.to_datetime([
    '2021-10-01',
    '2022-10-01',
    '2023-10-01',
    '2024-10-01',
    '2025-10-01',
])

print(f'\n[2] Rebalance Dates')
print(f'  Period: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}')
print(f'  N Rebalances: {len(rebalance_dates)}')

print('\n[3] Running Backtest with Daily Tracking')

daily_portfolio_values = []
current_portfolio = []

for i in range(len(rebalance_dates) - 1):
    rebal_date = rebalance_dates[i]
    next_rebal_date = rebalance_dates[i + 1]

    print(f'\n  --- {rebal_date.date()} ---')

    # Screening (same as before)
    available_prices = df_prices[df_prices['Date'] <= rebal_date].copy()
    available_fins = df_fins[df_fins['DiscDate'] <= rebal_date].copy()

    latest_prices = available_prices.sort_values('Date').groupby('Code').last().reset_index()
    latest_prices = latest_prices[['Code', 'Price']].rename(columns={'Price': 'Close'})

    latest_fins = available_fins.sort_values('DiscDate').groupby('Code').last().reset_index()

    merged = latest_prices.merge(
        latest_fins[['Code', 'Profit', 'Eq', 'SharesOut']],
        on='Code',
        how='inner'
    )

    merged['Profit'] = pd.to_numeric(merged['Profit'], errors='coerce')
    merged['Eq'] = pd.to_numeric(merged['Eq'], errors='coerce')
    merged['SharesOut'] = pd.to_numeric(merged['SharesOut'], errors='coerce')

    merged['MarketCap'] = merged['Close'] * merged['SharesOut']
    merged['PBR'] = merged['MarketCap'] / merged['Eq']
    merged['ROE'] = (merged['Profit'] / merged['Eq']) * 100

    valid_data = merged[
        (merged['PBR'] > 0) &
        (merged['PBR'] < 50) &
        (merged['ROE'] > -100) &
        (merged['ROE'] < 100) &
        (merged['MarketCap'] > 1_000_000_000)
    ].copy()

    if len(valid_data) < 100:
        print(f'    SKIP: Insufficient data')
        continue

    valid_data['PBR_Rank'] = valid_data['PBR'].rank(method='first', ascending=True)
    valid_data['ROE_Rank'] = valid_data['ROE'].rank(method='first', ascending=False)

    valid_data['PBR_Quartile'] = pd.qcut(valid_data['PBR_Rank'], q=4, labels=[1, 2, 3, 4], duplicates='drop')
    valid_data['ROE_Quartile'] = pd.qcut(valid_data['ROE_Rank'], q=4, labels=[1, 2, 3, 4], duplicates='drop')

    candidates = valid_data[
        (valid_data['PBR_Quartile'] == 1) &
        (valid_data['ROE_Quartile'] == 4)
    ].copy()

    candidates = candidates.nsmallest(50, 'PBR')

    if len(candidates) < TARGET_POSITIONS:
        print(f'    SKIP: Insufficient candidates')
        continue

    selected = candidates.head(TARGET_POSITIONS).copy()
    capital_per_stock = INITIAL_CAPITAL / TARGET_POSITIONS

    portfolio = []
    for _, row in selected.iterrows():
        price = row['Close']
        shares = int(capital_per_stock / price / 100) * 100
        if shares > 0:
            portfolio.append({
                'Code': row['Code'],
                'Shares': shares
            })

    current_portfolio = pd.DataFrame(portfolio)

    print(f'    Portfolio: {len(current_portfolio)} stocks')

    # Entry date (next business day)
    entry_start = rebal_date + timedelta(days=1)
    exit_start = next_rebal_date + timedelta(days=1)

    entry_dates = df_prices[
        (df_prices['Date'] >= entry_start) &
        (df_prices['Date'] <= entry_start + timedelta(days=5))
    ]['Date'].unique()

    if len(entry_dates) == 0:
        print(f'    SKIP: Cannot find entry date')
        continue

    entry_date = min(entry_dates)

    # Daily tracking
    period_dates = df_prices[
        (df_prices['Date'] >= entry_date) &
        (df_prices['Date'] < next_rebal_date)
    ]['Date'].unique()
    period_dates = sorted(period_dates)

    print(f'    Entry: {entry_date.date()}')
    print(f'    Tracking {len(period_dates)} trading days')

    for date in period_dates:
        date_prices = df_prices[
            (df_prices['Date'] == date) &
            (df_prices['Code'].isin(current_portfolio['Code']))
        ][['Code', 'Price']]

        portfolio_with_prices = current_portfolio.merge(date_prices, on='Code', how='left')
        portfolio_with_prices['Price'] = portfolio_with_prices['Price'].fillna(method='ffill')

        portfolio_value = (portfolio_with_prices['Shares'] * portfolio_with_prices['Price']).sum()

        daily_portfolio_values.append({
            'Date': date,
            'PortfolioValue': portfolio_value
        })

# Results
daily_df = pd.DataFrame(daily_portfolio_values)

if len(daily_df) == 0:
    print('ERROR: No daily data')
    exit(1)

print(f'\n[4] Daily Portfolio Values')
print(f'  N Days: {len(daily_df)} trading days')
print(f'  Period: {daily_df["Date"].min().date()} ~ {daily_df["Date"].max().date()}')

# Daily returns
daily_df = daily_df.sort_values('Date').reset_index(drop=True)
daily_df['DailyReturn'] = daily_df['PortfolioValue'].pct_change()

# Cumulative value
daily_df['CumulativeValue'] = daily_df['PortfolioValue']

# Drawdown calculation
daily_df['RunningMax'] = daily_df['CumulativeValue'].expanding().max()
daily_df['Drawdown'] = (daily_df['CumulativeValue'] / daily_df['RunningMax']) - 1

max_dd_daily = daily_df['Drawdown'].min() * 100
max_dd_date = daily_df.loc[daily_df['Drawdown'].idxmin(), 'Date']

print(f'\n[5] Daily Drawdown Analysis')
print(f'  Max Daily Drawdown: {max_dd_daily:.2f}%')
print(f'  Occurred on: {max_dd_date.date()}')

# Cumulative return
total_return = (daily_df['PortfolioValue'].iloc[-1] / INITIAL_CAPITAL - 1) * 100
print(f'  Total Return (gross): {total_return:.2f}%')

# Save
daily_path = OUTPUT_DIR / 'daily_portfolio_values.csv'
daily_df.to_csv(daily_path, index=False)
print(f'\n[6] Saved: {daily_path}')

# Summary
summary = {
    'Strategy': 'October_Rebalance_Daily_DD',
    'Period': f'{daily_df["Date"].min().date()} ~ {daily_df["Date"].max().date()}',
    'N_Days': len(daily_df),
    'Total_Return_Gross': total_return,
    'Max_Daily_Drawdown': max_dd_daily,
    'Max_DD_Date': max_dd_date
}

summary_df = pd.DataFrame([summary])
summary_path = OUTPUT_DIR / 'daily_dd_summary.csv'
summary_df.to_csv(summary_path, index=False)
print(f'  Summary: {summary_path}')

print('\nCompleted')
