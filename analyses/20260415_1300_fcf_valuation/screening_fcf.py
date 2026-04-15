"""
現金+FCF×10バリュエーション スクリーニング

FCF (Free Cash Flow) = CFO - CFI
理論的価値 = 現金 + FCF×10
割安度スコア = (理論的価値 - 時価総額) / 時価総額
"""

import pandas as pd
import numpy as np
from pathlib import Path

# データパス
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "jquants_historical_6years"

PRICES_PATH = DATA_DIR / "daily_bars_2021_2026.parquet"
FINANCIALS_PATH = DATA_DIR / "financials_2021_2026.parquet"

def load_data():
    """データ読み込み"""
    print("データ読み込み中...")

    prices = pd.read_parquet(PRICES_PATH)
    prices['Date'] = pd.to_datetime(prices['Date'])

    financials = pd.read_parquet(FINANCIALS_PATH)
    financials['DiscDate'] = pd.to_datetime(financials['DiscDate'])
    financials['CurPerEn'] = pd.to_datetime(financials['CurPerEn'])

    return prices, financials

def classify_by_market_cap(prices, base_date, min_market_cap=10e9):
    """時価総額分類"""
    base_date_dt = pd.to_datetime(base_date)
    prices_subset = prices[prices['Date'] <= base_date_dt].copy()

    if 'AdjFactor' in prices_subset.columns:
        prices_subset['Price'] = prices_subset['C'] * prices_subset['AdjFactor']
    else:
        prices_subset['Price'] = prices_subset['C']

    latest_prices = prices_subset.sort_values(['Code', 'Date']).groupby('Code').last().reset_index()
    latest_prices['MarketCap'] = latest_prices['Price'] * latest_prices['Vo'] * 100
    latest_prices = latest_prices[latest_prices['MarketCap'] >= min_market_cap]

    large_cap_threshold = latest_prices['MarketCap'].quantile(0.70)
    small_cap_threshold = latest_prices['MarketCap'].quantile(0.30)

    latest_prices['CapGroup'] = 'Mid'
    latest_prices.loc[latest_prices['MarketCap'] >= large_cap_threshold, 'CapGroup'] = 'Large'
    latest_prices.loc[latest_prices['MarketCap'] <= small_cap_threshold, 'CapGroup'] = 'Small'

    return latest_prices[['Code', 'MarketCap', 'CapGroup']]

def calculate_fcf_scores(financials, target_codes, reference_date='2026-03-31'):
    """
    FCFスクリーニングスコア計算

    Returns:
        DataFrame with Code, FCF, CashEq, EquityRatio
    """
    print(f"\nFCFスクリーニング（{reference_date}基準）...")

    reference_dt = pd.to_datetime(reference_date)

    df = financials[financials['Code'].isin(target_codes)].copy()
    df = df[df['DiscDate'] <= reference_dt]

    # CFデータを数値に変換
    df['CFO'] = pd.to_numeric(df['CFO'], errors='coerce')
    df['CFI'] = pd.to_numeric(df['CFI'], errors='coerce')
    df['CashEq'] = pd.to_numeric(df['CashEq'], errors='coerce')

    # 自己資本比率
    df['TA'] = pd.to_numeric(df['TA'], errors='coerce')
    df['Eq'] = pd.to_numeric(df['Eq'], errors='coerce')
    df['EquityRatio'] = df['Eq'] / df['TA']

    # FCF計算
    df['FCF'] = df['CFO'] - df['CFI']

    # 欠損を除外
    df = df[df['FCF'].notna() & df['CashEq'].notna()]

    # FCF > 0でフィルタ（CRITICAL）
    df = df[df['FCF'] > 0]

    # 現金 > 0でフィルタ
    df = df[df['CashEq'] > 0]

    # 決算期でソート
    df = df.sort_values(['Code', 'CurPerEn'])

    results = []

    for code in target_codes:
        code_data = df[df['Code'] == code].copy()

        if len(code_data) == 0:
            continue

        # 最新データ
        latest = code_data.iloc[-1]

        results.append({
            'Code': code,
            'FCF': latest['FCF'],
            'CashEq': latest['CashEq'],
            'EquityRatio': latest['EquityRatio'],
        })

    result_df = pd.DataFrame(results)

    print(f"  FCFデータ取得: {len(result_df)}銘柄")
    print(f"  FCF範囲: {result_df['FCF'].min() / 1e9:.1f}億円 ～ {result_df['FCF'].max() / 1e9:.1f}億円")
    print(f"  現金範囲: {result_df['CashEq'].min() / 1e9:.1f}億円 ～ {result_df['CashEq'].max() / 1e9:.1f}億円")

    return result_df

