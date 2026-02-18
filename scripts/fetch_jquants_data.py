#!/usr/bin/env python3
"""
J-Quants API V2から日足データと財務データを取得するスクリプト
（APIキー方式）

使用例:
    # 過去7日分の日足データを取得
    python scripts/fetch_jquants_data.py --data-type daily --days 7

    # 過去1ヶ月分の財務データを取得
    python scripts/fetch_jquants_data.py --data-type fins --days 30

    # 両方を取得（デフォルト）
    python scripts/fetch_jquants_data.py --data-type all --days 7

    # 特定期間を指定
    python scripts/fetch_jquants_data.py --start-date 2026-01-01 --end-date 2026-02-18
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

import pandas as pd
import requests
from dotenv import load_dotenv

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "fetched"
DAILY_DIR = DATA_DIR / "daily_bars"
FINS_DIR = DATA_DIR / "fins_summary"
LOG_DIR = DATA_DIR / "logs"

# ログ設定
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"fetch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# J-Quants API V2 設定
JQUANTS_API_BASE = "https://api.jquants.com/v2"


class JQuantsClientV2:
    """J-Quants API V2 クライアント（APIキー方式）"""

    def __init__(self, api_key: str, plan: str = "Standard"):
        """
        Args:
            api_key: J-Quants API V2のAPIキー
            plan: プラン名（Free/Light/Standard/Premium）
        """
        self.api_key = api_key
        self.base_url = JQUANTS_API_BASE
        self.session = requests.Session()

        # プラン別の待機時間（レート制限対策）
        self.delay_sec = {
            "Free": 12.0,
            "Light": 1.0,
            "Standard": 0.5,
            "Premium": 0.12
        }.get(plan, 0.5)

        logger.info(f"APIクライアント初期化完了（プラン: {plan}, 待機時間: {self.delay_sec}秒）")

    def _headers(self):
        """APIリクエスト用ヘッダー"""
        return {"x-api-key": self.api_key}

    def _request(self, url: str, params: dict = None, max_retries: int = 3):
        """
        APIリクエスト（レート制限対応）

        Args:
            url: リクエストURL
            params: クエリパラメータ
            max_retries: 最大リトライ回数

        Returns:
            レスポンスJSON
        """
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    url,
                    headers=self._headers(),
                    params=params or {},
                    timeout=60
                )
                response.raise_for_status()

                # レート制限対策の待機
                time.sleep(self.delay_sec)

                return response.json()

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    # レート制限エラー時は待機時間を2倍にしてリトライ
                    wait_time = self.delay_sec * (2 ** attempt)
                    logger.warning(f"レート制限エラー: {wait_time:.1f}秒待機中...")
                    time.sleep(wait_time)
                else:
                    raise

        raise Exception(f"最大リトライ回数超過: {url}")

    def get_trading_calendar(self, date_from: str, date_to: str) -> List[str]:
        """
        営業日カレンダーを取得

        Args:
            date_from: 開始日（YYYY-MM-DD）
            date_to: 終了日（YYYY-MM-DD）

        Returns:
            営業日リスト
        """
        url = f"{self.base_url}/markets/calendar"
        params = {"from": date_from, "to": date_to, "hol_div": "1"}

        try:
            result = self._request(url, params)
            calendar = result.get("data", [])
            return [item["Date"] for item in calendar]
        except Exception as e:
            logger.warning(f"営業日カレンダー取得エラー: {e}")
            # フォールバック: 平日のみ
            return self._get_weekdays(date_from, date_to)

    def _get_weekdays(self, date_from: str, date_to: str) -> List[str]:
        """平日リストを生成（営業日カレンダー取得失敗時のフォールバック）"""
        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d")

        weekdays = []
        current = start
        while current <= end:
            if current.weekday() < 5:  # 月〜金
                weekdays.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        return weekdays

    def fetch_daily_bars(self, date: str) -> pd.DataFrame:
        """
        日足データ（OHLCV）を取得

        Args:
            date: 取得日（YYYY-MM-DD形式）

        Returns:
            日足データのDataFrame
        """
        url = f"{self.base_url}/equities/bars/daily"
        params = {"date": date}

        try:
            result = self._request(url, params)
            data = result.get("data", [])

            if not data:
                logger.warning(f"{date}: データなし")
                return pd.DataFrame()

            df = pd.DataFrame(data)

            # V2の短縮列名をV1互換に変換
            column_map = {
                "O": "Open",
                "H": "High",
                "L": "Low",
                "C": "Close",
                "Vo": "Volume",
                "Va": "TurnoverValue",
                "AdjO": "AdjustmentOpen",
                "AdjH": "AdjustmentHigh",
                "AdjL": "AdjustmentLow",
                "AdjC": "AdjustmentClose",
                "AdjVo": "AdjustmentVolume",
                "AdjFactor": "AdjustmentFactor"
            }
            df = df.rename(columns=column_map)

            logger.info(f"{date}: {len(df)}銘柄取得")
            return df

        except Exception as e:
            logger.error(f"{date}: 日足データ取得エラー: {e}")
            return pd.DataFrame()

    def fetch_fins_summary(self, date: str) -> pd.DataFrame:
        """
        財務データを取得

        Args:
            date: 開示日（YYYY-MM-DD形式）

        Returns:
            財務データのDataFrame
        """
        url = f"{self.base_url}/fins/summary"
        params = {"date": date}

        try:
            result = self._request(url, params)
            data = result.get("data", [])

            if not data:
                logger.warning(f"{date}: 財務データなし")
                return pd.DataFrame()

            df = pd.DataFrame(data)

            # V2の短縮列名をV1互換に変換
            column_map = {
                "Sales": "NetSales",
                "OP": "OperatingProfit",
                "OdP": "OrdinaryProfit",
                "NP": "Profit",
                "TA": "TotalAssets",
                "Eq": "NetAssets",
                "EPS": "EarningsPerShare",
                "BPS": "BookValuePerShare"
            }
            df = df.rename(columns=column_map)

            logger.info(f"{date}: {len(df)}件の財務データ取得")
            return df

        except Exception as e:
            logger.error(f"{date}: 財務データ取得エラー: {e}")
            return pd.DataFrame()


def fetch_daily_data(client: JQuantsClientV2, start_date: str, end_date: str):
    """
    日足データを取得して保存

    Args:
        client: J-Quants API V2 クライアント
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
    """
    logger.info(f"日足データ取得開始: {start_date} 〜 {end_date}")

    DAILY_DIR.mkdir(parents=True, exist_ok=True)

    # 営業日リスト取得
    trading_days = client.get_trading_calendar(start_date, end_date)
    logger.info(f"営業日数: {len(trading_days)}日")

    fetched_count = 0

    for date_str in trading_days:
        # データ取得
        df = client.fetch_daily_bars(date_str)

        if not df.empty:
            # parquet保存
            output_file = DAILY_DIR / f"date={date_str}.parquet"
            df.to_parquet(output_file, engine="pyarrow", index=False)
            logger.info(f"保存完了: {output_file}")
            fetched_count += 1

    logger.info(f"日足データ取得完了: {fetched_count}ファイル保存")


def fetch_fins_data(client: JQuantsClientV2, start_date: str, end_date: str):
    """
    財務データを取得して保存

    Args:
        client: J-Quants API V2 クライアント
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
    """
    logger.info(f"財務データ取得開始: {start_date} 〜 {end_date}")

    FINS_DIR.mkdir(parents=True, exist_ok=True)

    # 日付リスト生成（全日）
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    current = start

    fetched_count = 0

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")

        # データ取得
        df = client.fetch_fins_summary(date_str)

        if not df.empty:
            # parquet保存
            output_file = FINS_DIR / f"disclosed_date={date_str}.parquet"
            df.to_parquet(output_file, engine="pyarrow", index=False)
            logger.info(f"保存完了: {output_file}")
            fetched_count += 1

        current += timedelta(days=1)

    logger.info(f"財務データ取得完了: {fetched_count}ファイル保存")


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="J-Quants API V2から日足データと財務データを取得"
    )
    parser.add_argument(
        "--data-type",
        choices=["daily", "fins", "all"],
        default="all",
        help="取得するデータ種別（daily: 日足のみ, fins: 財務のみ, all: 両方）"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="過去何日分のデータを取得するか（デフォルト: 7日）"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="開始日（YYYY-MM-DD形式）。指定した場合は --days より優先"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="終了日（YYYY-MM-DD形式）。デフォルトは今日"
    )
    parser.add_argument(
        "--plan",
        choices=["Free", "Light", "Standard", "Premium"],
        default="Standard",
        help="J-Quantsプラン（レート制限調整用、デフォルト: Standard）"
    )

    args = parser.parse_args()

    # まず環境変数から取得を試みる（推奨、セキュア）
    api_key = os.environ.get("JQUANTS_API_KEY")

    # 環境変数になければ、.envファイルから読み込む（フォールバック）
    if not api_key:
        env_paths = [
            PROJECT_ROOT / "legacy" / "_inbox" / "J-Quants.env",
            PROJECT_ROOT / "legacy" / "_inbox" / ".env"
        ]

        for env_path in env_paths:
            if env_path.exists():
                logger.info(f"環境変数が未設定のため、{env_path}から読み込みます")
                load_dotenv(env_path)
                api_key = os.getenv("JQUANTS_API_KEY")
                if api_key:
                    break

        if not api_key:
            logger.error("JQUANTS_API_KEY が環境変数または.envに設定されていません")
            logger.error("以下のいずれかの方法で設定してください：")
            logger.error("1. Windows環境変数に設定（推奨）")
            logger.error("   [System.Environment]::SetEnvironmentVariable('JQUANTS_API_KEY', 'your_key', 'User')")
            logger.error("2. legacy/_inbox/J-Quants.env に JQUANTS_API_KEY=your_key を追加")
            sys.exit(1)
    else:
        logger.info("✅ 環境変数 JQUANTS_API_KEY を使用します")

    # 日付範囲設定
    if args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    elif args.start_date:
        start_date = args.start_date
        end_date = datetime.now().strftime("%Y-%m-%d")
    else:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    logger.info("="*80)
    logger.info("J-Quants API V2 データ取得スクリプト")
    logger.info("="*80)
    logger.info(f"データ種別: {args.data_type}")
    logger.info(f"取得期間: {start_date} 〜 {end_date}")
    logger.info(f"プラン: {args.plan}")
    logger.info(f"保存先: {DATA_DIR}")
    logger.info("="*80)

    # クライアント作成
    client = JQuantsClientV2(api_key, plan=args.plan)

    # データ取得
    if args.data_type in ["daily", "all"]:
        fetch_daily_data(client, start_date, end_date)

    if args.data_type in ["fins", "all"]:
        fetch_fins_data(client, start_date, end_date)

    logger.info("="*80)
    logger.info("✅ データ取得完了")
    logger.info(f"ログファイル: {log_file}")
    logger.info("="*80)


if __name__ == "__main__":
    main()
