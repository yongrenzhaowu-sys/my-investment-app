"""
日米業種ETFデータ取得（yfinance）

米国11セクターETF + 日本17業種ETF
期間: 2010-01-01 ~ 2025-12-31

注意: yfinance v0.2以降では、デフォルトで調整済み価格が返される
"""
import yfinance as yf
import pandas as pd
from pathlib import Path
from datetime import datetime

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data/raw/us_jp_leadlag"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("="*80)
print("日米業種ETFデータ取得")
print("="*80)

# 米国11セクターETF (Select Sector SPDR ETFs)
us_tickers = [
    'XLB',   # Materials
    'XLC',   # Communication Services
    'XLE',   # Energy
    'XLF',   # Financials
    'XLI',   # Industrials
    'XLK',   # Information Technology
    'XLP',   # Consumer Staples
    'XLRE',  # Real Estate
    'XLU',   # Utilities
    'XLV',   # Health Care
    'XLY',   # Consumer Discretionary
]

# 日本17業種ETF (NEXT FUNDS TOPIX-17)
jp_tickers = [
    '1617.T',  # 食品
    '1618.T',  # エネルギー資源
    '1619.T',  # 建設・資材
    '1620.T',  # 素材・化学
    '1621.T',  # 医薬品
    '1622.T',  # 自動車・輸送機
    '1623.T',  # 鉄鋼・非鉄
    '1624.T',  # 機械
    '1625.T',  # 電機・精密
    '1626.T',  # 情報通信・サービスその他
    '1627.T',  # 電力・ガス
    '1628.T',  # 運輸・物流
    '1629.T',  # 商社・卸売
    '1630.T',  # 小売
    '1631.T',  # 銀行
    '1632.T',  # 金融（除く銀行）
    '1633.T',  # 不動産
]

# データ取得期間
start_date = '2010-01-01'
end_date = '2025-12-31'

print(f"\n[1] 米国11セクターETFデータ取得")
print(f"  期間: {start_date} ~ {end_date}")

us_data_list = []
for ticker in us_tickers:
    try:
        print(f"  取得中: {ticker}...", end='')
        data = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)

        # インデックスをリセット
        data = data.reset_index()

        # MultiIndex列をフラット化（最初の要素を使用）
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        # 列名の確認と統一
        # yfinance v0.2+ では auto_adjust=True でOpen, High, Low, Close, Volumeが返される
        required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        data = data[required_cols]
        data['Ticker'] = ticker

        print(f" {len(data)}日")
        us_data_list.append(data)
    except Exception as e:
        print(f" エラー: {e}")

# 結合
us_df = pd.concat(us_data_list, ignore_index=True)
print(f"  合計: {len(us_df)}レコード")

# 保存
us_output_path = OUTPUT_DIR / "us_sectors.parquet"
us_df.to_parquet(us_output_path, index=False)
print(f"  保存: {us_output_path}")

print(f"\n[2] 日本17業種ETFデータ取得")
print(f"  期間: {start_date} ~ {end_date}")

jp_data_list = []
for ticker in jp_tickers:
    try:
        print(f"  取得中: {ticker}...", end='')
        data = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)

        # インデックスをリセット
        data = data.reset_index()

        # MultiIndex列をフラット化（最初の要素を使用）
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        # 必要な列のみ選択
        required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        data = data[required_cols]
        data['Ticker'] = ticker

        print(f" {len(data)}日")
        jp_data_list.append(data)
    except Exception as e:
        print(f" エラー: {e}")

# 結合
jp_df = pd.concat(jp_data_list, ignore_index=True)
print(f"  合計: {len(jp_df)}レコード")

# 保存
jp_output_path = OUTPUT_DIR / "jp_sectors.parquet"
jp_df.to_parquet(jp_output_path, index=False)
print(f"  保存: {jp_output_path}")

# サマリー表示
print(f"\n[3] データ概要")
print(f"  米国: {us_df['Ticker'].nunique()}銘柄 × {len(us_df['Date'].unique())}日 = {len(us_df):,}レコード")
print(f"  日本: {jp_df['Ticker'].nunique()}銘柄 × {len(jp_df['Date'].unique())}日 = {len(jp_df):,}レコード")

print("\n完了")
