"""東証33業種指数の強弱判定ロジック

TOPIX対比で各業種の強弱を3つの指標で判定:
1. 期間リターン
2. 移動平均乖離
3. RSI（相対力指数）
"""
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np


def calculate_period_return(
    client,
    start_date: str,
    end_date: str
) -> Tuple[Dict[str, float], float]:
    """
    期間リターンを計算（33業種 + TOPIX）

    Args:
        client: J-Quants APIクライアント
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）

    Returns:
        (sector_returns, topix_return)
        - sector_returns: {業種コード: リターン(%)}
        - topix_return: TOPIXリターン(%)
    """
    # 33業種指数データを取得
    sector_data = client.get_sector_33_indices(start_date, end_date)

    if not sector_data:
        print("WARNING: No sector index data received")
        return {}, 0.0

    # DataFrameに変換
    df = pd.DataFrame(sector_data)

    # 日付列を変換
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    elif "date" in df.columns:
        df["Date"] = pd.to_datetime(df["date"])
        df = df.drop(columns=["date"])

    # 終値列を確認
    close_col = None
    for col in ["Close", "close", "AdjC"]:
        if col in df.columns:
            close_col = col
            break

    if not close_col:
        print(f"ERROR: Close price column not found. Available columns: {df.columns.tolist()}")
        return {}, 0.0

    # 業種ごとにリターンを計算
    sector_returns = {}

    for sector_code in df["Code"].unique():
        sector_df = df[df["Code"] == sector_code].copy()
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

    # TOPIXリターン計算
    topix_data = client.get_indices_topix(start_date, end_date)

    if not topix_data or len(topix_data) < 2:
        print("WARNING: Insufficient TOPIX data")
        topix_return = 0.0
    else:
        topix_df = pd.DataFrame(topix_data)

        if "Date" in topix_df.columns:
            topix_df["Date"] = pd.to_datetime(topix_df["Date"])
        elif "date" in topix_df.columns:
            topix_df["Date"] = pd.to_datetime(topix_df["date"])

        topix_df = topix_df.sort_values("Date")

        # 終値列を確認
        topix_close_col = None
        for col in ["Close", "close", "AdjC"]:
            if col in topix_df.columns:
                topix_close_col = col
                break

        if topix_close_col:
            start_value = topix_df.iloc[0][topix_close_col]
            end_value = topix_df.iloc[-1][topix_close_col]
            topix_return = (end_value - start_value) / start_value * 100
        else:
            topix_return = 0.0

    return sector_returns, topix_return


def calculate_ma_divergence(
    client,
    start_date: str,
    end_date: str,
    ma_periods: List[int] = [25, 75]
) -> Tuple[Dict[str, Dict], Dict]:
    """
    移動平均乖離を計算（33業種 + TOPIX）

    Args:
        client: J-Quants APIクライアント
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        ma_periods: 移動平均期間のリスト（デフォルト: [25, 75]）

    Returns:
        (sector_ma_divs, topix_ma_div)
        - sector_ma_divs: {業種コード: {"ma_25": 乖離率(%), "ma_75": 乖離率(%)}}
        - topix_ma_div: {"ma_25": 乖離率(%), "ma_75": 乖離率(%)}
    """
    # データ取得期間を延長（移動平均計算のため）
    from datetime import datetime, timedelta
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    # 最大期間の2倍分を取得
    max_period = max(ma_periods)
    extended_start = (start_dt - timedelta(days=max_period * 2)).strftime("%Y-%m-%d")

    # 33業種指数データを取得
    sector_data = client.get_sector_33_indices(extended_start, end_date)

    if not sector_data:
        print("WARNING: No sector index data received")
        return {}, {}

    # DataFrameに変換
    df = pd.DataFrame(sector_data)

    # 日付列を変換
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    elif "date" in df.columns:
        df["Date"] = pd.to_datetime(df["date"])
        df = df.drop(columns=["date"])

    # 終値列を確認
    close_col = None
    for col in ["Close", "close", "AdjC"]:
        if col in df.columns:
            close_col = col
            break

    if not close_col:
        print(f"ERROR: Close price column not found. Available columns: {df.columns.tolist()}")
        return {}, {}

    # 業種ごとにMA乖離を計算
    sector_ma_divs = {}

    for sector_code in df["Code"].unique():
        sector_df = df[df["Code"] == sector_code].copy()
        sector_df = sector_df.sort_values("Date")

        if len(sector_df) < max_period:
            continue

        # 移動平均を計算
        ma_div = {}
        current_price = sector_df.iloc[-1][close_col]

        for period in ma_periods:
            ma_value = sector_df[close_col].tail(period).mean()
            if ma_value > 0:
                divergence = (current_price - ma_value) / ma_value * 100
                ma_div[f"ma_{period}"] = divergence

        if ma_div:
            sector_ma_divs[str(sector_code)] = ma_div

    # TOPIXのMA乖離計算
    topix_data = client.get_indices_topix(extended_start, end_date)

    topix_ma_div = {}

    if topix_data and len(topix_data) >= max_period:
        topix_df = pd.DataFrame(topix_data)

        if "Date" in topix_df.columns:
            topix_df["Date"] = pd.to_datetime(topix_df["Date"])
        elif "date" in topix_df.columns:
            topix_df["Date"] = pd.to_datetime(topix_df["date"])

        topix_df = topix_df.sort_values("Date")

        # 終値列を確認
        topix_close_col = None
        for col in ["Close", "close", "AdjC"]:
            if col in topix_df.columns:
                topix_close_col = col
                break

        if topix_close_col:
            current_price = topix_df.iloc[-1][topix_close_col]

            for period in ma_periods:
                ma_value = topix_df[topix_close_col].tail(period).mean()
                if ma_value > 0:
                    divergence = (current_price - ma_value) / ma_value * 100
                    topix_ma_div[f"ma_{period}"] = divergence

    return sector_ma_divs, topix_ma_div


