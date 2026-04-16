"""
銘柄16630の詳細デバッグスクリプト

単位変換が正しく行われているか確認
"""

import sys
from pathlib import Path
import pandas as pd

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
        return

    # 認証
    print("認証中...")
    auth = JQuantsAuth(mail, password, refresh_token)

    if not auth.is_authenticated():
        print(f"認証失敗: {auth.error_message}")
        return

    print("認証成功!\n")

    # APIクライアント初期化
    client = JQuantsClient(auth)

    # テスト銘柄
    test_code = "16630"

    print(f"{'='*80}")
    print(f"銘柄コード: {test_code}")
    print(f"{'='*80}\n")

    # 1. 財務データ取得
    print("【財務データ】")
    try:
        financials = client.get_financial_statements(code=test_code, limit=3)

        if len(financials) > 0:
            print(f"取得件数: {len(financials)}\n")

            latest = financials.iloc[0]

            # 生データを表示
            print("【生データ（API直接レスポンス）】")
            for key in ['Sales', 'OP', 'NP', 'TA', 'Eq', 'EPS', 'DiscDate', 'CurPerEn']:
                if key in latest:
                    value = latest[key]
                    print(f"  {key}: {value} (型: {type(value).__name__})")

            # 数値変換
            print("\n【数値変換後】")
            sales = pd.to_numeric(latest.get('Sales'), errors='coerce')
            op = pd.to_numeric(latest.get('OP'), errors='coerce')
            np_val = pd.to_numeric(latest.get('NP'), errors='coerce')
            ta = pd.to_numeric(latest.get('TA'), errors='coerce')
            eq = pd.to_numeric(latest.get('Eq'), errors='coerce')
            eps = pd.to_numeric(latest.get('EPS'), errors='coerce')

            print(f"  Sales: {sales:,.0f} 円")
            print(f"  OP:    {op:,.0f} 円")
            print(f"  NP:    {np_val:,.0f} 円")
            print(f"  TA:    {ta:,.0f} 円")
            print(f"  Eq:    {eq:,.0f} 円")
            print(f"  EPS:   {eps:.2f} 円/株")

            # 億円換算
            print("\n【億円換算（÷100,000,000）】")
            print(f"  Sales: {sales/1e8:.2f} 億円")
            print(f"  OP:    {op/1e8:.2f} 億円")
            print(f"  NP:    {np_val/1e8:.2f} 億円")
            print(f"  TA:    {ta/1e8:.2f} 億円")
            print(f"  Eq:    {eq/1e8:.2f} 億円")

            # 発行済株式数計算
            if pd.notna(np_val) and pd.notna(eps) and eps > 0:
                shares_outstanding = np_val / eps
                print(f"\n【発行済株式数計算】")
                print(f"  NP: {np_val:,.0f} 円")
                print(f"  EPS: {eps:.2f} 円/株")
                print(f"  発行済株式数 = NP ÷ EPS = {shares_outstanding:,.0f} 株")
                print(f"  発行済株式数（万株）: {shares_outstanding/10000:.2f} 万株")

        else:
            print("データなし")
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

    # 2. 株価データ取得
    print(f"\n{'='*80}")
    print("【株価データ】")
    try:
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=10)

        prices = client.get_daily_quotes(
            code=test_code,
            from_date=start_date.strftime('%Y-%m-%d'),
            to_date=end_date.strftime('%Y-%m-%d')
        )

        if len(prices) > 0:
            latest_price = prices.iloc[-1]

            print(f"最新株価データ:")
            print(f"  日付: {latest_price.get('Date', 'N/A')}")
            print(f"  終値（Price）: {latest_price.get('Price', 'N/A'):.2f} 円")

            # 時価総額計算（財務データがある場合）
            if len(financials) > 0:
                latest_fin = financials.iloc[0]
                np_val = pd.to_numeric(latest_fin.get('NP'), errors='coerce')
                eps = pd.to_numeric(latest_fin.get('EPS'), errors='coerce')
                current_price = latest_price.get('Price', 0)

                if pd.notna(np_val) and pd.notna(eps) and eps > 0:
                    shares_outstanding = np_val / eps
                    market_cap_yen = current_price * shares_outstanding
                    market_cap_million = market_cap_yen / 1_000_000

                    print(f"\n【時価総額計算】")
                    print(f"  株価: {current_price:.2f} 円")
                    print(f"  発行済株式数: {shares_outstanding:,.0f} 株")
                    print(f"  時価総額（円）: {market_cap_yen:,.0f} 円")
                    print(f"  時価総額（百万円）: {market_cap_million:,.2f} 百万円")
                    print(f"  時価総額（億円）: {market_cap_million/100:.2f} 億円")

        else:
            print("データなし")
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*80}")
    print("完了")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
