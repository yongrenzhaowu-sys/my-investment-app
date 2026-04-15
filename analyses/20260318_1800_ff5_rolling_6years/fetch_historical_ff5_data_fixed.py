"""
5年間の歴史的データを取得（2021-03～2026-03）

修正版: 正しいAPIパラメータ使用（date指定、1日ずつ取得）
推定所要時間: 約50〜60分（営業日約1,250日）
"""
import pandas as pd
import numpy as np
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
import requests

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
EXISTING_DATA_DIR = PROJECT_ROOT / "data/processed/jquants_latest_full"
OUTPUT_DIR = PROJECT_ROOT / "data/processed/jquants_historical_6years"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# J-Quants API設定
API_KEY = os.environ.get('JQUANTS_API_KEY')
if not API_KEY:
    raise ValueError("環境変数 JQUANTS_API_KEY が設定されていません")

BASE_URL = "https://api.jquants.com/v2"

print("="*80)
print("FF5ファクター長期データ取得（2021-03～2026-03、5年間）")
print("="*80)

# ヘッダー設定
headers = {
    'x-api-key': API_KEY
}

def generate_business_days(start_date, end_date):
    """営業日リスト生成（土日を除外）"""
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # 月曜～金曜
            dates.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)
    return dates

def fetch_daily_bars(date):
    """株価データ取得（1日分）"""
    url = f"{BASE_URL}/equities/bars/daily"
    params = {'date': date}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=60)

        if response.status_code == 429:
            print(f"  [WARNING] レート制限（429）。60秒待機...")
            time.sleep(60)
            response = requests.get(url, headers=headers, params=params, timeout=60)

        response.raise_for_status()
        data = response.json()

        if 'data' in data and len(data['data']) > 0:
            return pd.DataFrame(data['data'])
    except Exception as e:
        print(f"  [ERROR] {date}: {e}")

    return pd.DataFrame()

def fetch_financials(date):
    """財務データ取得（1日分）"""
    url = f"{BASE_URL}/fins/summary"
    params = {'date': date}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=60)

        if response.status_code == 429:
            print(f"  [WARNING] レート制限（429）。60秒待機...")
            time.sleep(60)
            response = requests.get(url, headers=headers, params=params, timeout=60)

        response.raise_for_status()
        data = response.json()

        if 'data' in data and len(data['data']) > 0:
            return pd.DataFrame(data['data'])
    except Exception as e:
        print(f"  [ERROR] {date}: {e}")

    return pd.DataFrame()

# 既存データ読み込み
print("\n[1] 既存データ読み込み")
existing_prices = pd.read_parquet(EXISTING_DATA_DIR / "daily_bars_full.parquet")
existing_fins = pd.read_parquet(EXISTING_DATA_DIR / "financials_full.parquet")

print(f"  既存株価: {len(existing_prices):,}レコード")
print(f"  期間: {existing_prices['Date'].min()} ~ {existing_prices['Date'].max()}")
print(f"  既存財務: {len(existing_fins):,}レコード")
print(f"  期間: {existing_fins['DiscDate'].min()} ~ {existing_fins['DiscDate'].max()}")

# 取得期間設定
print("\n[2] 取得期間設定")
start_date = datetime(2021, 3, 1)
end_date = datetime(2025, 3, 2)  # 既存データの前日まで

print(f"  取得期間: {start_date.date()} ~ {end_date.date()}")

# 営業日リスト生成
business_days = generate_business_days(start_date, end_date)
print(f"  営業日数: {len(business_days)}日")
print(f"  推定所要時間: 約{len(business_days) // 60 + 1}分 x 2（株価+財務） = 約{(len(business_days) // 60 + 1) * 2}分")

# 株価データ取得
print("\n[3] 株価データ取得（5年間）")
all_prices = []
request_count = 0
start_time = time.time()

for i, date in enumerate(business_days, 1):
    if i % 10 == 0 or i == 1:
        elapsed = time.time() - start_time
        remaining = (len(business_days) - i) * (elapsed / i if i > 0 else 1)
        print(f"  [{i}/{len(business_days)}] {date[:4]}-{date[4:6]}-{date[6:8]} (残り約{remaining/60:.1f}分)...", end='', flush=True)

    df = fetch_daily_bars(date)

    if len(df) > 0:
        all_prices.append(df)
        if i % 10 == 0 or i == 1:
            print(f" OK {len(df):,}レコード")
    else:
        if i % 10 == 0 or i == 1:
            print(" スキップ")

    request_count += 1
    time.sleep(1)  # 1秒待機

    # 100リクエストごとに60秒休止
    if request_count % 100 == 0:
        print(f"  [休止] 100リクエスト到達、60秒待機...")
        time.sleep(60)

