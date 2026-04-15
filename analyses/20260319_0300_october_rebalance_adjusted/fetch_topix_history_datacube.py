# -*- coding: utf-8 -*-
"""
TOPIX Constituent History Fetcher - DataCube + Fallback

目的：月末時点のTOPIX構成銘柄スナップショットを取得し、生存バイアスを排除した
    時系列分析を可能にする。

データソース優先順位：
1. J-Quants DataCube "Master of Index" (月次スナップショット、2015-11～)
2. フォールバック：時価総額上位2,000銘柄（各時点で計算）

成果物：
- month_end_membership.parquet: 月末構成銘柄テーブル
- daily_membership.parquet: 日次メンバーシップ（forward-fill）
- data_quality_report.txt: データ品質チェック結果

要件：
- 再実行可能（キャッシュ機能）
- 環境変数から認証情報読み込み
- データ品質チェック（銘柄数推移、重複、最新月との整合性）
"""

import os
import pandas as pd
import numpy as np
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta
import time
from typing import List, Dict, Tuple

# =============================================================================
# Configuration
# =============================================================================

PROJECT_ROOT = Path('C:/Users/yongr/claude project/workspace')
CACHE_DIR = PROJECT_ROOT / 'data/processed/topix_history'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = Path('results')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# J-Quants API credentials (from environment)
API_KEY = os.environ.get('JQUANTS_API_KEY', '')

# Target period (5 years back from now)
END_DATE = datetime.now()
START_DATE = END_DATE - timedelta(days=365*5)

# DataCube base URL
DATACUBE_BASE_URL = 'https://dc.jpx-jquants.com/en/product/master_of_index_topix_{yyyymm}'

print('='*80)
print('TOPIX Constituent History Fetcher')
print('='*80)
print(f'Target period: {START_DATE.strftime("%Y-%m")} ~ {END_DATE.strftime("%Y-%m")}')
print(f'Cache directory: {CACHE_DIR}')

# =============================================================================
# Method 1: J-Quants DataCube (Primary)
# =============================================================================

def fetch_datacube_topix(year: int, month: int) -> pd.DataFrame:
    """
    Fetch TOPIX constituents from J-Quants DataCube for a specific month

    Returns:
        DataFrame with columns: [yyyymm, date_month_end, code, isin, weight, ...]
        Empty DataFrame if failed
    """
    yyyymm = f'{year:04d}{month:02d}'
    cache_file = CACHE_DIR / f'datacube_{yyyymm}.parquet'

    # Check cache
    if cache_file.exists():
        print(f'  [Cache] {yyyymm}')
        return pd.read_parquet(cache_file)

    print(f'  [Fetch] {yyyymm}...', end='')

    # DataCube URL format (need to verify actual URL structure)
    url = DATACUBE_BASE_URL.format(yyyymm=yyyymm)

    try:
        # Note: DataCube might require different authentication or download process
        # This is a placeholder - actual implementation depends on DataCube access method
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            # Parse response (format depends on DataCube response type)
            # Placeholder: assume CSV format
            df = pd.read_csv(pd.io.common.BytesIO(response.content))

            # Standardize columns
            if 'Code' in df.columns or 'code' in df.columns:
                df['code'] = df.get('Code', df.get('code', '')).astype(str).str[:4]
                df['yyyymm'] = yyyymm

                # Infer month-end date (last business day of month)
                last_day = pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0)
                df['date_month_end'] = last_day

                # Save to cache
                df.to_parquet(cache_file)
                print(f' OK ({len(df)} stocks)')
                return df
            else:
                print(' FAILED (no Code column)')
                return pd.DataFrame()
        else:
            print(f' FAILED (HTTP {response.status_code})')
            return pd.DataFrame()

    except Exception as e:
        print(f' FAILED ({str(e)[:50]})')
        return pd.DataFrame()

# =============================================================================
# Method 2: Market Cap Proxy (Fallback)
# =============================================================================

