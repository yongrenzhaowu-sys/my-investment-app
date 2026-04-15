"""
リスク管理とポジションサイジング

ボラティリティ（またはATR）に基づく逆相関ウェイト配分
"""
import pandas as pd
import numpy as np
from typing import Optional


def calculate_position_sizes(
    stocks: pd.DataFrame,
    target_gross: float = 1.0,
    min_weight: float = 0.02,
    max_weight: float = 0.08,
    risk_measure: str = "volatility",
) -> pd.DataFrame:
    """
    推奨銘柄のポジションサイズを計算（inverse-volatility weighting）

    Args:
        stocks: 推奨銘柄のDataFrame（Volatility20, ATR14, AdjCを含む）
        target_gross: 総エクスポージャー（デフォルト1.0 = 100%）
        min_weight: 最小ウェイト（デフォルト2%）
        max_weight: 最大ウェイト（デフォルト8%）
        risk_measure: リスク指標（"volatility" or "atr"）

    Returns:
        pd.DataFrame: weight, stop_distance, risk_amountを追加したDataFrame
    """
    df = stocks.copy()

    # リスク指標の選択
    if risk_measure == "volatility":
        risk_col = "Volatility20"
    elif risk_measure == "atr":
        # ATR/Close で%ATRを計算
        if "ATR14" not in df.columns or "AdjC" not in df.columns:
            raise ValueError("ATR使用にはATR14とAdjCが必要です")
        df["pct_atr"] = df["ATR14"] / df["AdjC"]
        risk_col = "pct_atr"
    else:
        raise ValueError(f"不明なrisk_measure: {risk_measure}")

    if risk_col not in df.columns:
        raise ValueError(f"{risk_col}列が存在しません")

    # 逆数ウェイト（リスクが低いほど大きなポジション）
    df["inv_risk"] = 1.0 / df[risk_col].replace(0, np.nan)
    df["inv_risk"] = df["inv_risk"].fillna(0)

    # 未正規化ウェイト
    total_inv_risk = df["inv_risk"].sum()
    if total_inv_risk == 0:
        # 全てゼロの場合は均等配分
        df["weight_raw"] = target_gross / len(df)
    else:
        df["weight_raw"] = (df["inv_risk"] / total_inv_risk) * target_gross

    # クリッピング
    df["weight"] = df["weight_raw"].clip(min_weight, max_weight)

    # 再正規化（クリッピング後の合計をtarget_grossに戻す）
    total_weight = df["weight"].sum()
    if total_weight > 0:
        df["weight"] = (df["weight"] / total_weight) * target_gross

    # ストップ距離（例：2×ATR14）
    if "ATR14" in df.columns:
        df["stop_distance"] = 2.0 * df["ATR14"]
    else:
        df["stop_distance"] = np.nan

    # リスク額の参考値（仮にportfolio_value=1として）
    # 実際の円建ては呼び出し側でportfolio_value_jpyを掛ける
    df["risk_amount_pct"] = df["weight"] * 0.02  # 例：各銘柄で2%リスク

    return df
