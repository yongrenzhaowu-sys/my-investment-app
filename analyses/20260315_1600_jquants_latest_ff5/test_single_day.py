"""
1日分のデータ取得テスト（所要時間計測）
"""
import os
import time
import requests
import pandas as pd

api_key = os.environ.get("JQUANTS_API_KEY")
if not api_key:
    print("ERROR: API key not found")
    exit(1)

BASE_URL = "https://api.jquants.com/v2"
session = requests.Session()
session.headers.update({"x-api-key": api_key})

print("="*80)
print("1日分データ取得テスト")
print("="*80)

# テスト日付
test_date = "20260310"

# 株価データ取得
print(f"\n[TEST] 株価データ取得: {test_date}")
start_time = time.time()

try:
    url = f"{BASE_URL}/equities/bars/daily"
    params = {"date": test_date}

    print(f"  リクエスト: {url}")
    print(f"  パラメータ: {params}")

    response = session.get(url, params=params, timeout=30)
    elapsed = time.time() - start_time

    print(f"  ステータスコード: {response.status_code}")
    print(f"  所要時間: {elapsed:.2f}秒")

    if response.status_code == 200:
        data = response.json()
        if data.get("data"):
            df = pd.DataFrame(data["data"])
            print(f"  取得レコード数: {len(df):,}")
            print(f"  銘柄数: {df['Code'].nunique()}")
            print(f"  サンプルデータ:")
            print(df.head(3)[['Date', 'Code', 'AdjC']])
        else:
            print(f"  データなし")
    else:
        print(f"  エラー: {response.text[:200]}")

except Exception as e:
    elapsed = time.time() - start_time
    print(f"  例外発生: {e}")
    print(f"  所要時間: {elapsed:.2f}秒")

# 財務データ取得
print(f"\n[TEST] 財務データ取得: {test_date}")
start_time = time.time()

try:
    url = f"{BASE_URL}/fins/summary"
    params = {"date": test_date}

    print(f"  リクエスト: {url}")
    print(f"  パラメータ: {params}")

    response = session.get(url, params=params, timeout=30)
    elapsed = time.time() - start_time

    print(f"  ステータスコード: {response.status_code}")
    print(f"  所要時間: {elapsed:.2f}秒")

    if response.status_code == 200:
        data = response.json()
        if data.get("data"):
            df = pd.DataFrame(data["data"])
            print(f"  取得レコード数: {len(df):,}")
            print(f"  銘柄数: {df['Code'].nunique()}")
            print(f"  サンプルデータ:")
            print(df.head(3)[['DiscDate', 'Code', 'Sales', 'OP']])
        else:
            print(f"  データなし")
    else:
        print(f"  エラー: {response.text[:200]}")

except Exception as e:
    elapsed = time.time() - start_time
    print(f"  例外発生: {e}")
    print(f"  所要時間: {elapsed:.2f}秒")

print("\n完了")