def calculate_marketcap_proxy_topix(
    prices_df: pd.DataFrame,
    fins_df: pd.DataFrame,
    target_date: pd.Timestamp,
    top_n: int = 2000
) -> List[str]:
    """
    Calculate TOPIX proxy using top N stocks by market cap at target_date

    Args:
        prices_df: Price data
        fins_df: Financial data
        target_date: Target date for membership
        top_n: Number of top stocks (default: 2000)

    Returns:
        List of stock codes (4-digit strings)
    """
    cache_file = CACHE_DIR / f'marketcap_proxy_{target_date.strftime("%Y%m%d")}.json'

    # Check cache
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            return json.load(f)['codes']

    # Filter data available at target_date
    available_prices = prices_df[prices_df['Date'] <= target_date].copy()
    available_fins = fins_df[fins_df['DiscDate'] <= target_date].copy()

    # Latest prices
    latest_prices = available_prices.sort_values('Date').groupby('Code').last().reset_index()
    latest_prices = latest_prices[['Code', 'Price']]

    # Latest financials
    latest_fins = available_fins.sort_values('DiscDate').groupby('Code').last().reset_index()
    latest_fins = latest_fins[['Code', 'Equity', 'BPS']]

    # Merge
    merged = latest_prices.merge(latest_fins, on='Code', how='inner')

    # Convert to numeric
    merged['Equity'] = pd.to_numeric(merged['Equity'], errors='coerce')
    merged['BPS'] = pd.to_numeric(merged['BPS'], errors='coerce')
    merged['Price'] = pd.to_numeric(merged['Price'], errors='coerce')

    # Calculate market cap
    merged['SharesOut'] = merged['Equity'] / merged['BPS']
    merged['MarketCap'] = merged['Price'] * merged['SharesOut']

    # Filter valid
    merged = merged[
        (merged['MarketCap'] > 0) &
        (merged['MarketCap'].notna())
    ].copy()

    # Sort by market cap descending
    merged = merged.sort_values('MarketCap', ascending=False)

    # Top N
    topix_proxy = merged.head(top_n)['Code'].tolist()

    # Save to cache
    with open(cache_file, 'w') as f:
        json.dump({
            'date': target_date.strftime('%Y-%m-%d'),
            'method': 'marketcap_proxy',
            'top_n': top_n,
            'codes': topix_proxy
        }, f)

    return topix_proxy

# =============================================================================
# Main Processing
# =============================================================================

def generate_month_end_dates(start_date: datetime, end_date: datetime) -> List[pd.Timestamp]:
    """Generate list of month-end dates between start and end"""
    dates = pd.date_range(start=start_date, end=end_date, freq='M')
    return [pd.Timestamp(d) for d in dates]

