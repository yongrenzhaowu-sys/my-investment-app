"""資産額計算"""
from typing import List, Dict
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd


def get_holdings_at_date(
    target_date: str,
    hypotheses: List[Dict],
    trading_history: List[Dict]
) -> List[Dict]:
    """
    指定日時点の保有銘柄リストを取得

    Args:
        target_date: 対象日（YYYY-MM-DD）
        hypotheses: 現在保有中の銘柄リスト
        trading_history: 売買履歴

    Returns:
        保有銘柄リスト [{"code", "name", "purchase_price", "shares", "purchase_date"}]
    """
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    holdings = []

    # 現在保有中の銘柄で、target_date時点でも保有していたもの
    for hypo in hypotheses:
        purchase_dt = datetime.strptime(hypo["purchase_date"], "%Y-%m-%d")
        if purchase_dt <= target_dt:
            holdings.append({
                "code": hypo["code"],
                "name": hypo["name"],
                "purchase_price": hypo["purchase_price"],
                "shares": hypo.get("shares", 100),
                "purchase_date": hypo["purchase_date"]
            })

    # 売却済み銘柄で、target_date時点では保有していたもの
    for record in trading_history:
        purchase_dt = datetime.strptime(record["purchase_date"], "%Y-%m-%d")
        sell_dt = datetime.strptime(record["sell_date"], "%Y-%m-%d")

        if purchase_dt <= target_dt < sell_dt:
            holdings.append({
                "code": record["code"],
                "name": record["name"],
                "purchase_price": record["purchase_price"],
                "shares": record.get("shares", 100),
                "purchase_date": record["purchase_date"]
            })

    return holdings


