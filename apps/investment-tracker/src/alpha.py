"""アルファ計算モジュール"""
import pandas as pd
import yfinance as yf
from datetime import datetime
from typing import Tuple
from .api import JQuantsClient


def calculate_alpha(
    client: JQuantsClient,
    code: str,
    purchase_date: str,
    purchase_price: float
) -> Tuple[float, float, float, pd.DataFrame]:
    """
    個別銘柄のアルファを計算

    Args:
        client: J-Quants APIクライアント
        code: 銘柄コード（例: "72030"）
        purchase_date: 購入日（YYYY-MM-DD）
        purchase_price: 購入価格

    Returns:
        (個別騰落率, S&P500騰落率, アルファ, 時系列データフレーム)
    """
    # 1. 個別銘柄の株価取得
    stock_df = client.get_daily_quotes(code, from_date=purchase_date)

    if stock_df.empty:
        raise ValueError(f"銘柄コード {code} のデータが取得できませんでした")

    # 最新の終値
    latest_price = stock_df.iloc[-1]["Close"]
    stock_return = (latest_price - purchase_price) / purchase_price * 100

    # 2. S&P500の取得（yfinance）
    sp500 = yf.download(
        "^GSPC",
        start=purchase_date,
        end=datetime.now().strftime("%Y-%m-%d"),
        progress=False
    )

    if sp500.empty:
        raise ValueError("S&P500データの取得に失敗しました")

    # yfinanceのバージョンによって列構造が異なる可能性があるため、reset_indexしてから処理
    sp500 = sp500.reset_index()

    # Close列を探す（MultiIndexの可能性もあるため）
    if isinstance(sp500.columns, pd.MultiIndex):
        # MultiIndexの場合、flattenする
        sp500.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in sp500.columns.values]
        close_col = [col for col in sp500.columns if 'Close' in col or 'close' in col][0]
    else:
        # 通常のIndexの場合
        if 'Close' in sp500.columns:
            close_col = 'Close'
        elif 'Adj Close' in sp500.columns:
            close_col = 'Adj Close'
        else:
            raise ValueError(f"Close列が見つかりません。利用可能な列: {list(sp500.columns)}")

    # Date列を確認
    date_col = 'Date' if 'Date' in sp500.columns else sp500.columns[0]

    # 購入日のS&P500価格
    sp500_start = sp500.iloc[0][close_col]
    sp500_latest = sp500.iloc[-1][close_col]
    sp500_return = (sp500_latest - sp500_start) / sp500_start * 100

    # 3. アルファ計算
    alpha = stock_return - sp500_return

    # 4. 時系列データフレーム作成（グラフ用）
    # 個別銘柄の騰落率を日次で計算
    stock_df = stock_df.copy()
    stock_df["stock_return"] = (stock_df["Close"] - purchase_price) / purchase_price * 100

    # S&P500の騰落率を日次で計算
    sp500 = sp500[[date_col, close_col]].copy()
    sp500.columns = ["Date", "Close"]
    sp500["sp500_return"] = (sp500["Close"] - sp500_start) / sp500_start * 100

    # マージ
    merged = pd.merge(
        stock_df[["Date", "stock_return"]],
        sp500[["Date", "sp500_return"]],
        on="Date",
        how="inner"
    )
    merged["alpha"] = merged["stock_return"] - merged["sp500_return"]

    return stock_return, sp500_return, alpha, merged
