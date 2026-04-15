"""
J-Quants API V2で日次データを並列取得（最速版）

並列度: 10スレッド
推定所要時間: 250日 ÷ 10 × 4秒 ≈ 100秒 = 1.7分
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
from typing import Dict, Optional, Tuple
from threading import Lock

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# スレッドセーフなカウンター
progress_lock = Lock()
progress_counter = {'success': 0, 'failed': 0, 'total': 0}


class JQuantsClient:
    """J-Quants API V2クライアント"""

    BASE_URL = "https://api.jquants.com/v2"

    def __init__(self):
        api_key = os.environ.get("JQUANTS_API_KEY")
        if not api_key:
            raise ValueError("環境変数 JQUANTS_API_KEY が設定されていません。")
        self.api_key = api_key
        print(f"[INFO] APIキー設定完了")

    def _create_session(self):
        """スレッドローカルなセッションを作成"""
        session = requests.Session()
        session.headers.update({"x-api-key": self.api_key})
        return session


def fetch_single_day_prices(args) -> Optional[pd.DataFrame]:
    """指定日の株価データを取得（並列処理用）"""
    date, client = args
    session = client._create_session()

    try:
        url = f"{client.BASE_URL}/equities/bars/daily"
        params = {"date": date}

        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        with progress_lock:
            progress_counter['success'] += 1
            total = progress_counter['success'] + progress_counter['failed']
            if total % 25 == 0:
                print(f"[INFO] 株価取得: {total}/{progress_counter['total']} ({total/progress_counter['total']*100:.1f}%)")

        if data.get("data"):
            return pd.DataFrame(data["data"])
        return None

    except Exception as e:
        with progress_lock:
            progress_counter['failed'] += 1
            if progress_counter['failed'] % 10 == 0:
                print(f"[WARN] 失敗数: {progress_counter['failed']}")
        return None
    finally:
        session.close()


def fetch_single_day_financials(args) -> Optional[pd.DataFrame]:
    """指定日の財務データを取得（並列処理用）"""
    date, client = args
    session = client._create_session()

    try:
        url = f"{client.BASE_URL}/fins/summary"
        params = {"date": date}

        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        with progress_lock:
            progress_counter['success'] += 1
            total = progress_counter['success'] + progress_counter['failed']
            if total % 10 == 0:
                print(f"[INFO] 財務取得: {total}/{progress_counter['total']} ({total/progress_counter['total']*100:.1f}%)")

        if data.get("data"):
            return pd.DataFrame(data["data"])
        return None

    except Exception as e:
        with progress_lock:
            progress_counter['failed'] += 1
        return None
    finally:
        session.close()


def generate_business_days(start_date: str, end_date: str):
    """営業日リストを生成（土日を除外）"""
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")

    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # 月曜～金曜
            dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    return dates


def main():
    print("="*80)
    print("J-Quants API V2 - 日次データ並列取得（最速版）")
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
    print(f"[INFO] 並列度: 10スレッド")
    print(f"[INFO] 推定所要時間: {len(business_days) / 10 * 4 / 60:.1f}分")

    # 株価データ並列取得
    print("\n" + "="*80)
    print("株価データ並列取得開始")
    print("="*80)

    progress_counter.update({'success': 0, 'failed': 0, 'total': len(business_days)})

    args_list = [(date, client) for date in business_days]
    all_prices = []

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_single_day_prices, args): args[0] for args in args_list}

        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                all_prices.append(result)

    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] 株価取得完了: {elapsed:.1f}秒 ({elapsed/60:.1f}分)")
    print(f"[INFO] 成功: {progress_counter['success']}/{len(business_days)}日")

    # 結合・保存
    if all_prices:
        print("[INFO] データ結合中...")
        df_prices = pd.concat(all_prices, ignore_index=True)

        prices_path = output_dir / "daily_bars_full.parquet"
        df_prices.to_parquet(prices_path, engine="pyarrow", index=False)

        print(f"[SUCCESS] 保存: {prices_path}")
        print(f"[INFO] レコード数: {len(df_prices):,}")
        print(f"[INFO] 銘柄数: {df_prices['Code'].nunique()}")
        print(f"[INFO] 期間: {df_prices['Date'].min()} ~ {df_prices['Date'].max()}")

    # 財務データ並列取得（全営業日）
    print("\n" + "="*80)
    print("財務データ並列取得開始")
    print("="*80)

    print(f"[INFO] 取得対象: {len(business_days)}日（全営業日）")

    progress_counter.update({'success': 0, 'failed': 0, 'total': len(business_days)})

    args_list = [(date, client) for date in business_days]
    all_fins = []

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_single_day_financials, args): args[0] for args in args_list}

        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                all_fins.append(result)

    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] 財務取得完了: {elapsed:.1f}秒 ({elapsed/60:.1f}分)")
    print(f"[INFO] 成功: {progress_counter['success']}/{len(business_days)}日")

    # 結合・保存
    if all_fins:
        print("[INFO] データ結合中...")
        df_fins = pd.concat(all_fins, ignore_index=True)

        # 重複除去
        df_fins = df_fins.drop_duplicates(subset=['Code', 'DiscDate'], keep='last')

        fins_path = output_dir / "financials_full.parquet"
        df_fins.to_parquet(fins_path, engine="pyarrow", index=False)

        print(f"[SUCCESS] 保存: {fins_path}")
        print(f"[INFO] レコード数: {len(df_fins):,}")
        print(f"[INFO] 銘柄数: {df_fins['Code'].nunique()}")

    print("\n" + "="*80)
    print("完了")
    print("="*80)
    print(f"\n出力ディレクトリ: {output_dir}")
    print(f"\n次のステップ:")
    print(f"  python calculate_ff5_momentum_full.py")


if __name__ == "__main__":
    main()
