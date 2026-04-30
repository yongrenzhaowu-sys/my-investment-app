"""セクターリターン計算モジュール（TOPIX-17業種指数ベース）"""
from typing import Dict, List
from datetime import datetime
import pandas as pd


def calculate_sector_returns_from_indices(
    client,
    start_date: str,
    end_date: str
) -> Dict[str, float]:
    """
    TOPIX-17業種指数からセクター別リターンを計算

    Args:
        client: J-Quants APIクライアント
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）

    Returns:
        {
            "1": 5.2,  # 食品: +5.2%
            "2": -2.1,  # エネルギー資源: -2.1%
            ...
        }
    """
    sector_returns = {}

    try:
        # TOPIX-17業種指数データを取得
        sector_data = client.get_topix_17_sectors(start_date, end_date)

        if not sector_data:
            print("WARNING: No sector index data received")
            return {}

        # DataFrameに変換
        df = pd.DataFrame(sector_data)

        # 日付列を変換
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
        elif "date" in df.columns:
            df["Date"] = pd.to_datetime(df["date"])

        # セクターコード列を確認
        sector_code_col = None
        for col in ["SectorCode", "Code", "IndustryCode", "Sector17Code"]:
            if col in df.columns:
                sector_code_col = col
                break

        if not sector_code_col:
            print(f"ERROR: Sector code column not found. Available columns: {df.columns.tolist()}")
            return {}

        # 終値列を確認
        close_col = None
        for col in ["Close", "close", "AdjC"]:
            if col in df.columns:
                close_col = col
                break

        if not close_col:
            print(f"ERROR: Close price column not found. Available columns: {df.columns.tolist()}")
            return {}

        # セクターごとにリターンを計算
        for sector_code in df[sector_code_col].unique():
            sector_df = df[df[sector_code_col] == sector_code].copy()
            sector_df = sector_df.sort_values("Date")

            if len(sector_df) < 2:
                continue

            # 開始日と終了日の指数値
            start_value = sector_df.iloc[0][close_col]
            end_value = sector_df.iloc[-1][close_col]

            # リターン計算
            if start_value > 0:
                sector_return = (end_value - start_value) / start_value * 100
                sector_returns[str(sector_code)] = sector_return

        return sector_returns

    except Exception as e:
        print(f"ERROR: calculate_sector_returns_from_indices failed: {e}")
        import traceback
        traceback.print_exc()
        return {}


def calculate_topix_return(
    client,
    start_date: str,
    end_date: str
) -> float:
    """
    TOPIXのリターンを計算

    Args:
        client: J-Quants APIクライアント
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）

    Returns:
        TOPIXリターン（%）
    """
    try:
        # TOPIXデータを取得
        topix_data = client.get_indices_topix(start_date, end_date)

        if not topix_data or len(topix_data) < 2:
            print("WARNING: Insufficient TOPIX data")
            return 0.0

        # DataFrameに変換
        df = pd.DataFrame(topix_data)

        # 日付列を変換
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
        elif "date" in df.columns:
            df["Date"] = pd.to_datetime(df["date"])

        df = df.sort_values("Date")

        # 終値列を確認
        close_col = None
        for col in ["Close", "close", "AdjC"]:
            if col in df.columns:
                close_col = col
                break

        if not close_col:
            print(f"ERROR: Close column not found in TOPIX data. Columns: {df.columns.tolist()}")
            return 0.0

        # 開始日と終了日の価格
        start_value = df.iloc[0][close_col]
        end_value = df.iloc[-1][close_col]

        # リターン計算
        topix_return = (end_value - start_value) / start_value * 100

        return topix_return

    except Exception as e:
        print(f"ERROR: calculate_topix_return failed: {e}")
        import traceback
        traceback.print_exc()
        return 0.0


def calculate_relative_returns(
    sector_returns: Dict[str, float],
    topix_return: float
) -> Dict[str, Dict]:
    """
    TOPIX対比の相対リターンを計算

    Args:
        sector_returns: セクターリターン
        topix_return: TOPIXリターン

    Returns:
        {
            "1": {
                "absolute_return": 5.2,
                "relative_return": 3.5,  # TOPIX+3.5%
                "sector_name": "食品"
            },
            ...
        }
    """
    from .sector_data import SECTOR_17_NAMES

    relative_returns = {}

    for sector_code, absolute_return in sector_returns.items():
        relative_return = absolute_return - topix_return

        relative_returns[sector_code] = {
            "absolute_return": absolute_return,
            "relative_return": relative_return,
            "sector_name": SECTOR_17_NAMES.get(sector_code, "不明")
        }

    return relative_returns
