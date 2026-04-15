"""
PEG Ratio計算のデバッグスクリプト

銘柄41770の実際のデータを確認
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

    print("認証成功!")

    # APIクライアント初期化
    client = JQuantsClient(auth)

    # 問題の銘柄
    test_code = "41770"

    print(f"\n{'='*80}")
    print(f"銘柄コード: {test_code}")
    print(f"{'='*80}")

    # 財務データ取得
    print("\n【財務データ】")
    try:
        financials = client.get_financial_statements(code=test_code, limit=10)

        if len(financials) > 0:
            print(f"取得件数: {len(financials)}")

            # 純利益列を確認
            if 'NP' in financials.columns:
                financials['NP_numeric'] = pd.to_numeric(financials['NP'], errors='coerce')

                print(f"\n純利益（NP）の値:")
                for idx, row in financials.iterrows():
                    disc_date = row.get('DiscDate', 'N/A')
                    cur_per_en = row.get('CurPerEn', 'N/A')
                    np_original = row.get('NP', 'N/A')
                    np_numeric = row.get('NP_numeric', 'N/A')

                    print(f"  開示日: {disc_date}, 決算期: {cur_per_en}")
                    print(f"    NP（元）: {np_original} (型: {type(np_original).__name__})")
                    print(f"    NP（数値）: {np_numeric:,.0f}" if pd.notna(np_numeric) else "    NP（数値）: NaN")
                    print()

                # 成長率計算
                np_values = financials['NP_numeric'].dropna()
                if len(np_values) >= 2:
                    np_list = np_values.tail(5).tolist()
                    print(f"成長率計算に使用する純利益（直近5期）:")
                    for i, np_val in enumerate(np_list):
                        print(f"  期{i+1}: {np_val:,.0f}")

                    years = len(np_list) - 1
                    growth_rate = (np_list[-1] / np_list[0]) ** (1 / years) - 1
                    print(f"\n成長率（CAGR）: {growth_rate:.2%}")
                    print(f"  最古: {np_list[0]:,.0f}")
                    print(f"  最新: {np_list[-1]:,.0f}")
                    print(f"  期間: {years}年")

        else:
            print("データなし")
    except Exception as e:
        print(f"エラー: {e}")

    # 株価データ取得
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
            latest = prices.iloc[-1]

            print(f"最新株価データ:")
            print(f"  日付: {latest.get('Date', 'N/A')}")
            print(f"  終値（C）: {latest.get('C', 'N/A')}")
            print(f"  調整係数（AdjFactor）: {latest.get('AdjFactor', 'N/A')}")
            print(f"  調整済終値（Price）: {latest.get('Price', 'N/A')}")
            print(f"  出来高（Vo）: {latest.get('Vo', 'N/A'):,.0f}" if pd.notna(latest.get('Vo')) else "  出来高（Vo）: N/A")

            # 時価総額計算
            price = latest.get('Price', 0)
            volume = latest.get('Vo', 0)
            market_cap = price * volume * 100

            print(f"\n時価総額計算:")
            print(f"  株価: {price:.2f}円")
            print(f"  出来高: {volume:,.0f}株")
            print(f"  時価総額: {market_cap:,.0f}円 = {market_cap/1e9:.2f}億円")

            # PER計算（最新純利益を使用）
            if len(financials) > 0 and 'NP_numeric' in financials.columns:
                latest_np = financials['NP_numeric'].iloc[-1]
                if pd.notna(latest_np) and latest_np > 0:
                    per = market_cap / latest_np
                    print(f"\nPER計算:")
                    print(f"  時価総額: {market_cap:,.0f}円")
                    print(f"  純利益: {latest_np:,.0f}円")
                    print(f"  PER: {per:.2f}")

        else:
            print("データなし")
    except Exception as e:
        print(f"エラー: {e}")

    print(f"\n{'='*80}")
    print("完了")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