def get_stock_price_at_date(code: str, target_date: str) -> float:
    """
    指定日の株価を取得（営業日でない場合は直近の営業日）

    Args:
        code: 銘柄コード
        target_date: 対象日（YYYY-MM-DD）

    Returns:
        株価（取得できない場合は0）
    """
    try:
        # 5桁コードの場合は4桁に変換
        ticker_code = code[:4] if len(code) == 5 else code
        ticker = yf.Ticker(f"{ticker_code}.T")

        # 対象日の前後数日のデータを取得（営業日対応）
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        start_date = (target_dt - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (target_dt + timedelta(days=1)).strftime("%Y-%m-%d")

        hist = ticker.history(start=start_date, end=end_date)

        if hist.empty:
            return 0.0

        # target_date以前の最も近い営業日の終値を取得
        hist_before = hist[hist.index <= target_date]
        if not hist_before.empty:
            return hist_before["Close"].iloc[-1]

        # target_date以前のデータがない場合は、以降の最初のデータを使用
        return hist["Close"].iloc[0]

    except Exception as e:
        print(f"株価取得エラー ({code}, {target_date}): {e}")
        return 0.0


def calculate_cash_at_date(
    target_date: str,
    hypotheses: List[Dict],
    trading_history: List[Dict],
    initial_capital: float,
    additional_capital: float = 0
) -> float:
    """
    指定日時点の現金残高を計算

    Args:
        target_date: 対象日（YYYY-MM-DD）
        hypotheses: 現在保有中の銘柄リスト
        trading_history: 売買履歴
        initial_capital: 初期資金
        additional_capital: 追加投資額

    Returns:
        現金残高
    """
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")

    # 初期資金 + 追加投資額
    cash = initial_capital + additional_capital

    # target_date以前の購入による支出
    for hypo in hypotheses:
        purchase_dt = datetime.strptime(hypo["purchase_date"], "%Y-%m-%d")
        if purchase_dt <= target_dt:
            cash -= hypo["purchase_price"] * hypo.get("shares", 100)

    # 売却済み銘柄で、target_date以前に購入したものの支出
    for record in trading_history:
        purchase_dt = datetime.strptime(record["purchase_date"], "%Y-%m-%d")
        if purchase_dt <= target_dt:
            cash -= record["purchase_price"] * record["shares"]

    # target_date以前の売却による入金
    for record in trading_history:
        sell_dt = datetime.strptime(record["sell_date"], "%Y-%m-%d")
        if sell_dt <= target_dt:
            # 売却額 = 売却価格 × 株数 - 税金
            # = 購入額 + 税引き後利益
            cash += record["purchase_price"] * record["shares"] + record["after_tax_profit"]

    return cash


def calculate_asset_value_at_date(
    target_date: str,
    hypotheses: List[Dict],
    trading_history: List[Dict],
    initial_capital: float,
    additional_capital: float = 0
) -> Dict[str, float]:
    """
    指定日時点の資産額を計算

    Args:
        target_date: 対象日（YYYY-MM-DD）
        hypotheses: 現在保有中の銘柄リスト
        trading_history: 売買履歴
        initial_capital: 初期資金
        additional_capital: 追加投資額

    Returns:
        {
            "date": 対象日,
            "market_value": 時価総額,
            "cash": 現金残高,
            "total_asset": 総資産額,
            "holdings": 保有銘柄詳細
        }
    """
    holdings = get_holdings_at_date(target_date, hypotheses, trading_history)

    market_value = 0.0
    holdings_detail = []

    for holding in holdings:
        price = get_stock_price_at_date(holding["code"], target_date)
        value = price * holding["shares"]
        market_value += value

        holdings_detail.append({
            "code": holding["code"],
            "name": holding["name"],
            "shares": holding["shares"],
            "price": price,
            "value": value
        })

    cash = calculate_cash_at_date(
        target_date, hypotheses, trading_history, initial_capital, additional_capital
    )

    return {
        "date": target_date,
        "market_value": market_value,
        "cash": cash,
        "total_asset": market_value + cash,
        "holdings": holdings_detail
    }


def calculate_asset_change(
    start_date: str,
    hypotheses: List[Dict],
    trading_history: List[Dict],
    initial_capital: float,
    additional_capital: float = 0
) -> Dict[str, float]:
    """
    基準日から現在までの資産増減を計算

    Args:
        start_date: 基準日（YYYY-MM-DD）
        hypotheses: 現在保有中の銘柄リスト
        trading_history: 売買履歴
        initial_capital: 初期資金
        additional_capital: 追加投資額

    Returns:
        {
            "start_date": 基準日,
            "start_asset": 基準日資産額,
            "start_market_value": 基準日時価総額,
            "start_cash": 基準日現金,
            "current_date": 現在日,
            "current_asset": 現在資産額,
            "current_market_value": 現在時価総額,
            "current_cash": 現在現金,
            "change_amount": 増減額,
            "change_rate": 増減率（%）
        }
    """
    # 基準日の資産額
    start_value = calculate_asset_value_at_date(
        start_date, hypotheses, trading_history, initial_capital, additional_capital
    )

    # 現在の資産額
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_value = calculate_asset_value_at_date(
        current_date, hypotheses, trading_history, initial_capital, additional_capital
    )

    change_amount = current_value["total_asset"] - start_value["total_asset"]
    change_rate = (change_amount / start_value["total_asset"] * 100) if start_value["total_asset"] > 0 else 0

    return {
        "start_date": start_date,
        "start_asset": start_value["total_asset"],
        "start_market_value": start_value["market_value"],
        "start_cash": start_value["cash"],
        "start_holdings": start_value["holdings"],
        "current_date": current_date,
        "current_asset": current_value["total_asset"],
        "current_market_value": current_value["market_value"],
        "current_cash": current_value["cash"],
        "current_holdings": current_value["holdings"],
        "change_amount": change_amount,
        "change_rate": change_rate
    }


def get_asset_history(
    start_date: str,
    end_date: str,
    hypotheses: List[Dict],
    trading_history: List[Dict],
    initial_capital: float,
    additional_capital: float = 0
) -> pd.DataFrame:
    """
    期間中の日次資産推移を取得

    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        hypotheses: 現在保有中の銘柄リスト
        trading_history: 売買履歴
        initial_capital: 初期資金
        additional_capital: 追加投資額

    Returns:
        日次資産推移DataFrame（列: date, market_value, cash, total_asset）
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    dates = pd.date_range(start=start_dt, end=end_dt, freq='D')
    history = []

    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        value = calculate_asset_value_at_date(
            date_str, hypotheses, trading_history, initial_capital, additional_capital
        )
        history.append({
            "date": date_str,
            "market_value": value["market_value"],
            "cash": value["cash"],
            "total_asset": value["total_asset"]
        })

    return pd.DataFrame(history)
