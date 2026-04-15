"""J-Quants API クライアント（V2）。"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

from .auth import get_api_key

logger = logging.getLogger(__name__)

BASE_URL = "https://api.jquants.com/v2"


class JQuantsClient:
    """J-Quants API V2クライアント。"""

    def __init__(self, api_key: Optional[str] = None):
        """初期化。

        Args:
            api_key: APIキー（Noneの場合は環境変数から取得）
        """
        self.api_key = api_key or get_api_key()
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": self.api_key})
    
    def _request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        max_retries: int = 3,
    ) -> Dict:
        """APIリクエストを送信する。
        
        Args:
            endpoint: エンドポイント（例: "/prices/daily_quotes"）
            params: クエリパラメータ
            max_retries: 最大リトライ回数
            
        Returns:
            APIレスポンス（JSON）
            
        Raises:
            requests.HTTPError: APIエラー時
        """
        url = f"{BASE_URL}{endpoint}"
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"HTTP error: {e}")
                    raise
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
        
        raise RuntimeError(f"Failed after {max_retries} retries")
    
    def get_daily_quotes(
        self,
        code: str,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        """日次株価データを取得する（V2 API: 日付ごとに取得）。

        Args:
            code: 証券コード（例: "7203"）4桁形式
            from_date: 開始日（YYYY-MM-DD）
            to_date: 終了日（YYYY-MM-DD）

        Returns:
            株価データのDataFrame
        """
        logger.info(f"Fetching daily quotes: {code} from {from_date} to {to_date}")

        # V2 APIでは5桁形式（4桁 + "0"）
        code_v2 = code + "0" if len(code) == 4 else code

        # 日付範囲を生成
        start_dt = pd.to_datetime(from_date)
        end_dt = pd.to_datetime(to_date)
        date_range = pd.date_range(start=start_dt, end=end_dt, freq='D')

        all_data = []

        for date in date_range:
            date_str = date.strftime('%Y-%m-%d')

            try:
                params = {"date": date_str}
                data = self._request("/equities/bars/daily", params=params)

                # dataキーから取得
                if "data" in data:
                    daily_data = data["data"]

                    # 指定銘柄のみフィルタ（5桁形式で検索）
                    code_data = [d for d in daily_data if d.get("Code") == code_v2]

                    if code_data:
                        all_data.extend(code_data)

            except Exception as e:
                logger.warning(f"Failed to fetch {code} for {date_str}: {e}")
                continue

        if not all_data:
            logger.warning(f"No data returned for {code}")
            return pd.DataFrame()

        df = pd.DataFrame(all_data)

        # V2の短縮列名をV1互換に変換
        column_map = {
            "O": "Open",
            "H": "High",
            "L": "Low",
            "C": "Close",
            "Vo": "Volume",
            "Va": "TurnoverValue",
            "AdjC": "AdjustmentClose",
        }
        df = df.rename(columns=column_map)

        # 日付をdatetime型に変換
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date")

        # 終値がない場合は調整後終値を使用
        if "Close" not in df.columns and "AdjustmentClose" in df.columns:
            df["Close"] = df["AdjustmentClose"]

        logger.info(f"Fetched {len(df)} records for {code}")

        return df
    
    def get_multiple_quotes(
        self,
        codes: List[str],
        from_date: str,
        to_date: str,
        delay: float = 0.5,
    ) -> Dict[str, pd.DataFrame]:
        """複数銘柄の株価データを取得する。
        
        Args:
            codes: 証券コードのリスト
            from_date: 開始日（YYYY-MM-DD）
            to_date: 終了日（YYYY-MM-DD）
            delay: リクエスト間の待機時間（秒）
            
        Returns:
            {証券コード: DataFrame} の辞書
        """
        results = {}
        
        for code in codes:
            try:
                df = self.get_daily_quotes(code, from_date, to_date)
                results[code] = df
                
                # レート制限対策
                if delay > 0:
                    time.sleep(delay)
            
            except Exception as e:
                logger.error(f"Error fetching {code}: {e}")
                results[code] = pd.DataFrame()
        
        return results
