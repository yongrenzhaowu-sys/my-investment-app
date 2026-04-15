"""
J-Quants API V2で最新データを取得してFF5ファクターを更新

使用方法:
    python fetch_latest_data.py

前提条件:
    環境変数 JQUANTS_API_KEY が設定されていること
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import requests
from typing import Dict, List, Optional

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class JQuantsClient:
    """J-Quants API V2クライアント"""

    BASE_URL = "https://api.jquants.com/v2"
    RATE_LIMIT_DELAY = 0.1  # 1秒あたり10リクエスト

    def __init__(self):
        """初期化（環境変数からAPIキー取得）"""
        api_key = os.environ.get("JQUANTS_API_KEY")
        if not api_key:
            raise ValueError(
                "環境変数 JQUANTS_API_KEY が設定されていません。\n"
                "以下のコマンドで設定してください:\n"
                "  setx JQUANTS_API_KEY \"your_api_key_here\"\n"
                "詳細: docs/knowledges/20260311_1800_jquants_api_v2_complete.md"
            )

        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": self.api_key})
        print(f"[INFO] APIキー設定完了: {self._mask_key(api_key)}")

    @staticmethod
    def _mask_key(key: str) -> str:
        """APIキーをマスク表示"""
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """APIリクエスト"""
        url = f"{self.BASE_URL}{endpoint}"
        time.sleep(self.RATE_LIMIT_DELAY)  # レート制限対策

        try:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] HTTP Error: {e}")
            print(f"[ERROR] URL: {url}")
            print(f"[ERROR] Params: {params}")
            raise
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            raise

    def get_stock_list(self) -> pd.DataFrame:
        """銘柄マスター取得"""
        print("[INFO] 銘柄マスター取得中...")
        data = self._request("/equities/master")
        df = pd.DataFrame(data["data"])
        print(f"[INFO] 銘柄数: {len(df)}")
        return df

    def get_daily_bars(self, code: str, start_dt: str, end_dt: Optional[str] = None) -> pd.DataFrame:
        """株価データ（日次バー）取得"""
        params = {"code": code, "start_dt": start_dt}
        if end_dt:
            params["end_dt"] = end_dt

        data = self._request("/equities/bars/daily", params)
        if not data.get("data"):
            return pd.DataFrame()

        df = pd.DataFrame(data["data"])
        return df

    def get_financials(self, code: str) -> pd.DataFrame:
        """財務データ取得"""
        params = {"code": code}
        data = self._request("/fins/summary", params)
        if not data.get("data"):
            return pd.DataFrame()

        df = pd.DataFrame(data["data"])
        return df


def fetch_all_stocks_prices(client: JQuantsClient, start_dt: str, end_dt: str, output_path: Path):
    """全銘柄の株価データを取得"""
    print("\n" + "="*80)
    print("株価データ取得開始")
    print("="*80)

    # 銘柄マスター取得
    stocks = client.get_stock_list()
    codes = stocks["Code"].unique()[:100]  # テスト: 最初の100銘柄のみ
    print(f"[INFO] 取得対象銘柄数: {len(codes)}")

    all_data = []
    for i, code in enumerate(codes, 1):
        if i % 10 == 0:
            print(f"[INFO] 進捗: {i}/{len(codes)} ({i/len(codes)*100:.1f}%)")

        try:
            df = client.get_daily_bars(code, start_dt, end_dt)
            if not df.empty:
                all_data.append(df)
        except Exception as e:
            print(f"[WARN] {code}: {e}")
            continue

    # 結合
    if all_data:
        df_all = pd.concat(all_data, ignore_index=True)
        df_all.to_parquet(output_path, engine="pyarrow", index=False)
        print(f"\n[SUCCESS] 保存完了: {output_path}")
        print(f"[INFO] レコード数: {len(df_all):,}")
        return df_all
    else:
        print("[ERROR] データ取得失敗")
        return pd.DataFrame()


def fetch_all_stocks_financials(client: JQuantsClient, output_path: Path):
    """全銘柄の財務データを取得"""
    print("\n" + "="*80)
    print("財務データ取得開始")
    print("="*80)

    # 銘柄マスター取得
    stocks = client.get_stock_list()
    codes = stocks["Code"].unique()[:100]  # テスト: 最初の100銘柄のみ
    print(f"[INFO] 取得対象銘柄数: {len(codes)}")

    all_data = []
    for i, code in enumerate(codes, 1):
        if i % 10 == 0:
            print(f"[INFO] 進捗: {i}/{len(codes)} ({i/len(codes)*100:.1f}%)")

        try:
            df = client.get_financials(code)
            if not df.empty:
                all_data.append(df)
        except Exception as e:
            print(f"[WARN] {code}: {e}")
            continue

    # 結合
    if all_data:
        df_all = pd.concat(all_data, ignore_index=True)
        df_all.to_parquet(output_path, engine="pyarrow", index=False)
        print(f"\n[SUCCESS] 保存完了: {output_path}")
        print(f"[INFO] レコード数: {len(df_all):,}")
        return df_all
    else:
        print("[ERROR] データ取得失敗")
        return pd.DataFrame()


def main():
    """メイン処理"""
    print("="*80)
    print("J-Quants API V2 - 最新データ取得")
    print("="*80)

    # クライアント初期化
    try:
        client = JQuantsClient()
    except ValueError as e:
        print(f"[ERROR] {e}")
        return

    # 出力ディレクトリ
    output_dir = PROJECT_ROOT / "data/processed/jquants_latest"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 取得期間
    start_dt = "20251001"  # 2025-10-01
    end_dt = "20260315"    # 2026-03-15
    print(f"\n[INFO] 取得期間: {start_dt} ~ {end_dt}")

    # 株価データ取得
    prices_path = output_dir / "daily_bars_2025_2026.parquet"
    df_prices = fetch_all_stocks_prices(client, start_dt, end_dt, prices_path)

    # 財務データ取得
    fins_path = output_dir / "financials_2025_2026.parquet"
    df_fins = fetch_all_stocks_financials(client, fins_path)

    print("\n" + "="*80)
    print("完了")
    print("="*80)
    print(f"\n出力ディレクトリ: {output_dir}")
    print(f"  - 株価データ: {prices_path.name}")
    print(f"  - 財務データ: {fins_path.name}")


if __name__ == "__main__":
    main()
