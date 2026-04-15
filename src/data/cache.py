"""データキャッシュ管理。"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

CACHE_DIR = "data/raw/jquants"


def get_cache_path(code: str, date: str) -> Path:
    """キャッシュファイルのパスを取得する。
    
    Args:
        code: 証券コード
        date: 日付（YYYYMMDD）
        
    Returns:
        キャッシュファイルのパス
    """
    cache_dir = Path(CACHE_DIR) / date
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{code}.json"


def load_from_cache(code: str, date: str) -> Optional[pd.DataFrame]:
    """キャッシュからデータを読み込む。
    
    Args:
        code: 証券コード
        date: 日付（YYYYMMDD）
        
    Returns:
        DataFrame、またはキャッシュがない場合はNone
    """
    cache_path = get_cache_path(code, date)
    
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not data:
            return None
        
        df = pd.DataFrame(data)
        
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
        
        logger.info(f"Loaded {code} from cache: {cache_path}")
        return df
    
    except Exception as e:
        logger.warning(f"Failed to load cache for {code}: {e}")
        return None


def save_to_cache(code: str, date: str, df: pd.DataFrame) -> None:
    """データをキャッシュに保存する。
    
    Args:
        code: 証券コード
        date: 日付（YYYYMMDD）
        df: 保存するDataFrame
    """
    cache_path = get_cache_path(code, date)
    
    try:
        # DataFrameをJSON形式に変換
        data = df.to_dict(orient="records")
        
        # Date列を文字列に変換
        for record in data:
            if "Date" in record and isinstance(record["Date"], pd.Timestamp):
                record["Date"] = record["Date"].strftime("%Y-%m-%d")
        
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {code} to cache: {cache_path}")
    
    except Exception as e:
        logger.warning(f"Failed to save cache for {code}: {e}")


def get_cached_or_fetch(
    client,
    code: str,
    from_date: str,
    to_date: str,
    force_fetch: bool = False,
) -> pd.DataFrame:
    """キャッシュから取得、なければAPIで取得してキャッシュする。
    
    Args:
        client: JQuantsClientインスタンス
        code: 証券コード
        from_date: 開始日（YYYY-MM-DD）
        to_date: 終了日（YYYY-MM-DD）
        force_fetch: Trueの場合はキャッシュを無視してAPIから取得
        
    Returns:
        株価データのDataFrame
    """
    today = datetime.now().strftime("%Y%m%d")
    
    # キャッシュチェック
    if not force_fetch:
        cached_df = load_from_cache(code, today)
        if cached_df is not None and not cached_df.empty:
            logger.info(f"Using cached data for {code}")
            return cached_df
    
    # APIから取得
    logger.info(f"Fetching from API: {code}")
    df = client.get_daily_quotes(code, from_date, to_date)
    
    # キャッシュに保存
    if not df.empty:
        save_to_cache(code, today, df)
    
    return df


def cleanup_old_cache(retention_days: int = 30) -> None:
    """古いキャッシュを削除する。
    
    Args:
        retention_days: 保持日数
    """
    cache_root = Path(CACHE_DIR)
    
    if not cache_root.exists():
        return
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    for date_dir in cache_root.iterdir():
        if not date_dir.is_dir():
            continue
        
        try:
            dir_date = datetime.strptime(date_dir.name, "%Y%m%d")
            
            if dir_date < cutoff_date:
                # 古いディレクトリを削除
                for file in date_dir.iterdir():
                    file.unlink()
                date_dir.rmdir()
                logger.info(f"Deleted old cache: {date_dir}")
        
        except ValueError:
            # 日付形式でないディレクトリはスキップ
            continue
