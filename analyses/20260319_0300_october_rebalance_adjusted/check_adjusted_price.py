# -*- coding: utf-8 -*-
"""
Check if adjusted_close in curated data is correctly calculated
"""
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path('C:/Users/yongr/claude project/workspace')
PRICES_PATH = PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet'

print('='*80)
print('Checking adjusted_close calculation in curated data')
print('='*80)

df = pd.read_parquet(PRICES_PATH)
df['date'] = pd.to_datetime(df['date'])

print(f'\nTotal records: {len(df):,}')
print(f'Date range: {df["date"].min().date()} ~ {df["date"].max().date()}')
print(f'\nColumns: {df.columns.tolist()}')

# Check records where adjustment_factor != 1.0
adj_df = df[df['adjustment_factor'] != 1.0].head(20)
print(f'\n[1] Records where adjustment_factor != 1.0 (first 20):')
print(adj_df[['code', 'date', 'close', 'adjusted_close', 'adjustment_factor']].to_string())

# Verify the formula: adjusted_close = close * adjustment_factor
adj_df['calculated'] = adj_df['close'] * adj_df['adjustment_factor']
adj_df['diff'] = abs(adj_df['calculated'] - adj_df['adjusted_close'])
adj_df['match'] = adj_df['diff'] < 0.01

print(f'\n[2] Verifying formula: adjusted_close = close * adjustment_factor')
print(adj_df[['code', 'close', 'adjustment_factor', 'adjusted_close', 'calculated', 'match']].to_string())

match_rate = adj_df['match'].sum() / len(adj_df) * 100
print(f'\nMatch rate: {match_rate:.1f}%')

# Check if adjusted_close = close when adjustment_factor = 1.0
no_adj_df = df[df['adjustment_factor'] == 1.0].head(20)
no_adj_df['match'] = abs(no_adj_df['close'] - no_adj_df['adjusted_close']) < 0.01
print(f'\n[3] When adjustment_factor = 1.0, is adjusted_close = close?')
print(no_adj_df[['code', 'close', 'adjusted_close', 'adjustment_factor', 'match']].head(10).to_string())

no_adj_match_rate = no_adj_df['match'].sum() / len(no_adj_df) * 100
print(f'\nMatch rate (no adjustment): {no_adj_match_rate:.1f}%')

# Check a specific problematic case from earlier
print(f'\n[4] Check code 13010 on 2016-01-15:')
specific = df[(df['code'] == '13010') & (df['date'] == '2016-01-15')]
if len(specific) > 0:
    row = specific.iloc[0]
    print(f"  close: {row['close']}")
    print(f"  adjusted_close: {row['adjusted_close']}")
    print(f"  adjustment_factor: {row['adjustment_factor']}")
    print(f"  Expected (close * factor): {row['close'] * row['adjustment_factor']}")
    print(f"  Match: {abs(row['close'] * row['adjustment_factor'] - row['adjusted_close']) < 0.01}")
else:
    print("  Not found")

print('\nConclusion:')
if match_rate > 99 and no_adj_match_rate < 50:
    print('  adjusted_close is correctly calculated as close * adjustment_factor')
    print('  The curated data is CORRECT - we can use adjusted_close directly')
elif match_rate < 50:
    print('  adjusted_close does NOT follow the formula close * adjustment_factor')
    print('  We need to manually calculate AdjC_Correct = close * adjustment_factor')
else:
    print('  Results are mixed - need further investigation')

print('\nCompleted')