def calculate_rsi(
    client,
    start_date: str,
    end_date: str,
    period: int = 14
) -> Tuple[Dict[str, float], float]:
    """
    RSI（相対力指数）を計算（33業種 + TOPIX）

    Args:
        client: J-Quants APIクライアント
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        period: RSI期間（デフォルト: 14）

    Returns:
        (sector_rsi, topix_rsi)
        - sector_rsi: {業種コード: RSI値}
        - topix_rsi: TOPIXのRSI値
    """
    # データ取得期間を延長（RSI計算のため）
    from datetime import datetime, timedelta
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    extended_start = (start_dt - timedelta(days=period * 2)).strftime("%Y-%m-%d")

    # 33業種指数データを取得
    sector_data = client.get_sector_33_indices(extended_start, end_date)

    if not sector_data:
        print("WARNING: No sector index data received")
        return {}, 0.0

    # DataFrameに変換
    df = pd.DataFrame(sector_data)

    # 日付列を変換
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    elif "date" in df.columns:
        df["Date"] = pd.to_datetime(df["date"])
        df = df.drop(columns=["date"])

    # 終値列を確認
    close_col = None
    for col in ["Close", "close", "AdjC"]:
        if col in df.columns:
            close_col = col
            break

    if not close_col:
        print(f"ERROR: Close price column not found. Available columns: {df.columns.tolist()}")
        return {}, 0.0

    # 業種ごとにRSIを計算
    sector_rsi = {}

    for sector_code in df["Code"].unique():
        sector_df = df[df["Code"] == sector_code].copy()
        sector_df = sector_df.sort_values("Date")

        if len(sector_df) < period + 1:
            continue

        # RSI計算
        rsi_value = _calculate_rsi_series(sector_df[close_col], period)

        if rsi_value is not None:
            sector_rsi[str(sector_code)] = rsi_value

    # TOPIXのRSI計算
    topix_data = client.get_indices_topix(extended_start, end_date)

    topix_rsi = 0.0

    if topix_data and len(topix_data) >= period + 1:
        topix_df = pd.DataFrame(topix_data)

        if "Date" in topix_df.columns:
            topix_df["Date"] = pd.to_datetime(topix_df["Date"])
        elif "date" in topix_df.columns:
            topix_df["Date"] = pd.to_datetime(topix_df["date"])

        topix_df = topix_df.sort_values("Date")

        # 終値列を確認
        topix_close_col = None
        for col in ["Close", "close", "AdjC"]:
            if col in topix_df.columns:
                topix_close_col = col
                break

        if topix_close_col:
            topix_rsi = _calculate_rsi_series(topix_df[topix_close_col], period) or 0.0

    return sector_rsi, topix_rsi


def _calculate_rsi_series(prices: pd.Series, period: int = 14) -> float:
    """
    RSIを計算（内部関数）

    Args:
        prices: 価格のシリーズ
        period: RSI期間

    Returns:
        RSI値（0〜100）
    """
    if len(prices) < period + 1:
        return None

    # 価格変動を計算
    delta = prices.diff()

    # 上昇と下落を分離
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # 平均上昇・平均下落を計算
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    # RS（相対力）を計算
    rs = avg_gain / avg_loss

    # RSIを計算
    rsi = 100 - (100 / (1 + rs))

    # 最新のRSI値を返す
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0  # NaNの場合は中立値


