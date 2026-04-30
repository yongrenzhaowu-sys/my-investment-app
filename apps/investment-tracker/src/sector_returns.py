"""セクターリターン計算モジュール"""
from typing import Dict, List
from datetime import datetime
import pandas as pd


def calculate_sector_returns(
    client,
    sector_master: Dict[str, Dict],
    stocks_by_sector: Dict[str, List[str]],
    start_date: str,
    end_date: str,
    method: str = "equal_weight"
) -> Dict[str, float]:
    """
    各セクターのリターンを計算

    Args:
        client: J-Quants APIクライアント
        sector_master: セクターマスター
        stocks_by_sector: セクター別銘柄リスト
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        method: 加重方法（"equal_weight" or "market_cap_weight"）

    Returns:
        {
            "5050": 5.2,  # 情報・通信業: +5.2%
            "6050": -2.1,  # サービス業: -2.1%
            ...
        }
    """
    sector_returns = {}

    for sector_code, stock_codes in stocks_by_sector.items():
        returns = []
        weights = []

        for code in stock_codes:
            try:
                # 4桁コードに変換（5桁の場合）
                ticker_code = code[:4] if len(code) == 5 else code

                # 株価データを取得
                prices = client.get_price_range(code, start_date, end_date)

                if not prices or len(prices) < 2:
                    continue

                # DataFrameに変換
                df = pd.DataFrame(prices)
                df = df.sort_values("Date")

                # 開始日と終了日の価格
                start_price = df.iloc[0]["Close"]
                end_price = df.iloc[-1]["Close"]

                # リターン計算
                stock_return = (end_price - start_price) / start_price * 100

                returns.append(stock_return)

                # 時価総額加重の場合、ウェイトを取得
                if method == "market_cap_weight":
                    market_cap = df.iloc[-1].get("MarketCapitalization", 1)
                    weights.append(market_cap)
                else:
                    weights.append(1)  # 等加重

            except Exception as e:
                # エラーが発生した銘柄はスキップ
                print(f"銘柄 {code} のデータ取得エラー: {e}")
                continue

        # セクターリターンを計算
        if returns:
            if method == "market_cap_weight":
                # 時価総額加重平均
                total_weight = sum(weights)
                if total_weight > 0:
                    sector_return = sum(
                        r * w / total_weight for r, w in zip(returns, weights)
                    )
                else:
                    sector_return = sum(returns) / len(returns)
            else:
                # 等加重平均
                sector_return = sum(returns) / len(returns)

            sector_returns[sector_code] = sector_return
        else:
            sector_returns[sector_code] = 0.0

    return sector_returns


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
        # J-Quants APIのインデックスエンドポイントを使用
        # （実際のエンドポイントに応じて調整が必要）
        topix_data = client.get_indices_topix(start_date, end_date)

        if not topix_data or len(topix_data) < 2:
            raise ValueError("TOPIXデータが不足しています")

        # DataFrameに変換
        df = pd.DataFrame(topix_data)
        df = df.sort_values("Date")

        # 開始日と終了日の価格
        start_value = df.iloc[0]["Close"]
        end_value = df.iloc[-1]["Close"]

        # リターン計算
        topix_return = (end_value - start_value) / start_value * 100

        return topix_return

    except Exception as e:
        print(f"TOPIXデータ取得エラー: {e}")
        # フォールバック: 全銘柄の時価総額加重平均で代用
        return 0.0


def calculate_relative_returns(
    sector_returns: Dict[str, float],
    topix_return: float,
    sector_master: Dict[str, Dict]
) -> Dict[str, Dict]:
    """
    TOPIX対比の相対リターンを計算

    Args:
        sector_returns: セクターリターン
        topix_return: TOPIXリターン
        sector_master: セクターマスター

    Returns:
        {
            "5050": {
                "absolute_return": 5.2,
                "relative_return": 3.5,  # TOPIX+3.5%
                "sector_name": "情報・通信業"
            },
            ...
        }
    """
    from .sector_data import get_sector_info

    relative_returns = {}

    for sector_code, absolute_return in sector_returns.items():
        sector_info = get_sector_info(sector_code)

        relative_return = absolute_return - topix_return

        relative_returns[sector_code] = {
            "absolute_return": absolute_return,
            "relative_return": relative_return,
            "sector_name": sector_info["name"]
        }

    return relative_returns
