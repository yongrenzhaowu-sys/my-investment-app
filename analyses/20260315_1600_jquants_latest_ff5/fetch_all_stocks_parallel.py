"""
J-Quants API V2で全銘柄データを並列取得（高速版）

並列度: 20スレッド（レート制限: 10req/sec → 1スレッドあたり0.5秒間隔で安全）
推定所要時間: 4443銘柄 ÷ 20 × 0.5秒 ≈ 2分
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
from typing import Dict, List, Optional
from threading import Lock

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# スレッドセーフなカウンター
progress_lock = Lock()
progress_counter = {'success': 0, 'failed': 0, 'total': 0}


class JQuantsClient:
    """J-Quants API V2クライアント（並列処理対応）"""

    BASE_URL = "https://api.jquants.com/v2"

    def __init__(self):
        api_key = os.environ.get("JQUANTS_API_KEY")
        if not api_key:
            raise ValueError("環境変数 JQUANTS_API_KEY が設定されていません。")

        self.api_key = api_key
        # セッションはスレッドごとに作成
        print(f"[INFO] APIキー設定完了")

    def _create_session(self):
        """スレッドローカルなセッションを作成"""
        session = requests.Session()
        session.headers.update({"x-api-key": self.api_key})
        return session

    def _request(self, endpoint: str, params: Optional[Dict] = None, session=None) -> Dict:
        """APIリクエスト"""
        if session is None:
            session = self._create_session()

        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {"data": []}
            raise
        except Exception as e:
            raise

    def get_stock_list(self) -> pd.DataFrame:
        """銘柄マスター取得"""
        print("[INFO] 銘柄マスター取得中...")
        data = self._request("/equities/master")
        df = pd.DataFrame(data["data"])
        print(f"[INFO] 銘柄数: {len(df)}")
        return df

    def get_daily_bars(self, code: str, start_dt: str, end_dt: Optional[str] = None, session=None) -> pd.DataFrame:
        """株価データ取得"""
        params = {"code": code, "start_dt": start_dt}
        if end_dt:
            params["end_dt"] = end_dt

        data = self._request("/equities/bars/daily", params, session)
        if not data.get("data"):
            return pd.DataFrame()

        return pd.DataFrame(data["data"])

    def get_financials(self, code: str, session=None) -> pd.DataFrame:
        """財務データ取得"""
        params = {"code": code}
        data = self._request("/fins/summary", params, session)
        if not data.get("data"):
            return pd.DataFrame()

        return pd.DataFrame(data["data"])


def fetch_single_stock_prices(args):
    """単一銘柄の株価データを取得（並列処理用）"""
    code, client, start_dt, end_dt = args
    session = client._create_session()

    try:
        time.sleep(0.05)  # レート制限対策（並列20スレッド × 0.05秒 = 1秒で20リクエスト）
        df = client.get_daily_bars(code, start_dt, end_dt, session)

        with progress_lock:
            progress_counter['success'] += 1
            total = progress_counter['success'] + progress_counter['failed']
            if total % 500 == 0:
                print(f"[INFO] 株価取得: {total}/{progress_counter['total']} ({total/progress_counter['total']*100:.1f}%)")

        return df if not df.empty else None
    except Exception as e:
        with progress_lock:
            progress_counter['failed'] += 1
        return None
    finally:
        session.close()


def fetch_single_stock_financials(args):
    """単一銘柄の財務データを取得（並列処理用）"""
    code, client = args
    session = client._create_session()

    try:
        time.sleep(0.05)
        df = client.get_financials(code, session)

        with progress_lock:
            progress_counter['success'] += 1
            total = progress_counter['success'] + progress_counter['failed']
            if total % 500 == 0:
                print(f"[INFO] 財務取得: {total}/{progress_counter['total']} ({total/progress_counter['total']*100:.1f}%)")

        return df if not df.empty else None
    except Exception as e:
        with progress_lock:
            progress_counter['failed'] += 1
        return None
    finally:
        session.close()


def main():
    print("="*80)
    print("J-Quants API V2 - 全銘柄並列取得（高速版）")
    print("="*80)

    # クライアント初期化
    try:
        client = JQuantsClient()
    except ValueError as e:
        print(f"[ERROR] {e}")
        return

    # 銘柄マスター取得
    stocks = client.get_stock_list()
    stocks['Code4'] = stocks['Code'].str[:4]
    codes = sorted(stocks['Code4'].unique())

    # 出力ディレクトリ
    output_dir = PROJECT_ROOT / "data/processed/jquants_latest_full"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 取得期間
    start_dt = "20250301"
    end_dt = "20260315"
    print(f"\n[INFO] 取得期間: {start_dt} ~ {end_dt}")

    # 株価データ並列取得
    print("\n" + "="*80)
    print("株価データ並列取得開始")
    print("="*80)
    print(f"[INFO] 銘柄数: {len(codes)}")
    print(f"[INFO] 並列度: 20スレッド")
    print(f"[INFO] 推定所要時間: {len(codes) / 20 * 0.05 / 60:.1f}分")

    progress_counter.update({'success': 0, 'failed': 0, 'total': len(codes)})

    args_list = [(code, client, start_dt, end_dt) for code in codes]
    all_prices = []

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_single_stock_prices, args): args[0] for args in args_list}

        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                all_prices.append(result)

    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] 株価取得完了: {elapsed:.1f}秒")
    print(f"[INFO] 成功: {progress_counter['success']}/{len(codes)} 銘柄")

    # 結合・保存
    if all_prices:
        df_prices = pd.concat(all_prices, ignore_index=True)
        prices_path = output_dir / "daily_bars_full.parquet"
        df_prices.to_parquet(prices_path, engine="pyarrow", index=False)
        print(f"[INFO] 保存: {prices_path}")
        print(f"[INFO] レコード数: {len(df_prices):,}")

    # 財務データ並列取得
    print("\n" + "="*80)
    print("財務データ並列取得開始")
    print("="*80)

    progress_counter.update({'success': 0, 'failed': 0, 'total': len(codes)})

    args_list = [(code, client) for code in codes]
    all_fins = []

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_single_stock_financials, args): args[0] for args in args_list}

        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                all_fins.append(result)

    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] 財務取得完了: {elapsed:.1f}秒")
    print(f"[INFO] 成功: {progress_counter['success']}/{len(codes)} 銘柄")

    # 結合・保存
    if all_fins:
        df_fins = pd.concat(all_fins, ignore_index=True)
        fins_path = output_dir / "financials_full.parquet"
        df_fins.to_parquet(fins_path, engine="pyarrow", index=False)
        print(f"[INFO] 保存: {fins_path}")
        print(f"[INFO] レコード数: {len(df_fins):,}")

    print("\n" + "="*80)
    print("完了")
    print("="*80)
    print(f"\n出力ディレクトリ: {output_dir}")
    print(f"\n次のステップ:")
    print(f"  python calculate_ff5_momentum_full.py")


if __name__ == "__main__":
    main()
