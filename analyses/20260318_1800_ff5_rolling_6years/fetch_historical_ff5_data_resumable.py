"""
5年間の歴史的データを取得（2021-03～2026-03）

途中保存機能付き版:
- 100日ごとに取得済みデータを保存
- 再開時に取得済み日付をスキップ
- 進捗状態を保存
"""
import pandas as pd
import numpy as np
import os
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
import requests

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
EXISTING_DATA_DIR = PROJECT_ROOT / "data/processed/jquants_latest_full"
OUTPUT_DIR = PROJECT_ROOT / "data/processed/jquants_historical_6years"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 進捗ファイル
PROGRESS_FILE = OUTPUT_DIR / "fetch_progress.json"

# J-Quants API設定
API_KEY = os.environ.get('JQUANTS_API_KEY')
if not API_KEY:
    raise ValueError("環境変数 JQUANTS_API_KEY が設定されていません")

BASE_URL = "https://api.jquants.com/v2"

print("="*80)
print("FF5ファクター長期データ取得（2021-03～2026-03、5年間、途中保存対応）")
print("="*80)

# ヘッダー設定
headers = {
    'x-api-key': API_KEY
}

def load_progress():
    """進捗状態を読み込み"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        'prices_completed_dates': [],
        'fins_completed_dates': [],
        'prices_phase_complete': False,
        'fins_phase_complete': False
    }

def save_progress(progress):
    """進捗状態を保存"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def save_intermediate_data(data_list, phase, date_str):
    """途中経過データを保存"""
    if len(data_list) == 0:
        return

    df = pd.concat(data_list, ignore_index=True)

    if phase == 'prices':
        path = OUTPUT_DIR / f"prices_partial_{date_str}.parquet"
    else:
        path = OUTPUT_DIR / f"fins_partial_{date_str}.parquet"

    df.to_parquet(path, index=False)
    print(f"  [保存] 途中データ保存: {path.name} ({len(df):,}レコード)")

def load_partial_data(phase):
    """途中保存データを読み込み"""
    pattern = f"{phase}_partial_*.parquet"
    files = list(OUTPUT_DIR.glob(pattern))

    if len(files) == 0:
        return pd.DataFrame()

    dfs = [pd.read_parquet(f) for f in files]
    return pd.concat(dfs, ignore_index=True)

def cleanup_partial_files(phase):
    """途中保存ファイルを削除"""
    pattern = f"{phase}_partial_*.parquet"
    files = list(OUTPUT_DIR.glob(pattern))
    for f in files:
        f.unlink()
    print(f"  [クリーンアップ] {len(files)}個の途中保存ファイルを削除")

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

# 進捗状態読み込み
progress = load_progress()
print(f"\n[進捗状態]")
print(f"  株価データ: {len(progress['prices_completed_dates'])}日取得済み")
print(f"  財務データ: {len(progress['fins_completed_dates'])}日取得済み")

# 既存データ読み込み
print("\n[1] 既存データ読み込み")
existing_prices = pd.read_parquet(EXISTING_DATA_DIR / "daily_bars_full.parquet")
existing_fins = pd.read_parquet(EXISTING_DATA_DIR / "financials_full.parquet")

print(f"  既存株価: {len(existing_prices):,}レコード")
print(f"  期間: {existing_prices['Date'].min()} ~ {existing_prices['Date'].max()}")
print(f"  既存財務: {len(existing_fins):,}レコード")
print(f"  期間: {existing_fins['DiscDate'].min()} ~ {existing_fins['DiscDate'].max()}")

# 途中保存データ読み込み
partial_prices = load_partial_data('prices')
partial_fins = load_partial_data('fins')

if len(partial_prices) > 0:
    print(f"  途中保存株価: {len(partial_prices):,}レコード")
if len(partial_fins) > 0:
    print(f"  途中保存財務: {len(partial_fins):,}レコード")

# 取得期間設定
print("\n[2] 取得期間設定")
start_date = datetime(2021, 3, 1)
end_date = datetime(2025, 3, 2)  # 既存データの前日まで

print(f"  取得期間: {start_date.date()} ~ {end_date.date()}")

# 営業日リスト生成
business_days = generate_business_days(start_date, end_date)
print(f"  営業日数: {len(business_days)}日")

