# -*- coding: utf-8 -*-
"""
Check ROE Distribution for 2023-10-01
Why are negative ROE values in "High ROE (Q4)" quartile?
"""
import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path('C:/Users/yongr/claude project/workspace')
PRICES_PATH = PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet'
FINS_PATH = PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet'
OUTPUT_DIR = Path('results')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print('='*80)
print('ROE Distribution Analysis for 2023-10-01')
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

# Rename
df_prices = df_prices.rename(columns={
    'date': 'Date',
    'code': 'Code',
    'close': 'C',
    'adjustment_factor': 'AdjFactor'
})

df_prices['Price'] = df_prices['C'] * df_prices['AdjFactor']
df_prices = df_prices.sort_values(['Code', 'Date'])
df_prices = df_prices.drop_duplicates(subset=['Code', 'Date'], keep='last')

df_fins = df_fins.rename(columns={
    'disclosed_date': 'DiscDate',
    'code': 'Code',
    'net_profit': 'Profit',
    'equity': 'Equity',
    'bps': 'BPS'
})

for col in ['Profit', 'Equity', 'BPS']:
    if col in df_fins.columns:
        df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

df_fins['SharesOut'] = df_fins['Equity'] / df_fins['BPS']

# Focus on 2023
rebal_date = pd.to_datetime('2023-10-01')

print(f'\n[2] Data at {rebal_date.date()}')

available_prices = df_prices[df_prices['Date'] <= rebal_date].copy()
available_fins = df_fins[df_fins['DiscDate'] <= rebal_date].copy()

latest_prices = available_prices.sort_values('Date').groupby('Code').last().reset_index()
latest_prices = latest_prices[['Code', 'Price']].rename(columns={'Price': 'Close'})

latest_fins = available_fins.sort_values('DiscDate').groupby('Code').last().reset_index()

merged = latest_prices.merge(
    latest_fins[['Code', 'Profit', 'Equity', 'SharesOut']],
    on='Code',
    how='inner'
)

merged['Profit'] = pd.to_numeric(merged['Profit'], errors='coerce')
merged['Equity'] = pd.to_numeric(merged['Equity'], errors='coerce')
merged['SharesOut'] = pd.to_numeric(merged['SharesOut'], errors='coerce')

merged['MarketCap'] = merged['Close'] * merged['SharesOut']
merged['PBR'] = merged['MarketCap'] / merged['Equity']
merged['ROE'] = (merged['Profit'] / merged['Equity']) * 100

# Filter (same as backtest)
valid_data = merged[
    (merged['PBR'] > 0) &
    (merged['PBR'] < 50) &
    (merged['ROE'] > -100) &
    (merged['ROE'] < 100) &
    (merged['MarketCap'] > 1_000_000_000)
].copy()

print(f'  Valid data: {len(valid_data)} stocks')

# ROE statistics BEFORE quartile division
print(f'\n[3] ROE Distribution (before quartile division)')
print(f'  Mean: {valid_data["ROE"].mean():.2f}%')
print(f'  Median: {valid_data["ROE"].median():.2f}%')
print(f'  Min: {valid_data["ROE"].min():.2f}%')
print(f'  Max: {valid_data["ROE"].max():.2f}%')
print(f'  Std: {valid_data["ROE"].std():.2f}%')

# Count by sign
n_positive = (valid_data['ROE'] > 0).sum()
n_negative = (valid_data['ROE'] < 0).sum()
n_zero = (valid_data['ROE'] == 0).sum()

print(f'\n  ROE > 0: {n_positive} ({n_positive/len(valid_data)*100:.1f}%)')
print(f'  ROE < 0: {n_negative} ({n_negative/len(valid_data)*100:.1f}%)')
print(f'  ROE = 0: {n_zero} ({n_zero/len(valid_data)*100:.1f}%)')

# Percentiles
percentiles = [0, 5, 10, 25, 50, 75, 90, 95, 100]
print(f'\n[4] ROE Percentiles')
for p in percentiles:
    val = valid_data['ROE'].quantile(p/100)
    print(f'  {p:3d}%: {val:>8.2f}%')

# Now apply ranking and quartile (same as backtest)
print(f'\n[5] Applying Ranking and Quartile Division')
valid_data['PBR_Rank'] = valid_data['PBR'].rank(method='first', ascending=True)
valid_data['ROE_Rank'] = valid_data['ROE'].rank(method='first', ascending=False)

print(f'  PBR_Rank range: {valid_data["PBR_Rank"].min():.0f} ~ {valid_data["PBR_Rank"].max():.0f}')
print(f'  ROE_Rank range: {valid_data["ROE_Rank"].min():.0f} ~ {valid_data["ROE_Rank"].max():.0f}')

# Quartile division
valid_data['PBR_Quartile'] = pd.qcut(valid_data['PBR_Rank'], q=4, labels=[1, 2, 3, 4], duplicates='drop')
valid_data['ROE_Quartile'] = pd.qcut(valid_data['ROE_Rank'], q=4, labels=[1, 2, 3, 4], duplicates='drop')

# Check quartile boundaries
print(f'\n[6] Quartile Boundaries')

for q in [1, 2, 3, 4]:
    q_data = valid_data[valid_data['PBR_Quartile'] == q]
    if len(q_data) > 0:
        print(f'  PBR Q{q}: {q_data["PBR"].min():.4f} ~ {q_data["PBR"].max():.4f} (n={len(q_data)})')

print()
for q in [1, 2, 3, 4]:
    q_data = valid_data[valid_data['ROE_Quartile'] == q]
    if len(q_data) > 0:
        print(f'  ROE Q{q}: {q_data["ROE"].min():.2f}% ~ {q_data["ROE"].max():.2f}% (n={len(q_data)})')
        # CRITICAL: Check if Q4 contains negative values!
        if q == 4:
            n_neg_in_q4 = (q_data['ROE'] < 0).sum()
            if n_neg_in_q4 > 0:
                print(f'    ⚠️  WARNING: Q4 contains {n_neg_in_q4} negative ROE values!')

# Screening
print(f'\n[7] Screening: Low PBR (Q1) x High ROE (Q4)')
candidates = valid_data[
    (valid_data['PBR_Quartile'] == 1) &
    (valid_data['ROE_Quartile'] == 4)
].copy()

print(f'  Candidates: {len(candidates)} stocks')

if len(candidates) > 0:
    print(f'\n  Candidate ROE distribution:')
    print(f'    Mean: {candidates["ROE"].mean():.2f}%')
    print(f'    Median: {candidates["ROE"].median():.2f}%')
    print(f'    Min: {candidates["ROE"].min():.2f}%')
    print(f'    Max: {candidates["ROE"].max():.2f}%')

    n_neg_candidates = (candidates['ROE'] < 0).sum()
    print(f'    Negative ROE: {n_neg_candidates} ({n_neg_candidates/len(candidates)*100:.1f}%)')

    if n_neg_candidates > 0:
        print(f'\n  ⚠️  Negative ROE candidates:')
        neg_candidates = candidates[candidates['ROE'] < 0].sort_values('ROE')
        print(neg_candidates[['Code', 'PBR', 'ROE', 'PBR_Quartile', 'ROE_Quartile']].to_string(index=False))

# Save full distribution
output_path = OUTPUT_DIR / 'roe_distribution_2023.csv'
valid_data[['Code', 'PBR', 'ROE', 'MarketCap', 'PBR_Rank', 'ROE_Rank', 'PBR_Quartile', 'ROE_Quartile']].to_csv(output_path, index=False)
print(f'\n[8] Saved full distribution to: {output_path}')

print('\nCompleted')
