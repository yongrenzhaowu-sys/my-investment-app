# -*- coding: utf-8 -*-
"""
October Rebalance Strategy - 2017-2025 (9 years)
Using curated data (same as legacy version)
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Path setup
PROJECT_ROOT = Path('C:/Users/yongr/claude project/workspace')
PRICES_PATH = PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet'
FINS_PATH = PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet'
OUTPUT_DIR = Path('results')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print('='*80)
print('October Rebalance Strategy - 2017-2025 (9 years)')
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
df_prices = pd.read_parquet(PRICES_PATH)
df_fins = pd.read_parquet(FINS_PATH)

print(f'  Prices: {len(df_prices):,} records')
print(f'  Financials: {len(df_fins):,} records')

# Date conversion
df_prices['date'] = pd.to_datetime(df_prices['date'])
df_fins['disclosed_date'] = pd.to_datetime(df_fins['disclosed_date'])

# Code standardization (4 digits)
df_prices['code'] = df_prices['code'].astype(str).str[:4]
df_fins['code'] = df_fins['code'].astype(str).str[:4]

# Use adjusted_close (already calculated)
df_prices = df_prices.rename(columns={
    'date': 'Date',
    'code': 'Code',
    'open': 'O',
    'close': 'C',
    'adjusted_close': 'Price'
})

# Remove duplicates
df_prices = df_prices.sort_values(['Code', 'Date'], ascending=[True, True])
df_prices = df_prices.drop_duplicates(subset=['Code', 'Date'], keep='last')

print(f'  After deduplication: {len(df_prices):,} records')

# Rename financial columns
df_fins = df_fins.rename(columns={
    'disclosed_date': 'DiscDate',
    'code': 'Code',
    'net_profit': 'Profit',
    'equity': 'Equity',
    'bps': 'BPS',
    'total_assets': 'TA'
})

# Convert to numeric
for col in ['Profit', 'Equity', 'BPS', 'TA']:
    if col in df_fins.columns:
        df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

# Calculate shares outstanding from equity and BPS
df_fins['SharesOut'] = df_fins['Equity'] / df_fins['BPS']

print(f'  Financials after processing: {len(df_fins):,} records')

# Rebalance dates (2017-2025, 9 years)
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

print(f'\n[2] Rebalance Dates')
print(f'  Period: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}')
print(f'  N Rebalances: {len(rebalance_dates)}')

print('\n[3] Running Backtest')

annual_returns = []

for i in range(len(rebalance_dates) - 1):
    rebal_date = rebalance_dates[i]
    next_rebal_date = rebalance_dates[i + 1]

    print(f'\n  --- {rebal_date.date()} ---')

    # Available data at rebalance date
    available_prices = df_prices[df_prices['Date'] <= rebal_date].copy()
    available_fins = df_fins[df_fins['DiscDate'] <= rebal_date].copy()

    # Latest prices (closing price on rebalance date)
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

    # Ensure numeric types
    merged['Profit'] = pd.to_numeric(merged['Profit'], errors='coerce')
    merged['Equity'] = pd.to_numeric(merged['Equity'], errors='coerce')
    merged['SharesOut'] = pd.to_numeric(merged['SharesOut'], errors='coerce')

    # Calculate market cap, PBR, ROE
    merged['MarketCap'] = merged['Close'] * merged['SharesOut']
    merged['PBR'] = merged['MarketCap'] / merged['Equity']
    merged['ROE'] = (merged['Profit'] / merged['Equity']) * 100

    # Filter (same as legacy version)
    valid_data = merged[
        (merged['PBR'] > 0) &
        (merged['PBR'] < 50) &
        (merged['ROE'] > -100) &
        (merged['ROE'] < 100) &
        (merged['MarketCap'] > 1_000_000_000)
    ].copy()

    print(f'    Valid data: {len(valid_data)} stocks')

    if len(valid_data) < 100:
        print(f'    SKIP: Insufficient data (need 100+)')
        continue

    # Ranking (same as legacy)
    valid_data['PBR_Rank'] = valid_data['PBR'].rank(method='first', ascending=True)
    valid_data['ROE_Rank'] = valid_data['ROE'].rank(method='first', ascending=False)

    # Quartile division
    valid_data['PBR_Quartile'] = pd.qcut(valid_data['PBR_Rank'], q=4, labels=[1, 2, 3, 4], duplicates='drop')
    valid_data['ROE_Quartile'] = pd.qcut(valid_data['ROE_Rank'], q=4, labels=[1, 2, 3, 4], duplicates='drop')

    # Screening: Low PBR (Q1) x High ROE (Q4)
    candidates = valid_data[
        (valid_data['PBR_Quartile'] == 1) &
        (valid_data['ROE_Quartile'] == 4)
    ].copy()

    # Top 50 by lowest PBR
    candidates = candidates.nsmallest(50, 'PBR')

    print(f'    Candidates: {len(candidates)} stocks')

    if len(candidates) < TARGET_POSITIONS:
        print(f'    SKIP: Insufficient candidates (need {TARGET_POSITIONS})')
        continue

    # Portfolio construction (top 20, 100-share units, equal weight)
    selected = candidates.head(TARGET_POSITIONS).copy()
    capital_per_stock = INITIAL_CAPITAL / TARGET_POSITIONS

    portfolio = []
    for _, row in selected.iterrows():
        price = row['Close']
        shares = int(capital_per_stock / price / 100) * 100  # 100-share units
        if shares > 0:
            portfolio.append({
                'Code': row['Code'],
                'Shares': shares,
                'EntryPrice': price,
                'Amount': shares * price
            })

    portfolio_df = pd.DataFrame(portfolio)
    total_investment = portfolio_df['Amount'].sum()

    print(f'    Portfolio: {len(portfolio_df)} stocks')
    print(f'    Investment: {total_investment:,.0f} JPY ({total_investment/INITIAL_CAPITAL*100:.1f}%)')

    # Entry/Exit dates (next business day open price)
    entry_start = rebal_date + timedelta(days=1)
    exit_start = next_rebal_date + timedelta(days=1)

    # Find next business day
    entry_dates = df_prices[
        (df_prices['Date'] >= entry_start) &
        (df_prices['Date'] <= entry_start + timedelta(days=5))
    ]['Date'].unique()

    exit_dates = df_prices[
        (df_prices['Date'] >= exit_start) &
        (df_prices['Date'] <= exit_start + timedelta(days=5))
    ]['Date'].unique()

    if len(entry_dates) == 0 or len(exit_dates) == 0:
        print(f'    SKIP: Cannot find entry/exit dates')
        continue

    entry_date = min(entry_dates)
    exit_date = min(exit_dates)

    # Entry prices (open on entry date)
    entry_prices_data = df_prices[
        (df_prices['Date'] == entry_date) &
        (df_prices['Code'].isin(portfolio_df['Code']))
    ][['Code', 'O']].rename(columns={'O': 'EntryPriceActual'})

    # Exit prices (open on exit date)
    exit_prices_data = df_prices[
        (df_prices['Date'] == exit_date) &
        (df_prices['Code'].isin(portfolio_df['Code']))
    ][['Code', 'O']].rename(columns={'O': 'ExitPrice'})

    # Merge
    portfolio_df = portfolio_df.merge(entry_prices_data, on='Code', how='left')
    portfolio_df = portfolio_df.merge(exit_prices_data, on='Code', how='left')

    # Fill missing values with previous close price
    portfolio_df['EntryPriceActual'] = portfolio_df['EntryPriceActual'].fillna(portfolio_df['EntryPrice'])
    portfolio_df['ExitPrice'] = portfolio_df['ExitPrice'].fillna(portfolio_df['EntryPrice'])

    # Calculate returns
    portfolio_df['Return'] = (portfolio_df['ExitPrice'] / portfolio_df['EntryPriceActual']) - 1
    portfolio_df['PnL'] = portfolio_df['Shares'] * (portfolio_df['ExitPrice'] - portfolio_df['EntryPriceActual'])

    # Portfolio return (equal weight)
    portfolio_return_gross = portfolio_df['Return'].mean()

    # Tax (only on profits)
    total_pnl = portfolio_df['PnL'].sum()
    tax = max(0, total_pnl * TAX_RATE)
    portfolio_return_net = (total_pnl - tax) / total_investment

    print(f'    Entry: {entry_date.date()}')
    print(f'    Exit: {exit_date.date()}')
    print(f'    Gross Return: {portfolio_return_gross*100:.2f}%')
    print(f'    Net Return (after tax): {portfolio_return_net*100:.2f}%')
    print(f'    Tax: {tax:,.0f} JPY')

    # Record
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

# Results
annual_returns_df = pd.DataFrame(annual_returns)

print(f'\n[4] Backtest Results')
print(f'  N Rebalances: {len(annual_returns_df)}')

if len(annual_returns_df) == 0:
    print('ERROR: Backtest failed (insufficient data)')
    exit(1)

# Performance metrics
net_returns = annual_returns_df['NetReturn'].values
cumulative_return = (np.prod(1 + net_returns) - 1) * 100
n_years = len(net_returns)
annual_return = ((1 + cumulative_return/100) ** (1/n_years) - 1) * 100
annual_volatility = np.std(net_returns) * 100
sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0

# Max drawdown
cumulative_series = np.cumprod(1 + net_returns)
running_max = np.maximum.accumulate(cumulative_series)
drawdown = (cumulative_series / running_max) - 1
max_drawdown = np.min(drawdown) * 100

# Win rate
win_rate = (net_returns > 0).sum() / len(net_returns) * 100

print(f'\n[5] Performance Metrics (after tax)')
print(f'  Cumulative Return: {cumulative_return:.2f}%')
print(f'  Annual Return: {annual_return:.2f}%')
print(f'  Annual Volatility: {annual_volatility:.2f}%')
print(f'  Sharpe Ratio: {sharpe_ratio:.2f}%')
print(f'  Max Drawdown: {max_drawdown:.2f}%')
print(f'  Win Rate: {win_rate:.1f}% ({(net_returns > 0).sum()}/{len(net_returns)})')

# Save results
annual_returns_path = OUTPUT_DIR / 'annual_returns_2017_2025.csv'
annual_returns_df.to_csv(annual_returns_path, index=False)
print(f'\n[6] Saved')
print(f'  Annual returns: {annual_returns_path}')

# Summary
summary = {
    'Strategy': 'October_Rebalance_2017_2025',
    'Period': f'{annual_returns_df["RebalanceDate"].min().date()} ~ {annual_returns_df["RebalanceDate"].max().date()}',
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
summary_path = OUTPUT_DIR / 'performance_summary_2017_2025.csv'
summary_df.to_csv(summary_path, index=False)
print(f'  Summary: {summary_path}')

# Annual returns detail
print(f'\n[7] Annual Returns Detail')
for _, row in annual_returns_df.iterrows():
    print(f'  {row["Year"]}: {row["NetReturn"]*100:>6.2f}% ({row["N_Stocks"]} stocks, tax {row["Tax"]:,.0f} JPY)')

print('\nCompleted')
