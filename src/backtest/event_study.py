"""イベントスタディ型バックテスト。"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_returns(df: pd.DataFrame, method: str = "simple") -> pd.DataFrame:
    """リターンを計算する。
    
    Args:
        df: 株価データ（Date, Close列を含む）
        method: "simple" or "log"
        
    Returns:
        Returns列を追加したDataFrame
    """
    df = df.copy()
    df = df.sort_values("Date")
    
    if method == "simple":
        df["Returns"] = df["Close"].pct_change()
    elif method == "log":
        df["Returns"] = np.log(df["Close"] / df["Close"].shift(1))
    else:
        raise ValueError(f"Unknown method: {method}")
    
    return df


def get_event_date(published_at: str) -> datetime:
    """イベント日を取得する（公開日の翌営業日）。
    
    Args:
        published_at: 公開日時（ISO 8601形式）
        
    Returns:
        イベント日（datetime）
    """
    # published_atをdatetimeに変換
    try:
        pub_dt = pd.to_datetime(published_at)
    except Exception as e:
        logger.warning(f"Failed to parse published_at: {published_at}, using today")
        pub_dt = datetime.now()
    
    # 翌日をイベント日とする（実際の営業日判定は株価データで行う）
    event_date = pub_dt + timedelta(days=1)
    
    return event_date


def find_event_index(df: pd.DataFrame, event_date: datetime) -> Optional[int]:
    """イベント日に最も近い営業日のインデックスを取得する。
    
    Args:
        df: 株価データ（Date列を含む）
        event_date: イベント日
        
    Returns:
        インデックス、または見つからない場合はNone
    """
    if df.empty:
        return None
    
    # event_date以降の最初の日を探す
    future_dates = df[df["Date"] >= event_date]
    
    if future_dates.empty:
        return None
    
    return future_dates.index[0]


def calculate_holding_period_return(
    df: pd.DataFrame,
    event_idx: int,
    holding_days: int,
) -> Optional[float]:
    """保有期間リターンを計算する。
    
    Args:
        df: 株価データ（Returns列を含む）
        event_idx: イベント日のインデックス
        holding_days: 保有期間（営業日）
        
    Returns:
        累積リターン、または計算不可の場合はNone
    """
    if event_idx + holding_days >= len(df):
        # データが不足
        return None
    
    # イベント日から holding_days 間のリターンを累積
    returns = df.loc[event_idx:event_idx + holding_days, "Returns"].values[1:]  # 最初の日は含めない
    
    if len(returns) < holding_days:
        return None
    
    # 単純リターンの累積
    cumulative_return = (1 + returns).prod() - 1
    
    return cumulative_return


def run_event_study(
    idea: Dict,
    price_data: Dict[str, pd.DataFrame],
    holding_days: List[int] = [1, 3, 5],
    benchmark_data: Optional[pd.DataFrame] = None,
) -> Dict:
    """イベントスタディ型バックテストを実行する。
    
    Args:
        idea: 投資アイデア
        price_data: {証券コード: DataFrame} の辞書
        holding_days: 保有期間のリスト（営業日）
        benchmark_data: ベンチマークのDataFrame（オプション）
        
    Returns:
        バックテスト結果
    """
    results = {
        "idea_id": idea["id"],
        "tickers": idea["tickers"],
        "published_at": idea["published_at"],
        "event_date": None,
        "holding_periods": {},
        "summary": {},
    }
    
    # イベント日を取得
    event_date = get_event_date(idea["published_at"])
    results["event_date"] = event_date.strftime("%Y-%m-%d")
    
    all_returns = {days: [] for days in holding_days}
    
    # 各銘柄についてリターンを計算
    for code in idea["tickers"]:
        df = price_data.get(code)
        
        if df is None or df.empty:
            logger.warning(f"No price data for {code}")
            continue
        
        # リターン計算
        df = calculate_returns(df)
        
        # イベント日のインデックスを取得
        event_idx = find_event_index(df, event_date)
        
        if event_idx is None:
            logger.warning(f"Event date not found for {code}")
            continue
        
        # 各保有期間についてリターンを計算
        for days in holding_days:
            ret = calculate_holding_period_return(df, event_idx, days)
            
            if ret is not None:
                all_returns[days].append({
                    "code": code,
                    "return": ret,
                })
    
    # 集計
    for days in holding_days:
        returns = all_returns[days]
        
        if not returns:
            results["holding_periods"][f"{days}d"] = {
                "count": 0,
                "mean_return": None,
                "median_return": None,
                "std_return": None,
            }
            continue
        
        return_values = [r["return"] for r in returns]
        
        results["holding_periods"][f"{days}d"] = {
            "count": len(return_values),
            "mean_return": float(np.mean(return_values)),
            "median_return": float(np.median(return_values)),
            "std_return": float(np.std(return_values)),
            "min_return": float(np.min(return_values)),
            "max_return": float(np.max(return_values)),
        }
    
    # サマリー（5日保有期間を代表値とする）
    if "5d" in results["holding_periods"]:
        hp = results["holding_periods"]["5d"]
        results["summary"] = {
            "average_return_5d": hp.get("mean_return"),
            "positive_rate": sum(1 for r in all_returns[5] if r["return"] > 0) / max(len(all_returns[5]), 1),
            "total_tickers": len(idea["tickers"]),
            "valid_tickers": hp.get("count", 0),
        }
    
    return results


def save_backtest_results(results: Dict, output_path: str) -> None:
    """バックテスト結果を保存する。
    
    Args:
        results: バックテスト結果
        output_path: 保存先パス
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved backtest results to {output_path}")