def judge_sector_strength(
    sector_code: str,
    period_return: float,
    ma_div: Dict,
    rsi: float,
    topix_return: float,
    topix_ma_div: Dict,
    topix_rsi: float
) -> Dict:
    """
    セクターの強弱を総合判定

    Args:
        sector_code: 業種コード
        period_return: 期間リターン(%)
        ma_div: MA乖離率 {"ma_25": %, "ma_75": %}
        rsi: RSI値
        topix_return: TOPIXリターン(%)
        topix_ma_div: TOPIXのMA乖離率
        topix_rsi: TOPIXのRSI値

    Returns:
        {
            "sector_code": 業種コード,
            "score": 総合スコア (-3〜+3),
            "strength": "強い" | "普通" | "弱い",
            "details": {
                "return_signal": +1 or -1,
                "ma_signal": +1 or -1,
                "rsi_signal": +1 or -1
            }
        }
    """
    score = 0
    details = {}

    # 1. 期間リターン判定
    return_diff = period_return - topix_return
    if return_diff > 0:
        score += 1
        details["return_signal"] = 1
    else:
        score -= 1
        details["return_signal"] = -1

    # 2. MA乖離判定（25日MAを優先）
    ma_diff = 0
    if "ma_25" in ma_div and "ma_25" in topix_ma_div:
        ma_diff = ma_div["ma_25"] - topix_ma_div["ma_25"]
    elif "ma_75" in ma_div and "ma_75" in topix_ma_div:
        ma_diff = ma_div["ma_75"] - topix_ma_div["ma_75"]

    if ma_diff > 0:
        score += 1
        details["ma_signal"] = 1
    else:
        score -= 1
        details["ma_signal"] = -1

    # 3. RSI判定
    rsi_diff = rsi - topix_rsi
    if rsi_diff > 0:
        score += 1
        details["rsi_signal"] = 1
    else:
        score -= 1
        details["rsi_signal"] = -1

    # 総合判定
    if score >= 2:
        strength = "強い"
    elif score <= -2:
        strength = "弱い"
    else:
        strength = "普通"

    return {
        "sector_code": sector_code,
        "score": score,
        "strength": strength,
        "details": details
    }


def analyze_all_sectors(
    client,
    start_date: str,
    end_date: str
) -> List[Dict]:
    """
    全33業種の強弱を一括分析

    Args:
        client: J-Quants APIクライアント
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）

    Returns:
        分析結果のリスト
        [
            {
                "sector_code": "0040",
                "sector_name": "水産・農林業",
                "period_return": 5.2,
                "ma_div_25": 2.1,
                "ma_div_75": 1.5,
                "rsi": 65.0,
                "topix_relative_return": 3.5,  # TOPIX対比
                "topix_relative_ma_25": 1.2,
                "topix_relative_rsi": 10.0,
                "score": 3,
                "strength": "強い"
            },
            ...
        ]
    """
    from .sector_33_data import get_sector_name

    # 1. 期間リターン計算
    sector_returns, topix_return = calculate_period_return(client, start_date, end_date)

    # 2. MA乖離計算
    sector_ma_divs, topix_ma_div = calculate_ma_divergence(client, start_date, end_date)

    # 3. RSI計算
    sector_rsi, topix_rsi = calculate_rsi(client, start_date, end_date)

    # 4. 統合判定
    results = []

    for sector_code in sector_returns.keys():
        # データが揃っているか確認
        if (sector_code not in sector_ma_divs or
            sector_code not in sector_rsi):
            continue

        period_return = sector_returns[sector_code]
        ma_div = sector_ma_divs[sector_code]
        rsi = sector_rsi[sector_code]

        # 強弱判定
        judgment = judge_sector_strength(
            sector_code,
            period_return,
            ma_div,
            rsi,
            topix_return,
            topix_ma_div,
            topix_rsi
        )

        # 結果をまとめる
        result = {
            "sector_code": sector_code,
            "sector_name": get_sector_name(sector_code),
            "period_return": period_return,
            "ma_div_25": ma_div.get("ma_25", 0),
            "ma_div_75": ma_div.get("ma_75", 0),
            "rsi": rsi,
            "topix_relative_return": period_return - topix_return,
            "topix_relative_ma_25": ma_div.get("ma_25", 0) - topix_ma_div.get("ma_25", 0),
            "topix_relative_rsi": rsi - topix_rsi,
            "score": judgment["score"],
            "strength": judgment["strength"]
        }

        results.append(result)

    # スコア順にソート（降順）
    results = sorted(results, key=lambda x: x["score"], reverse=True)

    return results
