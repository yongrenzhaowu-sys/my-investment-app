"""
J-Quants 価格データ差分更新スクリプト (V2 API対応)

curated の最終日から今日までの差分をAPIから取得し、curatedに追記する。

Usage:
    python scripts/ingest/update_jquants_prices.py [--dry-run] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests


# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent

# パス
CURATED_PATH = PROJECT_ROOT / "data/curated/jquants/prices/daily_quotes_all.parquet"
RAW_DIR = PROJECT_ROOT / "data/raw/jquants/prices"

# J-Quants API V2
JQUANTS_BASE_URL = "https://api.jquants.com/v1"


class JQuantsClientV2:
    """J-Quants API V2 クライアント"""

    def __init__(self, email: str = None, password: str = None, api_key: str = None):
        self.email = email
        self.password = password
        self.api_key = api_key
        self.id_token = None

    def authenticate(self):
        """認証してIDトークンを取得"""
        # メール・パスワードで認証
        if self.email and self.password:
            print("認証中（メールアドレス・パスワード）...")
            url = f"{JQUANTS_BASE_URL}/token/auth_user"
            data = {
                "mailaddress": self.email,
                "password": self.password
            }
            response = requests.post(url, json=data)
            response.raise_for_status()
            refresh_token = response.json()["refreshToken"]

            # リフレッシュトークンからIDトークン取得
            url_refresh = f"{JQUANTS_BASE_URL}/token/auth_refresh"
            params = {"refreshtoken": refresh_token}
            response = requests.post(url_refresh, params=params)
            response.raise_for_status()
            self.id_token = response.json()["idToken"]
            print("[OK] 認証成功")

        # APIキー直接認証を試す
        elif self.api_key:
            print("APIキー認証を試行...")
            # APIキーをそのまま使用
            self.id_token = self.api_key
        else:
            raise ValueError("認証情報が不足しています")

    def get_daily_quotes(self, date_from: str, date_to: str, code: str = None):
        """
        日次株価取得 (V2)

        Args:
            date_from: 開始日 (YYYY-MM-DD)
            date_to: 終了日 (YYYY-MM-DD)
            code: 銘柄コード（省略時は全銘柄）
        """
        if not self.id_token:
            self.authenticate()

        url = f"{JQUANTS_BASE_URL}/prices/daily_quotes"
        headers = {
            "Authorization": f"Bearer {self.id_token}"
        }
        params = {
            "from": date_from,
            "to": date_to
        }
        if code:
            params["code"] = code

        print(f"API呼び出し: {date_from} ~ {date_to}" + (f" (code={code})" if code else " (全銘柄)"))

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 401:
            raise ValueError(
                "認証エラー (401): APIキー/認証情報が無効です。\n"
                "J-Quants.env の認証情報を確認してください。"
            )

        response.raise_for_status()

        data = response.json()
        if "daily_quotes" not in data:
            print(f"[WARN]  データなし")
            return pd.DataFrame()

        df = pd.DataFrame(data["daily_quotes"])
        print(f"取得: {len(df):,} 行")
        return df


def load_env():
    """環境変数または.envから認証情報を読み込み"""
    # プロジェクトルートのJ-Quants.envを優先
    env_paths = [
        PROJECT_ROOT / "J-Quants.env",
        PROJECT_ROOT / "legacy/_inbox/J-Quants.env"
    ]

    for env_path in env_paths:
        if env_path.exists():
            print(f"環境変数読み込み: {env_path}")
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            os.environ[key.strip()] = value.strip().strip('"').strip("'")
            break

    email = os.environ.get("JQUANTS_EMAIL")
    password = os.environ.get("JQUANTS_PASSWORD")
    api_key = os.environ.get("JQUANTS_API_KEY")

    return email, password, api_key


def get_last_date():
    """curatedの最終日を取得"""
    if not CURATED_PATH.exists():
        raise FileNotFoundError(
            f"Curated data not found: {CURATED_PATH}\n"
            "先に consolidate_legacy.py を実行してください。"
        )

    df = pd.read_parquet(CURATED_PATH)
    last_date = pd.to_datetime(df["date"]).max()
    return last_date.date()


def fetch_prices(start_date: str, end_date: str, dry_run: bool = False):
    """価格データをAPIから取得"""
    # 認証
    email, password, api_key = load_env()
    client = JQuantsClientV2(email=email, password=password, api_key=api_key)
    client.authenticate()

    # dry-run: 1銘柄のみ
    code = "86970" if dry_run else None  # 日本取引所グループ
    if dry_run:
        print(f"[DRY-RUN] 1銘柄のみ取得: code={code}")

    # API取得（3ヶ月制約対応）
    all_data = []
    current_start = datetime.strptime(start_date, "%Y-%m-%d").date()
    final_end = datetime.strptime(end_date, "%Y-%m-%d").date()

    while current_start <= final_end:
        # 3ヶ月ごとに分割
        current_end = min(current_start + timedelta(days=89), final_end)

        df = client.get_daily_quotes(
            date_from=current_start.strftime("%Y-%m-%d"),
            date_to=current_end.strftime("%Y-%m-%d"),
            code=code
        )

        if not df.empty:
            all_data.append(df)

        current_start = current_end + timedelta(days=1)

    if not all_data:
        print("[WARN]  取得データなし")
        return pd.DataFrame()

    df_all = pd.concat(all_data, ignore_index=True)
    return df_all


def process_and_save(df_api: pd.DataFrame):
    """APIデータを処理してcuratedに追記"""
    if df_api.empty:
        print("[WARN]  処理対象データなし")
        return

    # カラムリネーム（調整済み価格のみ）
    rename_map = {
        'Date': 'date',
        'Code': 'code',
        'AdjustmentOpen': 'open',
        'AdjustmentHigh': 'high',
        'AdjustmentLow': 'low',
        'AdjustmentClose': 'close',
        'AdjustmentVolume': 'volume'
    }

    # APIスキーマに合わせて柔軟に対応
    actual_rename = {k: v for k, v in rename_map.items() if k in df_api.columns}
    df_new = df_api[list(actual_rename.keys())].rename(columns=actual_rename)

    # 日付型変換
    df_new['date'] = pd.to_datetime(df_new['date'])

    # 既存curated読み込み
    df_existing = pd.read_parquet(CURATED_PATH)
    df_existing['date'] = pd.to_datetime(df_existing['date'])

    # 統合
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)

    # 重複削除（後勝ち = API優先）
    before_count = len(df_combined)
    df_combined = df_combined.drop_duplicates(subset=['date', 'code'], keep='last')
    after_count = len(df_combined)
    print(f"重複削除: {before_count - after_count:,} 行削除")

    # ソート
    df_combined = df_combined.sort_values(['code', 'date']).reset_index(drop=True)

    # 統計
    print(f"\n統計情報:")
    print(f"  既存: {len(df_existing):,} 行")
    print(f"  新規: {len(df_new):,} 行")
    print(f"  統合後: {len(df_combined):,} 行")
    print(f"  期間: {df_combined['date'].min().date()} ~ {df_combined['date'].max().date()}")

    # raw保存
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"daily_quotes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df_new.to_parquet(raw_path, index=False)
    print(f"\n[RAW] Raw保存: {raw_path}")

    # curated更新
    df_combined.to_parquet(CURATED_PATH, index=False)
    print(f"[OK] Curated更新: {CURATED_PATH}")


def main():
    parser = argparse.ArgumentParser(description="J-Quants 価格データ差分更新 (V2)")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run: 1銘柄×短期間のみ")
    parser.add_argument("--start-date", help="開始日 (YYYY-MM-DD、省略時は自動)")
    parser.add_argument("--end-date", help="終了日 (YYYY-MM-DD、省略時は今日)")

    args = parser.parse_args()

    print(f"=== J-Quants 価格データ更新 (V2) ===")
    print(f"モード: {'DRY-RUN' if args.dry_run else '本番'}")
    print(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # 期間決定
        if args.start_date:
            start_date = args.start_date
        else:
            last_date = get_last_date()
            start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            print(f"Curated最終日: {last_date}")
            print(f"差分開始日: {start_date}")

        end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")

        # dry-run: 直近5営業日のみ
        if args.dry_run:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            print(f"[DRY-RUN] 期間上書き: {start_date} ~ {end_date}")

        # 取得
        df = fetch_prices(start_date, end_date, dry_run=args.dry_run)

        if df.empty:
            print("\n[WARN]  取得データなし。終了します。")
            return

        # 処理・保存
        process_and_save(df)

        print("\n[OK] 更新完了")

    except Exception as e:
        print(f"\n[ERROR] エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
