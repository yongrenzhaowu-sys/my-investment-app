"""損益計算"""
from typing import List, Dict, Optional
from .trading_history import load_trading_history
import yfinance as yf
from datetime import datetime


def calculate_realized_profit() -> Dict[str, float]:
    """
    実現損益を計算

    Returns:
        {
            "total_profit": 累計実現損益,
            "total_tax": 累計税金,
            "after_tax_profit": 税引き後利益,
            "count": 売却済み銘柄数
        }
    """
    history = load_trading_history()

    if not history:
        return {
            "total_profit": 0.0,
            "total_tax": 0.0,
            "after_tax_profit": 0.0,
            "count": 0
        }

    total_profit = sum(record["realized_profit"] for record in history)
    total_tax = sum(record["tax_amount"] for record in history)
    after_tax_profit = sum(record["after_tax_profit"] for record in history)

    return {
        "total_profit": total_profit,
        "total_tax": total_tax,
        "after_tax_profit": after_tax_profit,
        "count": len(history)
    }


def calculate_unrealized_profit(hypotheses: List[Dict]) -> Dict[str, float]:
    """
    含み損益を計算

    Args:
        hypotheses: 保持中の仮説リスト

    Returns:
        {
            "total_unrealized": 累計含み損益,
            "count": 保持中銘柄数,
            "details": 銘柄別の含み損益
        }
    """
    if not hypotheses:
        return {
            "total_unrealized": 0.0,
            "count": 0,
            "details": []
        }

    details = []
    total_unrealized = 0.0

    for hypo in hypotheses:
        code = hypo["code"]
        purchase_price = hypo["purchase_price"]
        shares = hypo.get("shares", 100)  # デフォルト100株

        # 現在価格を取得
        try:
            # 5桁コードの場合は4桁に変換
            ticker_code = code[:4] if len(code) == 5 else code
            ticker = yf.Ticker(f"{ticker_code}.T")
            hist = ticker.history(period="1d")

            if not hist.empty:
                current_price = hist["Close"].iloc[-1]
                unrealized_per_share = current_price - purchase_price
                unrealized = unrealized_per_share * shares
                unrealized_rate = (unrealized_per_share / purchase_price) * 100 if purchase_price > 0 else 0

                details.append({
                    "code": code,
                    "name": hypo.get("name", f"銘柄{code}"),
                    "purchase_price": purchase_price,
                    "shares": shares,
                    "current_price": current_price,
                    "unrealized_profit": unrealized,
                    "unrealized_profit_rate": unrealized_rate
                })

                total_unrealized += unrealized
        except Exception as e:
            print(f"価格取得エラー ({code}): {e}")
            # エラー時は0として扱う
            details.append({
                "code": code,
                "name": hypo.get("name", f"銘柄{code}"),
                "purchase_price": purchase_price,
                "shares": shares,
                "current_price": purchase_price,
                "unrealized_profit": 0.0,
                "unrealized_profit_rate": 0.0
            })

    return {
        "total_unrealized": total_unrealized,
        "count": len(hypotheses),
        "details": details
    }


def calculate_total_profit(hypotheses: List[Dict]) -> Dict[str, float]:
    """
    合計損益を計算

    Args:
        hypotheses: 保持中の仮説リスト

    Returns:
        {
            "realized": 実現損益,
            "unrealized": 含み損益,
            "total": 合計損益
        }
    """
    realized = calculate_realized_profit()
    unrealized = calculate_unrealized_profit(hypotheses)

    return {
        "realized": realized["after_tax_profit"],
        "unrealized": unrealized["total_unrealized"],
        "total": realized["after_tax_profit"] + unrealized["total_unrealized"]
    }


def calculate_available_capital(
    hypotheses: List[Dict],
    initial_capital: float = 1_000_000
) -> Dict[str, float]:
    """
    余力を計算

    Args:
        hypotheses: 保持中の仮説リスト
        initial_capital: 初期資金（デフォルト: 100万円）

    Returns:
        {
            "initial_capital": 初期資金,
            "current_investment": 現在保有額,
            "cumulative_sales": 累計売却額（税引き後）,
            "available_capital": 余力
        }
    """
    # 現在保有額（購入価格 × 株数）
    current_investment = sum(
        hypo["purchase_price"] * hypo.get("shares", 100) for hypo in hypotheses
    )

    # 累計売却額（税引き後）
    history = load_trading_history()
    cumulative_sales = sum(
        record["sell_price"] - record["tax_amount"]
        for record in history
    )

    # 余力
    available_capital = initial_capital - current_investment + cumulative_sales

    return {
        "initial_capital": initial_capital,
        "current_investment": current_investment,
        "cumulative_sales": cumulative_sales,
        "available_capital": available_capital
    }


def calculate_yearly_profit(year: int) -> Dict[str, float]:
    """
    年間損益を計算（確定申告用）

    Args:
        year: 年（例: 2026）

    Returns:
        {
            "total_profit": 年間実現損益,
            "total_tax": 年間税金,
            "after_tax_profit": 税引き後利益,
            "count": 売却件数
        }
    """
    history = load_trading_history()
    yearly_records = [
        record for record in history
        if record["sell_date"].startswith(str(year))
    ]

    if not yearly_records:
        return {
            "total_profit": 0.0,
            "total_tax": 0.0,
            "after_tax_profit": 0.0,
            "count": 0
        }

    total_profit = sum(record["realized_profit"] for record in yearly_records)
    total_tax = sum(record["tax_amount"] for record in yearly_records)
    after_tax_profit = sum(record["after_tax_profit"] for record in yearly_records)

    return {
        "total_profit": total_profit,
        "total_tax": total_tax,
        "after_tax_profit": after_tax_profit,
        "count": len(yearly_records)
    }
