"""データモデル定義"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TradingRecord:
    """売買履歴レコード"""
    id: str
    code: str
    name: str
    purchase_date: str
    purchase_price: float
    shares: int
    purchase_reason: str
    sell_date: str
    sell_price: float
    sell_reason: str
    realized_profit: float
    realized_profit_rate: float
    holding_days: int
    tax_amount: float
    after_tax_profit: float
    original_hypothesis_id: str
    created_at: str
    sold_at: str
    kpi_threshold: Optional[float] = None

    def to_dict(self):
        """辞書形式に変換"""
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "purchase_date": self.purchase_date,
            "purchase_price": self.purchase_price,
            "shares": self.shares,
            "purchase_reason": self.purchase_reason,
            "sell_date": self.sell_date,
            "sell_price": self.sell_price,
            "sell_reason": self.sell_reason,
            "realized_profit": self.realized_profit,
            "realized_profit_rate": self.realized_profit_rate,
            "holding_days": self.holding_days,
            "tax_amount": self.tax_amount,
            "after_tax_profit": self.after_tax_profit,
            "original_hypothesis_id": self.original_hypothesis_id,
            "created_at": self.created_at,
            "sold_at": self.sold_at,
            "kpi_threshold": self.kpi_threshold
        }


def calculate_tax(profit: float) -> float:
    """
    株式譲渡所得税を計算

    日本の株式譲渡所得税率:
    - 所得税: 15%
    - 住民税: 5%
    - 復興特別所得税: 0.315%
    - 合計: 20.315%

    Args:
        profit: 実現損益（売却価格 - 購入価格）

    Returns:
        税金額（損失時は0）
    """
    if profit <= 0:
        return 0.0

    tax_rate = 0.20315
    return profit * tax_rate


def calculate_holding_days(purchase_date: str, sell_date: str) -> int:
    """
    保有日数を計算

    Args:
        purchase_date: 購入日（YYYY-MM-DD）
        sell_date: 売却日（YYYY-MM-DD）

    Returns:
        保有日数
    """
    purchase = datetime.strptime(purchase_date, "%Y-%m-%d")
    sell = datetime.strptime(sell_date, "%Y-%m-%d")
    return (sell - purchase).days