def main():
    print('\n[1] Attempting DataCube Method (Primary)')
    print('-' * 80)

    # Generate target months
    month_ends = generate_month_end_dates(START_DATE, END_DATE)
    print(f'Target months: {len(month_ends)}')

    datacube_results = []
    for month_end in month_ends:
        year, month = month_end.year, month_end.month
        df = fetch_datacube_topix(year, month)
        if len(df) > 0:
            datacube_results.append(df)
        time.sleep(0.5)  # Rate limiting

    datacube_success = len(datacube_results) > 0

    if datacube_success:
        print(f'\n✅ DataCube Success: {len(datacube_results)}/{len(month_ends)} months')
        month_end_membership = pd.concat(datacube_results, ignore_index=True)
    else:
        print('\n⚠️  DataCube Failed: Switching to Fallback Method')
        print('-' * 80)
        print('[2] Fallback: Market Cap Proxy (Top 2,000 stocks)')
        print('-' * 80)

        # Load price and financial data
        print('Loading data...')
        PRICES_PATH = PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet'
        FINS_PATH = PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet'

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

        df_fins = df_fins.rename(columns={
            'disclosed_date': 'DiscDate',
            'code': 'Code',
            'equity': 'Equity',
            'bps': 'BPS'
        })

        # Remove duplicates
        df_prices = df_prices.sort_values(['Code', 'Date']).drop_duplicates(['Code', 'Date'], keep='last')

        print(f'  Prices: {len(df_prices):,} records')
        print(f'  Financials: {len(df_fins):,} records')

        # Calculate for each month-end
        fallback_results = []
        for month_end in month_ends:
            print(f'  {month_end.strftime("%Y-%m")}: ', end='')
            codes = calculate_marketcap_proxy_topix(df_prices, df_fins, month_end, top_n=2000)
            print(f'{len(codes)} stocks')

            fallback_results.append({
                'yyyymm': month_end.strftime('%Y%m'),
                'date_month_end': month_end,
                'codes': codes,
                'n_stocks': len(codes)
            })

        # Convert to DataFrame
        rows = []
        for result in fallback_results:
            for code in result['codes']:
                rows.append({
                    'yyyymm': result['yyyymm'],
                    'date_month_end': result['date_month_end'],
                    'code': code,
                    'method': 'marketcap_proxy'
                })

        month_end_membership = pd.DataFrame(rows)

    # =============================================================================
    # Data Quality Checks
    # =============================================================================

    print('\n[3] Data Quality Checks')
    print('-' * 80)

    quality_report = []

    # Check 1: Monthly constituent count trend
    print('Check 1: Monthly constituent count')
    monthly_counts = month_end_membership.groupby('yyyymm').size().reset_index(name='count')
    print(monthly_counts.to_string(index=False))

    # Check for sudden changes (>20% month-over-month)
    monthly_counts['pct_change'] = monthly_counts['count'].pct_change() * 100
    sudden_changes = monthly_counts[abs(monthly_counts['pct_change']) > 20]
    if len(sudden_changes) > 0:
        quality_report.append('⚠️  WARNING: Sudden changes in constituent count:')
        quality_report.append(sudden_changes.to_string(index=False))
    else:
        quality_report.append('✅ No sudden changes in constituent count')

    # Check 2: Duplicate codes within same month
    print('\nCheck 2: Duplicate codes')
    duplicates = month_end_membership.groupby(['yyyymm', 'code']).size().reset_index(name='count')
    duplicates = duplicates[duplicates['count'] > 1]
    if len(duplicates) > 0:
        quality_report.append(f'⚠️  WARNING: {len(duplicates)} duplicate code-month pairs')
        quality_report.append(duplicates.head(10).to_string(index=False))
    else:
        quality_report.append('✅ No duplicate codes within same month')
        print('  ✅ No duplicates')

    # Check 3: Compare latest month with JPX official data
    print('\nCheck 3: Compare with JPX official data (latest month)')
    try:
        # Download latest TOPIX weight file
        jpx_url = 'https://www.jpx.co.jp/automation/markets/indices/topix/files/topixweight_j.csv'
        response = requests.get(jpx_url, timeout=30)

        if response.status_code == 200:
            # Parse CSV (encoding might be Shift-JIS)
            from io import StringIO
            jpx_df = pd.read_csv(StringIO(response.content.decode('shift-jis', errors='ignore')))

            # Extract codes (column name might vary)
            code_col = [c for c in jpx_df.columns if 'コード' in c or 'Code' in c or 'code' in c]
            if len(code_col) > 0:
                jpx_codes = set(jpx_df[code_col[0]].astype(str).str[:4].unique())

                # Our latest month
                latest_yyyymm = month_end_membership['yyyymm'].max()
                our_codes = set(month_end_membership[month_end_membership['yyyymm'] == latest_yyyymm]['code'].unique())

                # Compare
                only_in_jpx = jpx_codes - our_codes
                only_in_ours = our_codes - jpx_codes
                overlap = jpx_codes & our_codes

                overlap_pct = len(overlap) / len(jpx_codes) * 100

                print(f'  JPX official: {len(jpx_codes)} stocks')
                print(f'  Our data ({latest_yyyymm}): {len(our_codes)} stocks')
                print(f'  Overlap: {len(overlap)} stocks ({overlap_pct:.1f}%)')
                print(f'  Only in JPX: {len(only_in_jpx)} stocks')
                print(f'  Only in ours: {len(only_in_ours)} stocks')

                if overlap_pct >= 90:
                    quality_report.append(f'✅ High overlap with JPX official data ({overlap_pct:.1f}%)')
                else:
                    quality_report.append(f'⚠️  WARNING: Low overlap with JPX official data ({overlap_pct:.1f}%)')
                    if len(only_in_jpx) > 0:
                        quality_report.append(f'  Only in JPX (sample): {list(only_in_jpx)[:10]}')
            else:
                quality_report.append('⚠️  Cannot find code column in JPX data')
        else:
            quality_report.append(f'⚠️  Cannot download JPX data (HTTP {response.status_code})')

    except Exception as e:
        quality_report.append(f'⚠️  JPX comparison failed: {str(e)[:100]}')

    # =============================================================================
    # Save Results
    # =============================================================================

    print('\n[4] Saving Results')
    print('-' * 80)

    # (A) Month-end membership table
    output_membership = OUTPUT_DIR / 'month_end_membership.parquet'
    month_end_membership.to_parquet(output_membership, index=False)
    print(f'✅ Saved: {output_membership}')
    print(f'   Rows: {len(month_end_membership):,}')
    print(f'   Columns: {month_end_membership.columns.tolist()}')

    # (B) Daily membership (forward-fill)
    print('\nGenerating daily membership (forward-fill)...')

    # Get all trading days from price data
    if 'df_prices' in locals():
        trading_days = sorted(df_prices['Date'].unique())
        trading_days = [d for d in trading_days if START_DATE <= d <= END_DATE]
    else:
        # Generate business days
        trading_days = pd.date_range(start=START_DATE, end=END_DATE, freq='B')

    # Forward-fill: each day uses the most recent month-end membership
    daily_rows = []
    month_end_membership['date_month_end'] = pd.to_datetime(month_end_membership['date_month_end'])

    for day in trading_days:
        # Find most recent month-end <= day
        valid_months = month_end_membership[month_end_membership['date_month_end'] <= day]
        if len(valid_months) > 0:
            latest_month = valid_months['date_month_end'].max()
            codes = valid_months[valid_months['date_month_end'] == latest_month]['code'].unique()

            for code in codes:
                daily_rows.append({
                    'date': day,
                    'code': code,
                    'source_month_end': latest_month
                })

    daily_membership = pd.DataFrame(daily_rows)
    output_daily = OUTPUT_DIR / 'daily_membership.parquet'
    daily_membership.to_parquet(output_daily, index=False)
    print(f'✅ Saved: {output_daily}')
    print(f'   Rows: {len(daily_membership):,}')
    print(f'   Trading days: {len(trading_days):,}')

    # (C) Quality report
    output_report = OUTPUT_DIR / 'data_quality_report.txt'
    with open(output_report, 'w', encoding='utf-8') as f:
        f.write('='*80 + '\n')
        f.write('TOPIX Constituent Data Quality Report\n')
        f.write('='*80 + '\n\n')
        f.write(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'Period: {START_DATE.strftime("%Y-%m")} ~ {END_DATE.strftime("%Y-%m")}\n')
        f.write(f'Method: {"DataCube" if datacube_success else "Market Cap Proxy"}\n\n')
        f.write('\n'.join(quality_report))

    print(f'✅ Saved: {output_report}')

    # =============================================================================
    # Usage Guide
    # =============================================================================

    print('\n[5] Usage Guide for Survivorship Bias Avoidance')
    print('='*80)
    print("""
To use this data in your backtest and avoid survivorship bias:

1. Load the daily membership table:
   daily_membership = pd.read_parquet('results/daily_membership.parquet')

2. For each rebalancing date t, filter to TOPIX constituents at that date:
   topix_codes_at_t = daily_membership[daily_membership['date'] == t]['code'].unique()

3. Apply filter to your stock universe:
   valid_stocks = all_stocks[all_stocks['Code'].isin(topix_codes_at_t)]

4. Perform screening (PBR, ROE, etc.) only on valid_stocks

Example (pseudo-code):
   for rebal_date in rebalance_dates:
       # Get TOPIX constituents at this date
       topix_at_date = daily_membership[daily_membership['date'] <= rebal_date]
       latest_month = topix_at_date['source_month_end'].max()
       topix_codes = topix_at_date[topix_at_date['source_month_end'] == latest_month]['code'].unique()

       # Filter universe
       universe = all_stocks[all_stocks['Code'].isin(topix_codes)]

       # Screen
       candidates = universe[(universe['PBR_Q'] == 1) & (universe['ROE_Q'] == 1)]

       # ... rest of backtest
""")

    print('\n✅ Completed')
    print('='*80)

if __name__ == '__main__':
    main()