# 株価データ取得
if not progress['prices_phase_complete']:
    print("\n[3] 株価データ取得（5年間）")

    # 未取得の日付のみ
    remaining_dates = [d for d in business_days if d not in progress['prices_completed_dates']]
    print(f"  残り営業日数: {len(remaining_dates)}日")
    print(f"  推定所要時間: 約{len(remaining_dates) // 60 + 1}分")

    all_prices = []
    if len(partial_prices) > 0:
        all_prices.append(partial_prices)

    request_count = 0
    start_time = time.time()
    save_counter = 0

    for i, date in enumerate(remaining_dates, 1):
        if i % 10 == 0 or i == 1:
            elapsed = time.time() - start_time
            remaining = (len(remaining_dates) - i) * (elapsed / i if i > 0 else 1)
            print(f"  [{i}/{len(remaining_dates)}] {date[:4]}-{date[4:6]}-{date[6:8]} (残り約{remaining/60:.1f}分)...", end='', flush=True)

        df = fetch_daily_bars(date)

        if len(df) > 0:
            all_prices.append(df)
            progress['prices_completed_dates'].append(date)
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

        # 100日ごとに途中保存
        save_counter += 1
        if save_counter >= 100:
            save_intermediate_data(all_prices, 'prices', date)
            save_progress(progress)
            save_counter = 0

    # 最終保存
    if save_counter > 0:
        save_intermediate_data(all_prices, 'prices', date)

    progress['prices_phase_complete'] = True
    save_progress(progress)

    # 株価データ結合
    if len(all_prices) > 0:
        df_prices_historical = pd.concat(all_prices, ignore_index=True)
        print(f"\n  取得完了: {len(df_prices_historical):,}レコード")
    else:
        df_prices_historical = pd.DataFrame()
        print("\n  取得失敗: データなし")
else:
    print("\n[3] 株価データ取得（スキップ、完了済み）")
    df_prices_historical = load_partial_data('prices')
    print(f"  既存データ: {len(df_prices_historical):,}レコード")

# 財務データ取得
if not progress['fins_phase_complete']:
    print("\n[4] 財務データ取得（5年間）")

    # 未取得の日付のみ
    remaining_dates = [d for d in business_days if d not in progress['fins_completed_dates']]
    print(f"  残り営業日数: {len(remaining_dates)}日")
    print(f"  推定所要時間: 約{len(remaining_dates) // 60 + 1}分")

    all_fins = []
    if len(partial_fins) > 0:
        all_fins.append(partial_fins)

    request_count = 0
    start_time = time.time()
    save_counter = 0

    for i, date in enumerate(remaining_dates, 1):
        if i % 10 == 0 or i == 1:
            elapsed = time.time() - start_time
            remaining = (len(remaining_dates) - i) * (elapsed / i if i > 0 else 1)
            print(f"  [{i}/{len(remaining_dates)}] {date[:4]}-{date[4:6]}-{date[6:8]} (残り約{remaining/60:.1f}分)...", end='', flush=True)

        df = fetch_financials(date)

        if len(df) > 0:
            all_fins.append(df)
            progress['fins_completed_dates'].append(date)
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

        # 100日ごとに途中保存
        save_counter += 1
        if save_counter >= 100:
            save_intermediate_data(all_fins, 'fins', date)
            save_progress(progress)
            save_counter = 0

    # 最終保存
    if save_counter > 0:
        save_intermediate_data(all_fins, 'fins', date)

    progress['fins_phase_complete'] = True
    save_progress(progress)

    # 財務データ結合
    if len(all_fins) > 0:
        df_fins_historical = pd.concat(all_fins, ignore_index=True)
        print(f"\n  取得完了: {len(df_fins_historical):,}レコード")
    else:
        df_fins_historical = pd.DataFrame()
        print("\n  取得失敗: データなし")
else:
    print("\n[4] 財務データ取得（スキップ、完了済み）")
    df_fins_historical = load_partial_data('fins')
    print(f"  既存データ: {len(df_fins_historical):,}レコード")

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

# 途中保存ファイルをクリーンアップ
print("\n[7] クリーンアップ")
cleanup_partial_files('prices')
cleanup_partial_files('fins')

# 進捗ファイル削除
if PROGRESS_FILE.exists():
    PROGRESS_FILE.unlink()
    print(f"  進捗ファイル削除: {PROGRESS_FILE.name}")

# サマリー
print("\n[8] サマリー")
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
