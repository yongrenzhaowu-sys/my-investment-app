"""東証業種別指数コードのテスト

J-Quants APIで実際にどのコードが取得できるか確認する
"""
import os
import time
from datetime import datetime, timedelta
from src.api import JQuantsClient
from src.auth import JQuantsAuth

def test_index_codes():
    """各指数コードでデータが取得できるか確認"""

    # 環境変数から認証情報取得
    secrets = {
        "JQUANTS_API_KEY": os.environ.get("JQUANTS_API_KEY", "")
    }

    # APIクライアント初期化
    auth = JQuantsAuth(secrets=secrets)
    api = JQuantsClient(auth=auth)

    # テスト期間（直近1週間）
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # テストするコード一覧
    test_codes = []

    # 0040-0049（数字）
    for i in range(0x40, 0x4A):
        test_codes.append(f"{i:04X}")

    # 004A-004F（16進数）
    for i in range(0x4A, 0x50):
        test_codes.append(f"{i:04X}")

    # 0050-0072（数字）- 実際に存在するか確認
    for i in range(0x50, 0x73):
        test_codes.append(f"{i:04X}")

    print(f"テスト対象: {len(test_codes)}コード")
    print(f"期間: {start_date} 〜 {end_date}\n")

    available_codes = []
    unavailable_codes = []

    for i, code in enumerate(test_codes):
        if i > 0 and i % 5 == 0:
            time.sleep(1)  # Rate limiting

        try:
            url = f"{api.BASE_URL}/indices/bars/daily"
            params = {
                "code": code,
                "from": start_date.replace("-", ""),
                "to": end_date.replace("-", "")
            }

            response = api.session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    print(f"[OK] {code}: データあり（{len(data)}件）")
                    available_codes.append(code)
                else:
                    print(f"[NG] {code}: レスポンスは200だがデータなし")
                    unavailable_codes.append(code)
            else:
                print(f"[NG] {code}: HTTPエラー {response.status_code}")
                unavailable_codes.append(code)

        except Exception as e:
            print(f"[NG] {code}: エラー - {str(e)}")
            unavailable_codes.append(code)

    print(f"\n--- 結果サマリー ---")
    print(f"取得可能: {len(available_codes)}コード")
    print(f"取得不可: {len(unavailable_codes)}コード")

    print(f"\n--- 取得可能なコード一覧 ---")
    for code in available_codes:
        print(code)

    print(f"\n--- 取得不可のコード一覧 ---")
    for code in unavailable_codes:
        print(code)

    return available_codes, unavailable_codes


if __name__ == "__main__":
    available, unavailable = test_index_codes()
