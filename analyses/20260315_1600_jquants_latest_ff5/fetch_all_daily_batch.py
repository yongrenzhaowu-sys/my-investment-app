"""
J-Quants API V2で日次単位バッチ取得（最高速版）

日付を指定してcode指定なしで取得 → 全銘柄データを一度に取得
推定所要時間: 250営業日 × 0.15秒 ≈ 40秒
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import requests
from typing import Dict, Optional

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class JQuantsClient:
    """J-Quants API V2クライアント（日次バッチ取得）"""

    BASE_URL = "https://api.jquants.com/v2"
    RATE_LIMIT_DELAY = 0.15

    def __init__(self):
        api_key = os.environ.get("JQUANTS_API_KEY")
        if not api_key:
            raise ValueError("環境変数 JQUANTS_API_KEY が設定されていません。")

        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": self.api_key})
        print(f"[INFO] APIキー設定完了")

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """APIリクエスト"""
        url = f"{self.BASE_URL}{endpoint}"
        time.sleep(self.RATE_LIMIT_DELAY)

        try:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {"data": []}
            print(f"[ERROR] HTTP {e.response.status_code}: {url}")
            print(f"[ERROR] Params: {params}")
            raise
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            raise

    def get_daily_bars_all(self, date: str) -> pd.DataFrame:
        """指定日の全銘柄株価データを取得（code指定なし）"""
        params = {"date": date}  # code指定なし
        data = self._request("/equities/bars/daily", params)

        if not data.get("data"):
            return pd.DataFrame()

        return pd.DataFrame(data["data"])

    def get_financials_all(self, date: str) -> pd.DataFrame:
        """指定日の全銘柄財務データを取得（code指定なし）"""
        params = {"date": date}  # code指定なし
        data = self._request("/fins/summary", params)

        if not data.get("data"):
            return pd.DataFrame()

        return pd.DataFrame(data["data"])


def generate_business_days(start_date: str, end_date: str):
    """営業日リストを生成（簡易版: 土日を除外）"""
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")

    dates = []
    current = start
    while current <= end:
        # 土日を除外
        if current.weekday() < 5:  # 0=月曜, 4=金曜
            dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    return dates


def main():
    print("="*80)
    print("J-Quants API V2 - 日次バッチ取得（最高速版）")
    print("="*80)

    # クライアント初期化
    try:
        client = JQuantsClient()
    except ValueError as e:
        print(f"[ERROR] {e}")
        return

    # 出力ディレクトリ
    output_dir = PROJECT_ROOT / "data/processed/jquants_latest_full"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 取得期間
    start_date = "20250301"
    end_date = "20260315"

    # 営業日生成
    business_days = generate_business_days(start_date, end_date)
    print(f"\n[INFO] 取得期間: {start_date} ~ {end_date}")
    print(f"[INFO] 営業日数: {len(business_days)}日")
    print(f"[INFO] 推定所要時間: {len(business_days) * 0.15 / 60:.1f}分")

    # 株価データ取得
    print("\n" + "="*80)
    print("株価データ日次バッチ取得開始")
    print("="*80)

    all_prices = []
    success_count = 0
    failed_dates = []

    for i, date in enumerate(business_days, 1):
        if i % 10 == 0:
            print(f"[INFO] 進捗: {i}/{len(business_days)} ({i/len(business_days)*100:.1f}%)")

        try:
            df = client.get_daily_bars_all(date)
            if not df.empty:
                all_prices.append(df)
                success_count += 1
        except Exception as e:
            failed_dates.append(date)
            if i % 50 == 0:
                print(f"[WARN] 失敗: {len(failed_dates)}日")
            continue

    print(f"\n[SUCCESS] 株価取得完了")
    print(f"[INFO] 成功: {success_count}/{len(business_days)}日")

    # 結合・保存
    if all_prices:
        df_prices = pd.concat(all_prices, ignore_index=True)
        prices_path = output_dir / "daily_bars_full.parquet"
        df_prices.to_parquet(prices_path, engine="pyarrow", index=False)
        print(f"[INFO] 保存: {prices_path}")
        print(f"[INFO] レコード数: {len(df_prices):,}")
        print(f"[INFO] 銘柄数: {df_prices['Code'].nunique()}")
    else:
        print("[ERROR] データ取得失敗")

    # 財務データ取得
    print("\n" + "="*80)
    print("財務データ日次バッチ取得開始")
    print("="*80)

    # 財務データは開示日ベースなので、全期間を一度に取得
    print("[INFO] 財務データは全期間一括取得を試みます...")

    all_fins = []

    # 月初のみ取得（財務データは月次更新が多い）
    monthly_dates = [d for d in business_days if d[-2:] in ['01', '02', '03']]
    print(f"[INFO] 取得対象日数: {len(monthly_dates)}日（月初のみ）")

    for i, date in enumerate(monthly_dates, 1):
        if i % 5 == 0:
            print(f"[INFO] 進捗: {i}/{len(monthly_dates)}")

        try:
            df = client.get_financials_all(date)
            if not df.empty:
                all_fins.append(df)
        except Exception as e:
            continue

    if all_fins:
        df_fins = pd.concat(all_fins, ignore_index=True)
        # 重複除去（同じ銘柄×開示日）
        df_fins = df_fins.drop_duplicates(subset=['Code', 'DiscDate'], keep='last')

        fins_path = output_dir / "financials_full.parquet"
        df_fins.to_parquet(fins_path, engine="pyarrow", index=False)
        print(f"\n[SUCCESS] 財務データ保存: {fins_path}")
        print(f"[INFO] レコード数: {len(df_fins):,}")
        print(f"[INFO] 銘柄数: {df_fins['Code'].nunique()}")
    else:
        print("[WARN] 財務データ取得失敗")

    print("\n" + "="*80)
    print("完了")
    print("="*80)
    print(f"\n出力ディレクトリ: {output_dir}")
    print(f"\n次のステップ:")
    print(f"  python calculate_ff5_momentum_full.py")


if __name__ == "__main__":
    main()
