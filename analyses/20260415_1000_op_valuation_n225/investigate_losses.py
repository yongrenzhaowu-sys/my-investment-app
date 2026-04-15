"""
極端な損失を出した銘柄の調査
"""

import pandas as pd
from pathlib import Path

# データパス
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "jquants_historical_6years"

PRICES_PATH = DATA_DIR / "daily_bars_2021_2026.parquet"

# 極端な損失を出した銘柄
loss_stocks = [
    {'Code': '94320', 'Year': 2023, 'EntryPrice': 3949.0, 'ExitPrice': 179.8, 'Return': -95.45},
    {'Code': '94340', 'Year': 2024, 'EntryPrice': 1949.0, 'ExitPrice': 208.4, 'Return': -89.31},
]

def investigate_stock(code, year, entry_price, exit_price):
    """銘柄の詳細を調査"""
    print(f"\n{'='*80}")
    print(f"銘柄コード: {code}")
    print(f"年度: {year}")
    print(f"エントリー価格: {entry_price:,.1f}円")
    print(f"エグジット価格: {exit_price:,.1f}円")
    print(f"損失: {((exit_price - entry_price) / entry_price) * 100:.2f}%")
    print(f"{'='*80}")

    # 株価データ読み込み
    prices = pd.read_parquet(PRICES_PATH)
    prices['Date'] = pd.to_datetime(prices['Date'])

    # 対象銘柄のデータ
    stock_data = prices[prices['Code'] == code].copy()

    if len(stock_data) == 0:
        print(f"ERROR: 銘柄{code}のデータが見つかりません")
        return

    # 調整済み株価
    if 'AdjFactor' in stock_data.columns:
        stock_data['Price'] = stock_data['C'] * stock_data['AdjFactor']
    else:
        stock_data['Price'] = stock_data['C']

    # 期間: エントリー前1ヶ月 ～ エグジット後1ヶ月
    entry_date = pd.to_datetime(f"{year}-04-01")
    exit_date = pd.to_datetime(f"{year + 1}-03-31")

    start_date = entry_date - pd.Timedelta(days=30)
    end_date = exit_date + pd.Timedelta(days=30)

    period_data = stock_data[
        (stock_data['Date'] >= start_date) &
        (stock_data['Date'] <= end_date)
    ].copy()

    print(f"\n株価推移（{start_date.date()} ～ {end_date.date()}）:")
    print(f"  データ件数: {len(period_data)}件")

    if len(period_data) > 0:
        print(f"  最高値: {period_data['Price'].max():,.1f}円 ({period_data.loc[period_data['Price'].idxmax(), 'Date'].date()})")
        print(f"  最安値: {period_data['Price'].min():,.1f}円 ({period_data.loc[period_data['Price'].idxmin(), 'Date'].date()})")
        print(f"  期間開始: {period_data.iloc[0]['Price']:,.1f}円 ({period_data.iloc[0]['Date'].date()})")
        print(f"  期間終了: {period_data.iloc[-1]['Price']:,.1f}円 ({period_data.iloc[-1]['Date'].date()})")

        # 最後の取引日
        last_trade = stock_data.sort_values('Date').iloc[-1]
        print(f"\n最終取引日:")
        print(f"  日付: {last_trade['Date'].date()}")
        print(f"  終値: {last_trade['Price']:,.1f}円")

        # 上場廃止の可能性
        if last_trade['Date'] < pd.to_datetime('2026-03-01'):
            print(f"\n[WARNING] 上場廃止の可能性あり（最終取引日が2026年3月以前）")
        else:
            print(f"\n[OK] 2026年3月以降も取引あり（継続上場）")

    # AdjFactorの変化を確認（株式分割・併合の可能性）
    print(f"\nAdjFactor変化:")
    if 'AdjFactor' in period_data.columns:
        adjfactor_changes = period_data[period_data['AdjFactor'].diff() != 0]
        if len(adjfactor_changes) > 0:
            print(f"  AdjFactorの変化あり（株式分割・併合の可能性）:")
            for idx, row in adjfactor_changes.iterrows():
                print(f"    {row['Date'].date()}: {row['AdjFactor']:.6f}")
        else:
            print(f"  AdjFactorの変化なし")
    else:
        print(f"  AdjFactor列なし")

    # 直近10日の株価
    print(f"\n直近10日の株価:")
    recent = period_data.tail(10)[['Date', 'O', 'H', 'L', 'C', 'Price', 'Vo']].copy()
    print(recent.to_string(index=False))

def main():
    """メイン処理"""
    print("=" * 80)
    print("極端な損失を出した銘柄の調査")
    print("=" * 80)

    for stock in loss_stocks:
        investigate_stock(
            code=stock['Code'],
            year=stock['Year'],
            entry_price=stock['EntryPrice'],
            exit_price=stock['ExitPrice']
        )

    print(f"\n{'='*80}")
    print("調査完了")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
