"""投資指標計算モジュール"""
import numpy as np
from typing import List, Dict


def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.001
) -> float:
    """
    シャープレシオを計算

    シャープレシオ = (平均リターン - リスクフリーレート) / リターンの標準偏差
    高いほど、リスクに対するリターンが良い

    Args:
        returns: リターンのリスト（%）
        risk_free_rate: リスクフリーレート（年率、デフォルト0.1%）

    Returns:
        シャープレシオ（データ不足の場合は0）
    """
    if len(returns) < 2:
        return 0.0

    avg_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)  # 不偏標準偏差

    if std_return == 0:
        return 0.0

    return (avg_return - risk_free_rate) / std_return


def calculate_max_drawdown(portfolio_values: List[float]) -> float:
    """
    最大ドローダウンを計算

    最大DD = (ピークからの最大下落額 / ピーク値) × 100
    低いほど良い（下落が小さい）

    Args:
        portfolio_values: 時系列の評価額リスト

    Returns:
        最大ドローダウン（%）
    """
    if len(portfolio_values) < 2:
        return 0.0

    values = np.array(portfolio_values)
    cummax = np.maximum.accumulate(values)
    drawdown = (values - cummax) / cummax
    max_dd = abs(np.min(drawdown)) * 100

    return max_dd


def calculate_win_rate(trading_history: List[Dict]) -> float:
    """
    勝率を計算

    勝率 = (利益が出た取引数 / 全取引数) × 100
    高いほど良い

    Args:
        trading_history: 売買履歴のリスト

    Returns:
        勝率（%）
    """
    if not trading_history:
        return 0.0

    wins = sum(1 for record in trading_history if record.get("realized_profit", 0) > 0)
    total = len(trading_history)

    return (wins / total) * 100


def calculate_avg_holding_days(trading_history: List[Dict]) -> float:
    """
    平均保有日数を計算

    Args:
        trading_history: 売買履歴のリスト

    Returns:
        平均保有日数
    """
    if not trading_history:
        return 0.0

    total_days = sum(record.get("holding_days", 0) for record in trading_history)
    return total_days / len(trading_history)


def calculate_total_return(
    initial_capital: float,
    current_investment: float,
    unrealized_profit: float,
    cumulative_sales: float
) -> float:
    """
    累計リターンを計算

    累計リターン = ((現在の総資産 - 初期資金) / 初期資金) × 100
    現在の総資産 = 現在保有額 + 含み損益 + 累計売却額（税引き後）

    Args:
        initial_capital: 初期資金
        current_investment: 現在保有額（購入価格ベース）
        unrealized_profit: 含み損益
        cumulative_sales: 累計売却額（税引き後）

    Returns:
        累計リターン（%）
    """
    if initial_capital == 0:
        return 0.0

    current_value = current_investment + unrealized_profit + cumulative_sales
    return ((current_value - initial_capital) / initial_capital) * 100


def calculate_profit_factor(trading_history: List[Dict]) -> float:
    """
    プロフィットファクターを計算

    PF = 総利益 / 総損失
    1.0より大きければ利益、小さければ損失

    Args:
        trading_history: 売買履歴のリスト

    Returns:
        プロフィットファクター
    """
    if not trading_history:
        return 0.0

    total_profit = sum(
        record.get("realized_profit", 0)
        for record in trading_history
        if record.get("realized_profit", 0) > 0
    )
    total_loss = abs(sum(
        record.get("realized_profit", 0)
        for record in trading_history
        if record.get("realized_profit", 0) < 0
    ))

    if total_loss == 0:
        return float('inf') if total_profit > 0 else 0.0

    return total_profit / total_loss
