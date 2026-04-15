# -*- coding: utf-8 -*-
"""
Investigate 2023 Portfolio Selection
Why +0.02% vs Legacy +51.70%?
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path('C:/Users/yongr/claude project/workspace')
PRICES_PATH = PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet'
FINS_PATH = PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet'
OUTPUT_DIR = Path('results')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print('='*80)
print('Investigating 2023 Portfolio Selection')
print('='*80)

# Load data
print('\n[1] Loading Data')
df_prices = pd.read_parquet(PRICES_PATH)
df_fins = pd.read_parquet(FINS_PATH)

# Date conversion
df_prices['date'] = pd.to_datetime(df_prices['date'])
df_fins['disclosed_date'] = pd.to_datetime(df_fins['disclosed_date'])

# Code standardization
df_prices['code'] = df_prices['code'].astype(str).str[:4]
df_fins['code'] = df_fins['code'].astype(str).str[:4]

# Rename and calculate adjusted prices
df_prices = df_prices.rename(columns={
    'date': 'Date',
    'code': 'Code',
    'open': 'O',
    'close': 'C',
    'adjusted_close': 'AdjC_Wrong',
    'adjustment_factor': 'AdjFactor'
})

df_prices['AdjC_Correct'] = df_prices['C'] * df_prices['AdjFactor']
df_prices['Price'] = df_prices['AdjC_Correct']

# Remove duplicates
df_prices = df_prices.sort_values(['Code', 'Date'], ascending=[True, True])
df_prices = df_prices.drop_duplicates(subset=['Code', 'Date'], keep='last')

# Financials
df_fins = df_fins.rename(columns={
    'disclosed_date': 'DiscDate',
    'code': 'Code',
    'net_profit': 'Profit',
    'equity': 'Equity',
    'bps': 'BPS',
    'total_assets': 'TA'
})

for col in ['Profit', 'Equity', 'BPS', 'TA']:
    if col in df_fins.columns:
        df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

df_fins['SharesOut'] = df_fins['Equity'] / df_fins['BPS']

# Focus on 2023
rebal_date = pd.to_datetime('2023-10-01')
next_rebal_date = pd.to_datetime('2024-10-01')

print(f'\n[2] Screening at {rebal_date.date()}')

# Available data
available_prices = df_prices[df_prices['Date'] <= rebal_date].copy()
available_fins = df_fins[df_fins['DiscDate'] <= rebal_date].copy()

# Latest prices
latest_prices = available_prices.sort_values('Date').groupby('Code').last().reset_index()
latest_prices = latest_prices[['Code', 'Price']].rename(columns={'Price': 'Close'})

# Latest financials
latest_fins = available_fins.sort_values('DiscDate').groupby('Code').last().reset_index()

# Merge
merged = latest_prices.merge(
    latest_fins[['Code', 'Profit', 'Equity', 'SharesOut']],
    on='Code',
    how='inner'
)

merged['Profit'] = pd.to_numeric(merged['Profit'], errors='coerce')
merged['Equity'] = pd.to_numeric(merged['Equity'], errors='coerce')
merged['SharesOut'] = pd.to_numeric(merged['SharesOut'], errors='coerce')

# Calculate
merged['MarketCap'] = merged['Close'] * merged['SharesOut']
merged['PBR'] = merged['MarketCap'] / merged['Equity']
merged['ROE'] = (merged['Profit'] / merged['Equity']) * 100

# Filter
valid_data = merged[
    (merged['PBR'] > 0) &
    (merged['PBR'] < 50) &
    (merged['ROE'] > -100) &
    (merged['ROE'] < 100) &
    (merged['MarketCap'] > 1_000_000_000)
].copy()

print(f'  Valid data: {len(valid_data)} stocks')

# Ranking
valid_data['PBR_Rank'] = valid_data['PBR'].rank(method='first', ascending=True)
valid_data['ROE_Rank'] = valid_data['ROE'].rank(method='first', ascending=False)

# Quartile
valid_data['PBR_Quartile'] = pd.qcut(valid_data['PBR_Rank'], q=4, labels=[1, 2, 3, 4], duplicates='drop')
valid_data['ROE_Quartile'] = pd.qcut(valid_data['ROE_Rank'], q=4, labels=[1, 2, 3, 4], duplicates='drop')

# Screening
candidates = valid_data[
    (valid_data['PBR_Quartile'] == 1) &
    (valid_data['ROE_Quartile'] == 4)
].copy()

candidates = candidates.nsmallest(50, 'PBR')
print(f'  Candidates: {len(candidates)} stocks')

# Top 20
selected = candidates.head(20).copy()
print(f'  Selected: {len(selected)} stocks')

# Entry/Exit dates
entry_start = rebal_date + timedelta(days=1)
exit_start = next_rebal_date + timedelta(days=1)

entry_dates = df_prices[
    (df_prices['Date'] >= entry_start) &
    (df_prices['Date'] <= entry_start + timedelta(days=5))
]['Date'].unique()

exit_dates = df_prices[
    (df_prices['Date'] >= exit_start) &
    (df_prices['Date'] <= exit_start + timedelta(days=5))
]['Date'].unique()

entry_date = min(entry_dates)
exit_date = min(exit_dates)

print(f'  Entry date: {entry_date.date()}')
print(f'  Exit date: {exit_date.date()}')

# Get entry/exit prices
entry_prices = df_prices[
    (df_prices['Date'] == entry_date) &
    (df_prices['Code'].isin(selected['Code']))
][['Code', 'O']].rename(columns={'O': 'EntryPrice'})

exit_prices = df_prices[
    (df_prices['Date'] == exit_date) &
    (df_prices['Code'].isin(selected['Code']))
][['Code', 'O']].rename(columns={'O': 'ExitPrice'})

# Merge
portfolio = selected.merge(entry_prices, on='Code', how='left')
portfolio = portfolio.merge(exit_prices, on='Code', how='left')

# Fill missing
portfolio['EntryPrice'] = portfolio['EntryPrice'].fillna(portfolio['Close'])
portfolio['ExitPrice'] = portfolio['ExitPrice'].fillna(portfolio['Close'])

# Calculate return
portfolio['Return'] = (portfolio['ExitPrice'] / portfolio['EntryPrice'] - 1) * 100

# Sort by return
portfolio = portfolio.sort_values('Return', ascending=False)

print(f'\n[3] Portfolio Details (sorted by return)')
print(portfolio[['Code', 'PBR', 'ROE', 'MarketCap', 'EntryPrice', 'ExitPrice', 'Return']].to_string(index=False))

# Statistics
print(f'\n[4] Return Statistics')
print(f'  Mean return: {portfolio["Return"].mean():.2f}%')
print(f'  Median return: {portfolio["Return"].median():.2f}%')
print(f'  Min return: {portfolio["Return"].min():.2f}%')
print(f'  Max return: {portfolio["Return"].max():.2f}%')
print(f'  Std dev: {portfolio["Return"].std():.2f}%')
print(f'  Positive returns: {(portfolio["Return"] > 0).sum()}/{len(portfolio)}')

# Check for anomalies
print(f'\n[5] Data Quality Checks')
missing_entry = portfolio['EntryPrice'].isna().sum()
missing_exit = portfolio['ExitPrice'].isna().sum()
zero_return = (portfolio['Return'].abs() < 0.01).sum()

print(f'  Missing entry prices: {missing_entry}')
print(f'  Missing exit prices: {missing_exit}')
print(f'  Near-zero returns (< 0.01%): {zero_return}')

if zero_return > 0:
    print(f'\n  Stocks with near-zero returns:')
    near_zero = portfolio[portfolio['Return'].abs() < 0.01]
    print(near_zero[['Code', 'EntryPrice', 'ExitPrice', 'Return']].to_string(index=False))

# Save
output_path = OUTPUT_DIR / 'portfolio_2023_detail.csv'
portfolio.to_csv(output_path, index=False)
print(f'\n[6] Saved to: {output_path}')

# Compare with all candidates
print(f'\n[7] Top 50 Candidates (we selected top 20)')
all_candidates = candidates[['Code', 'PBR', 'ROE', 'MarketCap']].head(50)
all_candidates['Selected'] = all_candidates['Code'].isin(portfolio['Code'])
print(all_candidates.to_string(index=False))

candidates_path = OUTPUT_DIR / 'candidates_2023_top50.csv'
all_candidates.to_csv(candidates_path, index=False)
print(f'\n  Saved candidates to: {candidates_path}')

print('\nCompleted')
