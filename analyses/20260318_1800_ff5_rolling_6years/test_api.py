"""
APIテスト: 1日分のデータ取得
"""
import os
import requests

API_KEY = os.environ.get('JQUANTS_API_KEY')
BASE_URL = "https://api.jquants.com/v2"

headers = {'x-api-key': API_KEY}

# 2025年3月3日のデータ取得テスト
test_date = '20250303'

print("株価データ取得テスト...")
url = f"{BASE_URL}/equities/bars/daily"
params = {'date': test_date}

response = requests.get(url, headers=headers, params=params, timeout=60)
print(f"ステータスコード: {response.status_code}")
print(f"レスポンス: {response.text[:500]}")

if response.status_code == 200:
    data = response.json()
    if 'data' in data:
        print(f"データ件数: {len(data['data'])}")
    else:
        print("データキーなし")