# 株価データ結合
if len(all_prices) > 0:
    df_prices_historical = pd.concat(all_prices, ignore_index=True)
    print(f"\n  取得完了: {len(df_prices_historical):,}レコード")
else:
    df_prices_historical = pd.DataFrame()
    print("\n  取得失敗: データなし")

# 財務データ取得
print("\n[4] 財務データ取得（5年間）")
all_fins = []
request_count = 0
start_time = time.time()

for i, date in enumerate(business_days, 1):
    if i % 10 == 0 or i == 1:
        elapsed = time.time() - start_time
        remaining = (len(business_days) - i) * (elapsed / i if i > 0 else 1)
        print(f"  [{i}/{len(business_days)}] {date[:4]}-{date[4:6]}-{date[6:8]} (残り約{remaining/60:.1f}分)...", end='', flush=True)

    df = fetch_financials(date)

    if len(df) > 0:
        all_fins.append(df)
        if i % 10 == 0 or i == 1:
            print(f" OK {len(df):,}レコード")
    else:
        if i % 10 == 0 or i == 1:
            print(" スキップ")

    request_count += 1
    time.sleep(1)  # 1秒待機

    # 100リクエストごとに60秒休止
    if request_count % 100 == 0:
        print(f"  [休止] 100リクエスト到達、60秒待機...")
        time.sleep(60)

# 財務データ結合
if len(all_fins) > 0:
    df_fins_historical = pd.concat(all_fins, ignore_index=True)
    print(f"\n  取得完了: {len(df_fins_historical):,}レコード")
else:
    df_fins_historical = pd.DataFrame()
    print("\n  取得失敗: データなし")

# 既存データとマージ
print("\n[5] データマージ")

# 株価データマージ
if len(df_prices_historical) > 0:
    df_prices_all = pd.concat([df_prices_historical, existing_prices], ignore_index=True)
    df_prices_all = df_prices_all.drop_duplicates(subset=['Code', 'Date'], keep='last')
    df_prices_all = df_prices_all.sort_values(['Code', 'Date'])
    print(f"  株価データ: {len(df_prices_all):,}レコード（重複削除後）")
else:
    df_prices_all = existing_prices
    print(f"  株価データ: {len(df_prices_all):,}レコード（既存データのみ）")

# 財務データマージ
if len(df_fins_historical) > 0:
    df_fins_all = pd.concat([df_fins_historical, existing_fins], ignore_index=True)
    df_fins_all = df_fins_all.drop_duplicates(subset=['Code', 'DiscDate'], keep='last')
    df_fins_all = df_fins_all.sort_values(['Code', 'DiscDate'])
    print(f"  財務データ: {len(df_fins_all):,}レコード（重複削除後）")
else:
    df_fins_all = existing_fins
    print(f"  財務データ: {len(df_fins_all):,}レコード（既存データのみ）")

# 保存
print("\n[6] データ保存")
prices_path = OUTPUT_DIR / "daily_bars_2021_2026.parquet"
fins_path = OUTPUT_DIR / "financials_2021_2026.parquet"

df_prices_all.to_parquet(prices_path, index=False)
print(f"  株価データ: {prices_path}")

df_fins_all.to_parquet(fins_path, index=False)
print(f"  財務データ: {fins_path}")

# サマリー
print("\n[7] サマリー")
print("="*80)
df_prices_all['Date'] = pd.to_datetime(df_prices_all['Date'])
df_fins_all['DiscDate'] = pd.to_datetime(df_fins_all['DiscDate'])

print(f"株価データ:")
print(f"  総レコード数: {len(df_prices_all):,}")
print(f"  銘柄数: {df_prices_all['Code'].nunique()}")
print(f"  期間: {df_prices_all['Date'].min()} ~ {df_prices_all['Date'].max()}")

print(f"\n財務データ:")
print(f"  総レコード数: {len(df_fins_all):,}")
print(f"  銘柄数: {df_fins_all['Code'].nunique()}")
print(f"  期間: {df_fins_all['DiscDate'].min()} ~ {df_fins_all['DiscDate'].max()}")

print("\n完了")
