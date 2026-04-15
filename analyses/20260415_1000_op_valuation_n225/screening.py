"""
営業利益バリュエーション検証（日経225）

仮説: 過去5年間の営業利益が増益基調の会社において、
     営業利益×10と時価総額の乖離が大きいと、割安と判定できる
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# データパス
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "jquants_historical_6years"

PRICES_PATH = DATA_DIR / "daily_bars_2021_2026.parquet"
FINANCIALS_PATH = DATA_DIR / "financials_2021_2026.parquet"

def load_data():
    """データ読み込み"""
    print("データ読み込み中...")

    # 株価データ
    prices = pd.read_parquet(PRICES_PATH)

    # Date列を日付型に変換（CRITICAL）
    prices['Date'] = pd.to_datetime(prices['Date'])

    print(f"株価データ: {len(prices):,}レコード")
    print(f"  列: {prices.columns.tolist()}")
    print(f"  期間: {prices['Date'].min()} ～ {prices['Date'].max()}")
    print(f"  銘柄数: {prices['Code'].nunique()}")

    # 財務データ
    financials = pd.read_parquet(FINANCIALS_PATH)

    # 開示日列を日付型に変換
    if 'DiscDate' in financials.columns:
        financials['DiscDate'] = pd.to_datetime(financials['DiscDate'])
        print(f"\n財務データ: {len(financials):,}レコード")
        print(f"  列: {financials.columns.tolist()}")
        print(f"  期間: {financials['DiscDate'].min()} ～ {financials['DiscDate'].max()}")
    elif 'DisclosedDate' in financials.columns:
        financials['DisclosedDate'] = pd.to_datetime(financials['DisclosedDate'])
        print(f"\n財務データ: {len(financials):,}レコード")
        print(f"  列: {financials.columns.tolist()}")
        print(f"  期間: {financials['DisclosedDate'].min()} ～ {financials['DisclosedDate'].max()}")
    else:
        print(f"\n財務データ: {len(financials):,}レコード")
        print(f"  列: {financials.columns.tolist()}")

    # 決算期列を日付型に変換
    if 'CurPerEn' in financials.columns:
        financials['CurPerEn'] = pd.to_datetime(financials['CurPerEn'])

    print(f"  銘柄数: {financials['Code'].nunique()}")

    return prices, financials

def get_nikkei225_proxy(prices, financials, base_date='2026-03-31'):
    """
    日経225の代替リスト取得

    注: 正確な日経225構成銘柄ではなく、東証プライム時価総額上位225銘柄で代替

    Args:
        prices: 株価データ
        financials: 財務データ
        base_date: 基準日（時価総額計算用）

    Returns:
        日経225代替銘柄のCodeリスト
    """
    print(f"\n日経225代替リスト作成（{base_date}時点）...")

    # 基準日の株価データ取得
    base_date_dt = pd.to_datetime(base_date)

    # 基準日以前の最新データ
    prices_subset = prices[prices['Date'] <= base_date_dt].copy()

    # 調整済み株価の正しい計算（CRITICAL）
    if 'AdjFactor' in prices_subset.columns:
        prices_subset['AdjC_Correct'] = prices_subset['C'] * prices_subset['AdjFactor']
        prices_subset['Price'] = prices_subset['AdjC_Correct']
    else:
        prices_subset['Price'] = prices_subset['C']

    # 各銘柄の最新株価
    latest_prices = prices_subset.sort_values(['Code', 'Date']).groupby('Code').last().reset_index()

    # 時価総額計算（価格 × 上場株式数）
    # Note: 上場株式数データがない場合は、出来高をプロキシとして使用
    if 'IssuedShareEquityQuote' in latest_prices.columns:
        latest_prices['MarketCap'] = latest_prices['Price'] * latest_prices['IssuedShareEquityQuote']
    elif 'Vo' in latest_prices.columns:
        # 出来高が大きい = 流動性が高い = 大型株として代替
        latest_prices['MarketCap'] = latest_prices['Price'] * latest_prices['Vo'] * 100  # スケール調整
    else:
        print("WARNING: 時価総額計算に必要なデータがありません")
        return []

    # 時価総額上位225銘柄
    top225 = latest_prices.nlargest(225, 'MarketCap')

    print(f"  対象銘柄数: {len(top225)}")
    print(f"  時価総額範囲: {top225['MarketCap'].min():,.0f} ～ {top225['MarketCap'].max():,.0f}")

    return top225['Code'].tolist()

def calculate_operating_profit_growth(financials, target_codes, reference_date='2026-03-31'):
    """
    過去5年間の営業利益成長を計算

    Args:
        financials: 財務データ
        target_codes: 対象銘柄コードリスト
        reference_date: 基準日（この日までに発表された決算のみ使用）

    Returns:
        営業利益データ（Code, 各年度の営業利益、成長指標）
    """
    print(f"\n営業利益成長計算（{reference_date}基準）...")

    # 対象銘柄のみ
    df = financials[financials['Code'].isin(target_codes)].copy()

    # 開示日でフィルタ（ルックアヘッドバイアス防止）
    reference_dt = pd.to_datetime(reference_date)
    if 'DiscDate' in df.columns:
        df = df[df['DiscDate'] <= reference_dt]
        print(f"  開示日フィルタ後: {len(df):,}レコード")
    elif 'DisclosedDate' in df.columns:
        df = df[df['DisclosedDate'] <= reference_dt]
        print(f"  開示日フィルタ後: {len(df):,}レコード")

    # 営業利益列の特定
    op_col = None
    for col in ['OperatingProfit', 'OP', 'operating_profit']:
        if col in df.columns:
            op_col = col
            break

    if op_col is None:
        print(f"ERROR: 営業利益列が見つかりません。利用可能な列: {df.columns.tolist()}")
        return pd.DataFrame()

    print(f"  営業利益列: {op_col}")

    # 決算期列の特定
    period_col = None
    for col in ['CurPerEn', 'FiscalPeriodEnd', 'CurrentFiscalYearEndDate', 'fiscal_period_end']:
        if col in df.columns:
            period_col = col
            break

    if period_col is None:
        print(f"ERROR: 決算期列が見つかりません。利用可能な列: {df.columns.tolist()}")
        return pd.DataFrame()

    print(f"  決算期列: {period_col}")

    # 決算期を日付型に変換
    df[period_col] = pd.to_datetime(df[period_col], errors='coerce')

    # 営業利益を数値に変換
    df[op_col] = pd.to_numeric(df[op_col], errors='coerce')

    # nullまたは0を除外
    df = df[df[op_col].notna() & (df[op_col] != 0)]

    # 決算期でソート
    df = df.sort_values(['Code', period_col])

    # 各銘柄の過去5年分の決算を取得
    results = []

    for code in target_codes:
        code_data = df[df['Code'] == code].copy()

        if len(code_data) < 2:  # 最低2期必要
            continue

        # 最新5期
        recent = code_data.tail(5)

        if len(recent) < 3:  # 最低3期必要
            continue

        # 各年度の営業利益
        op_values = recent[op_col].values

        # 増益基調の判定
        # パターンA: 5年間で4回以上増益
        growth_count = sum(op_values[i] > op_values[i-1] for i in range(1, len(op_values)))
        is_growth_a = growth_count >= min(4, len(op_values) - 1)

        # パターンB: 直近3年連続増益
        is_growth_b = False
        if len(op_values) >= 3:
            is_growth_b = (op_values[-1] > op_values[-2]) and (op_values[-2] > op_values[-3])

        # パターンC: CAGR > 0%
        if len(op_values) >= 2:
            years = len(op_values) - 1
            cagr = (op_values[-1] / op_values[0]) ** (1 / years) - 1
        else:
            cagr = 0
        is_growth_c = cagr > 0

        results.append({
            'Code': code,
            'LatestOP': op_values[-1],
            'OldestOP': op_values[0],
            'NumPeriods': len(op_values),
            'GrowthCount': growth_count,
            'IsGrowthA': is_growth_a,
            'IsGrowthB': is_growth_b,
            'CAGR': cagr,
            'IsGrowthC': is_growth_c,
        })

    result_df = pd.DataFrame(results)

    print(f"\n  営業利益データ取得: {len(result_df)}銘柄")
    print(f"  増益基調A（5年で4回以上増益）: {result_df['IsGrowthA'].sum()}銘柄")
    print(f"  増益基調B（直近3年連続増益）: {result_df['IsGrowthB'].sum()}銘柄")
    print(f"  増益基調C（CAGR > 0%）: {result_df['IsGrowthC'].sum()}銘柄")

    return result_df

def calculate_valuation_gap(op_data, prices, base_date='2026-03-31'):
    """
    割安度（営業利益×10 vs 時価総額）を計算

    Args:
        op_data: 営業利益データ
        prices: 株価データ
        base_date: 基準日

    Returns:
        割安度データ
    """
    print(f"\n割安度計算（{base_date}時点）...")

    # 基準日の株価データ
    base_date_dt = pd.to_datetime(base_date)
    prices_subset = prices[prices['Date'] <= base_date_dt].copy()

    # 調整済み株価の正しい計算（CRITICAL）
    if 'AdjFactor' in prices_subset.columns:
        prices_subset['AdjC_Correct'] = prices_subset['C'] * prices_subset['AdjFactor']
        prices_subset['Price'] = prices_subset['AdjC_Correct']
    else:
        prices_subset['Price'] = prices_subset['C']

    # 各銘柄の最新株価
    latest_prices = prices_subset.sort_values(['Code', 'Date']).groupby('Code').last().reset_index()

    # 時価総額計算
    if 'IssuedShareEquityQuote' in latest_prices.columns:
        latest_prices['MarketCap'] = latest_prices['Price'] * latest_prices['IssuedShareEquityQuote']
    elif 'Vo' in latest_prices.columns:
        latest_prices['MarketCap'] = latest_prices['Price'] * latest_prices['Vo'] * 100
    else:
        print("ERROR: 時価総額計算に必要なデータがありません")
        return pd.DataFrame()

    # 営業利益データとマージ
    result = op_data.merge(
        latest_prices[['Code', 'MarketCap', 'Price', 'Date']],
        on='Code',
        how='left'
    )

    # 時価総額データがない銘柄を除外
    result = result[result['MarketCap'].notna()]

    # 割安度スコア計算
    # スコア = (営業利益 × 10 - 時価総額) / 時価総額
    result['TheoreticalValue'] = result['LatestOP'] * 10
    result['ValuationGap'] = (result['TheoreticalValue'] - result['MarketCap']) / result['MarketCap']

    # PER風の指標も計算
    result['MarketCap_to_OP'] = result['MarketCap'] / result['LatestOP']

    print(f"  割安度計算完了: {len(result)}銘柄")
    print(f"  割安度スコア範囲: {result['ValuationGap'].min():.2f} ～ {result['ValuationGap'].max():.2f}")
    print(f"  時価総額/営業利益範囲: {result['MarketCap_to_OP'].min():.2f}倍 ～ {result['MarketCap_to_OP'].max():.2f}倍")

    return result

def main():
    """メイン処理"""
    print("=" * 80)
    print("営業利益バリュエーション検証（日経225）")
    print("=" * 80)

    # データ読み込み
    prices, financials = load_data()

    # 日経225代替リスト取得
    nikkei225_codes = get_nikkei225_proxy(prices, financials, base_date='2026-03-31')

    if len(nikkei225_codes) == 0:
        print("ERROR: 日経225代替リストを取得できませんでした")
        return

    # 営業利益成長計算
    op_growth = calculate_operating_profit_growth(
        financials,
        nikkei225_codes,
        reference_date='2026-03-31'
    )

    if len(op_growth) == 0:
        print("ERROR: 営業利益データを取得できませんでした")
        return

    # 割安度計算
    valuation = calculate_valuation_gap(op_growth, prices, base_date='2026-03-31')

    if len(valuation) == 0:
        print("ERROR: 割安度を計算できませんでした")
        return

    # 結果保存
    output_dir = Path(__file__).parent
    output_path = output_dir / "screening_results_20260331.csv"

    valuation_sorted = valuation.sort_values('ValuationGap', ascending=False)
    valuation_sorted.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\n結果保存: {output_path}")

    # サマリー表示
    print("\n" + "=" * 80)
    print("増益基調銘柄の割安度ランキング（上位20銘柄）")
    print("=" * 80)

    # 増益基調A（5年で4回以上増益）の銘柄
    growth_stocks = valuation_sorted[valuation_sorted['IsGrowthA']].copy()

    print(f"\n【増益基調A: 5年間で4回以上増益】{len(growth_stocks)}銘柄")
    print("\n割安度上位20銘柄:")
    print(growth_stocks.head(20)[
        ['Code', 'LatestOP', 'MarketCap', 'TheoreticalValue', 'ValuationGap', 'MarketCap_to_OP', 'CAGR']
    ].to_string())

    # 増益基調B（直近3年連続増益）の銘柄
    growth_stocks_b = valuation_sorted[valuation_sorted['IsGrowthB']].copy()

    print(f"\n\n【増益基調B: 直近3年連続増益】{len(growth_stocks_b)}銘柄")
    print("\n割安度上位20銘柄:")
    print(growth_stocks_b.head(20)[
        ['Code', 'LatestOP', 'MarketCap', 'TheoreticalValue', 'ValuationGap', 'MarketCap_to_OP', 'CAGR']
    ].to_string())

    print("\n" + "=" * 80)
    print("完了")
    print("=" * 80)

if __name__ == "__main__":
    main()
