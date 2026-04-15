"""
J-Quants API V2のレスポンス構造を確認するテストスクリプト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.auth import JQuantsAuth
from src.api import JQuantsClient
import os

def main():
    # 環境変数から認証情報を取得
    mail = os.environ.get('JQUANTS_MAIL')
    password = os.environ.get('JQUANTS_PASSWORD')
    refresh_token = os.environ.get('JQUANTS_REFRESH_TOKEN')

    if not all([mail, password, refresh_token]):
        print("エラー: 環境変数が設定されていません")
        print("必要な環境変数: JQUANTS_MAIL, JQUANTS_PASSWORD, JQUANTS_REFRESH_TOKEN")
        return

    # 認証
    print("認証中...")
    auth = JQuantsAuth(mail, password, refresh_token)

    if not auth.is_authenticated():
        print(f"認証失敗: {auth.error_message}")
        return

    print("認証成功!")

    # APIクライアント初期化
    client = JQuantsClient(auth)

    # テスト銘柄（トヨタ自動車）
    test_code = "7203"

    print(f"\n{'='*80}")
    print(f"テスト銘柄: {test_code}")
    print(f"{'='*80}")

    # 1. 株価データ
    print("\n【株価データ】")
    try:
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=100)

        prices = client.get_daily_quotes(
            code=test_code,
            from_date=start_date.strftime('%Y-%m-%d'),
            to_date=end_date.strftime('%Y-%m-%d')
        )

        if len(prices) > 0:
            print(f"取得件数: {len(prices)}")
            print(f"列名: {prices.columns.tolist()}")
            print(f"\n最新データ:")
            print(prices.tail(1).to_string())
        else:
            print("データなし")
    except Exception as e:
        print(f"エラー: {e}")

    # 2. 財務データ
    print(f"\n{'='*80}")
    print("【財務データ】")
    try:
        financials = client.get_financial_statements(code=test_code, limit=5)

        if len(financials) > 0:
            print(f"取得件数: {len(financials)}")
            print(f"列名: {financials.columns.tolist()}")
            print(f"\n全データ:")
            print(financials.to_string())

            # 各列のデータ型を確認
            print(f"\nデータ型:")
            for col in financials.columns:
                dtype = financials[col].dtype
                sample = financials[col].iloc[0] if len(financials) > 0 else None
                print(f"  {col}: {dtype} (例: {sample})")

        else:
            print("データなし")
    except Exception as e:
        print(f"エラー: {e}")

    print(f"\n{'='*80}")
    print("完了")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