def calculate_fcf_valuation(fcf_data, market_cap_data):
    """
    FCFバリュエーション計算

    理論的価値 = 現金 + FCF×10
    割安度スコア = (理論的価値 - 時価総額) / 時価総額
    """
    result = fcf_data.merge(
        market_cap_data[['Code', 'MarketCap', 'CapGroup']],
        on='Code',
        how='left'
    )

    result = result[result['MarketCap'].notna() & (result['MarketCap'] > 0)]

    # 理論的価値
    result['TheoreticalValue'] = result['CashEq'] + result['FCF'] * 10

    # 割安度スコア
    result['ValuationGap'] = (result['TheoreticalValue'] - result['MarketCap']) / result['MarketCap']

    # 現金比率
    result['CashRatio'] = result['CashEq'] / result['MarketCap']

    # FCF利回り
    result['FCFYield'] = result['FCF'] / result['MarketCap']

    return result

def main():
    """メイン処理"""
    print("=" * 80)
    print("現金+FCF×10バリュエーション スクリーニング")
    print("=" * 80)

    # データ読み込み
    prices, financials = load_data()

    # 時価総額分類
    print(f"\n時価総額分類（2026-03-31時点）...")
    market_cap_data = classify_by_market_cap(prices, base_date='2026-03-31', min_market_cap=10e9)

    # 中型株のみを対象（営業利益×10との比較のため）
    mid_cap_codes = market_cap_data[market_cap_data['CapGroup'] == 'Mid']['Code'].tolist()
    print(f"  中型株: {len(mid_cap_codes)}銘柄")

    # FCFスクリーニング
    fcf_scores = calculate_fcf_scores(financials, mid_cap_codes, reference_date='2026-03-31')

    if len(fcf_scores) == 0:
        print("ERROR: FCFデータを取得できませんでした")
        return

    # FCFバリュエーション
    print(f"\nFCFバリュエーション計算...")
    fcf_valuation = calculate_fcf_valuation(fcf_scores, market_cap_data)

    print(f"  バリュエーション計算完了: {len(fcf_valuation)}銘柄")
    print(f"  割安度スコア範囲: {fcf_valuation['ValuationGap'].min():.2f} ～ {fcf_valuation['ValuationGap'].max():.2f}")

    # 自己資本比率 > 20%でフィルタ
    fcf_valuation = fcf_valuation[fcf_valuation['EquityRatio'] >= 0.20]
    print(f"  自己資本比率20%以上: {len(fcf_valuation)}銘柄")

    # 割安度上位銘柄
    top_stocks = fcf_valuation.nlargest(20, 'ValuationGap')

    print(f"\n{'='*80}")
    print("割安度上位20銘柄（現金+FCF×10）")
    print(f"{'='*80}")
    print(top_stocks[[
        'Code', 'FCF', 'CashEq', 'MarketCap', 'TheoreticalValue',
        'ValuationGap', 'CashRatio', 'FCFYield', 'EquityRatio'
    ]].to_string(index=False))

    # 結果保存
    output_dir = Path(__file__).parent
    output_path = output_dir / "screening_results_fcf_20260331.csv"

    fcf_valuation_sorted = fcf_valuation.sort_values('ValuationGap', ascending=False)
    fcf_valuation_sorted.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\n結果保存: {output_path}")

    # 上位10銘柄を保存（バックテスト用）
    top10 = fcf_valuation_sorted.head(10)
    top10_path = output_dir / "screening_results_fcf_Mid_10stocks_20260331.csv"
    top10.to_csv(top10_path, index=False, encoding='utf-8-sig')

    print(f"上位10銘柄保存: {top10_path}")

    print(f"\n{'='*80}")
    print("完了")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
