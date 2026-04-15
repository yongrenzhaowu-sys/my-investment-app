# -*- coding: utf-8 -*-
"""
Fetch TOPIX Constituent History from J-Quants API

Fetches historical TOPIX constituent data for each rebalancing date
to avoid survivorship bias in backtesting.
"""
import os
import pandas as pd
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta
import time

PROJECT_ROOT = Path('C:/Users/yongr/claude project/workspace')
CACHE_DIR = PROJECT_ROOT / 'data/processed/topix_constituents'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Get API key from environment
API_KEY = os.environ.get('JQUANTS_API_KEY')
if not API_KEY:
    print('ERROR: JQUANTS_API_KEY not found in environment variables')
    exit(1)

print('='*80)
print('Fetching TOPIX Constituent History from J-Quants API')
print('='*80)

# Rebalance dates (2017-2025)
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

print(f'\nRebalancing dates: {len(rebalance_dates)} dates')
print(f'Period: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}')

# API endpoint for TOPIX constituents
# J-Quants API v2: /v2/indices/{index_code}/constituents
# TOPIX code might be "0000" or similar
BASE_URL = 'https://api.jquants.com'
HEADERS = {'x-api-key': API_KEY}

def fetch_topix_constituents(date):
    """
    Fetch TOPIX constituents as of the given date

    Returns: list of stock codes (4-digit strings)
    """
    cache_file = CACHE_DIR / f'topix_{date.strftime("%Y%m%d")}.json'

    # Check cache first
    if cache_file.exists():
        print(f'  Loading from cache: {cache_file.name}')
        with open(cache_file, 'r') as f:
            data = json.load(f)
        return data['codes']

    # Fetch from API
    # Try different endpoints/approaches

    # Approach 1: Try /v2/listed/info endpoint which might have index membership
    print(f'  Fetching from API (date: {date.date()})...')

    # Get all listed stocks with their info
    url = f'{BASE_URL}/v2/listed/info'
    params = {'date': date.strftime('%Y-%m-%d')}

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if 'info' in data:
            # Filter for TOPIX constituents
            # The API might have a field like 'topix_weight' or 'indices' that includes TOPIX
            topix_codes = []
            for stock in data['info']:
                # Check if stock is in TOPIX
                # This field name might vary - we'll need to inspect the response
                if 'topix_weight' in stock and stock['topix_weight'] is not None:
                    code = str(stock.get('Code', stock.get('code', '')))[:4]
                    if code:
                        topix_codes.append(code)

            if len(topix_codes) > 0:
                print(f'    Found {len(topix_codes)} TOPIX constituents')
                # Save to cache
                with open(cache_file, 'w') as f:
                    json.dump({'date': date.strftime('%Y-%m-%d'), 'codes': topix_codes}, f)
                return topix_codes

        print(f'    WARNING: Could not extract TOPIX constituents from response')
        print(f'    Response keys: {list(data.keys())}')
        if 'info' in data and len(data['info']) > 0:
            print(f'    Sample stock fields: {list(data["info"][0].keys())}')

    except Exception as e:
        print(f'    ERROR: {e}')

    # Approach 2: Use market cap as proxy (TOPIX = First Section stocks)
    # This is not perfect but better than nothing
    print(f'    Fallback: Using First Section stocks as TOPIX proxy')

    try:
        url = f'{BASE_URL}/v2/listed/info'
        params = {'date': date.strftime('%Y-%m-%d')}
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if 'info' in data:
            topix_codes = []
            for stock in data['info']:
                # First Section (市場区分: 東証一部) stocks
                market_section = stock.get('MarketCode', stock.get('Section', ''))
                if market_section in ['0111', 'Prime', '東証一部', 'TSE1']:
                    code = str(stock.get('Code', stock.get('code', '')))[:4]
                    if code:
                        topix_codes.append(code)

            if len(topix_codes) > 0:
                print(f'    Found {len(topix_codes)} First Section stocks (TOPIX proxy)')
                # Save to cache
                with open(cache_file, 'w') as f:
                    json.dump({'date': date.strftime('%Y-%m-%d'), 'codes': topix_codes, 'note': 'First Section proxy'}, f)
                return topix_codes

    except Exception as e:
        print(f'    ERROR: {e}')

    return []

# Fetch for all rebalancing dates
all_constituents = {}

for date in rebalance_dates:
    print(f'\n[{date.date()}]')
    codes = fetch_topix_constituents(date)
    all_constituents[date.strftime('%Y-%m-%d')] = codes

    # Rate limiting
    time.sleep(1)

# Save combined file
combined_file = CACHE_DIR / 'topix_constituents_history.json'
with open(combined_file, 'w') as f:
    json.dump(all_constituents, f, indent=2)

print(f'\n[Summary]')
print(f'  Fetched constituents for {len(all_constituents)} dates')
for date_str, codes in all_constituents.items():
    print(f'    {date_str}: {len(codes)} stocks')

print(f'\n  Saved to: {combined_file}')
print('\nCompleted')
