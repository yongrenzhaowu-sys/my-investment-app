"""
営業利益バリュエーション検証（上場全銘柄×時価総額別）

スクリーニング: 全銘柄を時価総額で分類し、各グループで割安度上位銘柄を選定
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
    prices['Date'] = pd.to_datetime(prices['Date'])

    print(f"株価データ: {len(prices):,}レコード")
    print(f"  期間: {prices['Date'].min()} ～ {prices['Date'].max()}")
    print(f"  銘柄数: {prices['Code'].nunique()}")

    # 財務データ
    financials = pd.read_parquet(FINANCIALS_PATH)
    financials['DiscDate'] = pd.to_datetime(financials['DiscDate'])
    financials['CurPerEn'] = pd.to_datetime(financials['CurPerEn'])

    print(f"\n財務データ: {len(financials):,}レコード")
    print(f"  期間: {financials['DiscDate'].min()} ～ {financials['DiscDate'].max()}")
    print(f"  銘柄数: {financials['Code'].nunique()}")

    return prices, financials

def classify_by_market_cap(prices, base_date='2026-03-31', min_market_cap=10_000_000_000):
    """
    時価総額で銘柄を分類

    Args:
        base_date: 基準日
        min_market_cap: 最低時価総額（デフォルト100億円）

    Returns:
        DataFrame with Code, MarketCap, CapGroup
    """
    print(f"\n時価総額分類（{base_date}時点）...")

    base_date_dt = pd.to_datetime(base_date)
    prices_subset = prices[prices['Date'] <= base_date_dt].copy()

    # 調整済み株価（CRITICAL）
    if 'AdjFactor' in prices_subset.columns:
        prices_subset['Price'] = prices_subset['C'] * prices_subset['AdjFactor']
    else:
        prices_subset['Price'] = prices_subset['C']

    # 各銘柄の最新株価
    latest_prices = prices_subset.sort_values(['Code', 'Date']).groupby('Code').last().reset_index()

    # 時価総額計算（価格 × 出来高 × 100をプロキシとして使用）
    latest_prices['MarketCap'] = latest_prices['Price'] * latest_prices['Vo'] * 100

    # 最低時価総額フィルタ
    latest_prices = latest_prices[latest_prices['MarketCap'] >= min_market_cap]

    # 時価総額で分類
    large_cap_threshold = latest_prices['MarketCap'].quantile(0.70)
    small_cap_threshold = latest_prices['MarketCap'].quantile(0.30)

    latest_prices['CapGroup'] = 'Mid'
    latest_prices.loc[latest_prices['MarketCap'] >= large_cap_threshold, 'CapGroup'] = 'Large'
    latest_prices.loc[latest_prices['MarketCap'] <= small_cap_threshold, 'CapGroup'] = 'Small'

    print(f"  最低時価総額: {min_market_cap:,.0f}円（{min_market_cap / 1e9:.0f}億円）")
    print(f"  分類後銘柄数: {len(latest_prices)}")
    print(f"    大型株（上位30%）: {(latest_prices['CapGroup'] == 'Large').sum()}銘柄")
    print(f"    中型株（30-70%）: {(latest_prices['CapGroup'] == 'Mid').sum()}銘柄")
    print(f"    小型株（下位30%）: {(latest_prices['CapGroup'] == 'Small').sum()}銘柄")

    print(f"\n  時価総額範囲:")
    for cap_group in ['Large', 'Mid', 'Small']:
        group_data = latest_prices[latest_prices['CapGroup'] == cap_group]
        print(f"    {cap_group}: {group_data['MarketCap'].min() / 1e9:,.1f}億円 ～ {group_data['MarketCap'].max() / 1e9:,.1f}億円")

    return latest_prices[['Code', 'MarketCap', 'CapGroup']]

def detect_stock_consolidation(prices, target_codes):
    """
    株式併合を検出（リスク管理）

    Args:
        prices: 株価データ
        target_codes: 対象銘柄コードリスト

    Returns:
        株式併合が実施された銘柄のCodeリスト
    """
    print("\n株式併合検出...")

    if 'AdjFactor' not in prices.columns:
        print("  AdjFactor列なし、スキップ")
        return []

    # 対象銘柄のみ
    prices_subset = prices[prices['Code'].isin(target_codes)].copy()

    # AdjFactorの急激な変化を検出（0.5以上の変化）
    consolidation_stocks = []

    for code in target_codes:
        code_data = prices_subset[prices_subset['Code'] == code].copy()

        if len(code_data) == 0:
            continue

        # AdjFactorの差分
        code_data = code_data.sort_values('Date')
        adjfactor_diff = code_data['AdjFactor'].diff().abs()

        # 0.5以上の変化があれば株式併合とみなす
        if (adjfactor_diff > 0.5).any():
            consolidation_stocks.append(code)

    print(f"  株式併合検出: {len(consolidation_stocks)}銘柄")

    return consolidation_stocks

def calculate_screening_scores(financials, target_codes, reference_date='2026-03-31'):
    """
    スクリーニングスコア計算

    Returns:
        DataFrame with Code, LatestOP, CAGR, IsGrowthB, EquityRatio
    """
    reference_dt = pd.to_datetime(reference_date)

    df = financials[financials['Code'].isin(target_codes)].copy()
    df = df[df['DiscDate'] <= reference_dt]

    # 営業利益を数値に変換
    df['OP'] = pd.to_numeric(df['OP'], errors='coerce')
    df = df[df['OP'].notna() & (df['OP'] > 0)]  # 営業利益 > 0

    # 自己資本比率計算（リスク管理）
    df['TA'] = pd.to_numeric(df['TA'], errors='coerce')
    df['Eq'] = pd.to_numeric(df['Eq'], errors='coerce')
    df['EquityRatio'] = df['Eq'] / df['TA']

    # 決算期でソート
    df = df.sort_values(['Code', 'CurPerEn'])

    results = []

    for code in target_codes:
        code_data = df[df['Code'] == code].copy()

        if len(code_data) < 3:  # 最低3期必要
            continue

        # 最新5期
        recent = code_data.tail(5)
        op_values = recent['OP'].values

        # 増益基調B: 直近3年連続増益
        is_growth_b = False
        if len(op_values) >= 3:
            is_growth_b = (op_values[-1] > op_values[-2]) and (op_values[-2] > op_values[-3])

        # CAGR計算
        if len(op_values) >= 2 and op_values[0] > 0:
            years = len(op_values) - 1
            try:
                cagr = (op_values[-1] / op_values[0]) ** (1 / years) - 1
            except:
                cagr = 0
        else:
            cagr = 0

        # 自己資本比率（最新）
        equity_ratio = recent['EquityRatio'].iloc[-1] if len(recent) > 0 else 0

        results.append({
            'Code': code,
            'LatestOP': op_values[-1],
            'CAGR': cagr,
            'IsGrowthB': is_growth_b,
            'EquityRatio': equity_ratio,
        })

    return pd.DataFrame(results)

def calculate_valuation_scores(op_data, market_cap_data):
    """
    割安度スコア計算

    Args:
        op_data: 営業利益データ
        market_cap_data: 時価総額データ

    Returns:
        割安度データ
    """
    # 時価総額データとマージ
    result = op_data.merge(
        market_cap_data[['Code', 'MarketCap', 'CapGroup']],
        on='Code',
        how='left'
    )

    result = result[result['MarketCap'].notna() & (result['MarketCap'] > 0)]

    # 割安度スコア
    result['TheoreticalValue'] = result['LatestOP'] * 10
    result['ValuationGap'] = (result['TheoreticalValue'] - result['MarketCap']) / result['MarketCap']

    return result

def screen_by_group(valuation_data, cap_group, top_n=10, min_equity_ratio=0.20):
    """
    時価総額グループ別にスクリーニング

    Args:
        cap_group: 'Large', 'Mid', 'Small'
        top_n: 上位何銘柄を選定するか
        min_equity_ratio: 最低自己資本比率

    Returns:
        選定銘柄
    """
    # グループフィルタ
    group_data = valuation_data[valuation_data['CapGroup'] == cap_group].copy()

    # 増益基調B
    growth_stocks = group_data[group_data['IsGrowthB']].copy()

    # 自己資本比率フィルタ（リスク管理）
    growth_stocks = growth_stocks[growth_stocks['EquityRatio'] >= min_equity_ratio]

    if len(growth_stocks) == 0:
        return pd.DataFrame()

    # 割安度上位N銘柄
    top_stocks = growth_stocks.nlargest(top_n, 'ValuationGap')

    return top_stocks

def main():
    """メイン処理"""
    print("=" * 80)
    print("営業利益バリュエーション検証（上場全銘柄×時価総額別）")
    print("=" * 80)

    # データ読み込み
    prices, financials = load_data()

    # 時価総額分類
    market_cap_data = classify_by_market_cap(prices, base_date='2026-03-31', min_market_cap=10e9)

    # 株式併合検出
    all_codes = market_cap_data['Code'].tolist()
    consolidation_stocks = detect_stock_consolidation(prices, all_codes)

    # 株式併合銘柄を除外
    market_cap_data = market_cap_data[~market_cap_data['Code'].isin(consolidation_stocks)]
    print(f"\n株式併合除外後: {len(market_cap_data)}銘柄")

    # スクリーニングスコア計算
    print(f"\n営業利益成長計算（2026-03-31基準）...")
    op_scores = calculate_screening_scores(
        financials,
        market_cap_data['Code'].tolist(),
        reference_date='2026-03-31'
    )

    print(f"  営業利益データ取得: {len(op_scores)}銘柄")
    print(f"  増益基調B（直近3年連続増益）: {op_scores['IsGrowthB'].sum()}銘柄")

    # 割安度計算
    print(f"\n割安度計算...")
    valuation = calculate_valuation_scores(op_scores, market_cap_data)

    print(f"  割安度計算完了: {len(valuation)}銘柄")

    # グループ別スクリーニング
    output_dir = Path(__file__).parent

    for cap_group in ['Large', 'Mid', 'Small']:
        print(f"\n{'='*80}")
        print(f"【{cap_group}型株】スクリーニング")
        print(f"{'='*80}")

        for top_n in [5, 10, 20]:
            selected = screen_by_group(valuation, cap_group, top_n=top_n, min_equity_ratio=0.20)

            print(f"\n上位{top_n}銘柄: {len(selected)}銘柄選定")

            if len(selected) > 0:
                # 結果保存
                output_path = output_dir / f"screening_results_{cap_group}_{top_n}stocks_20260331.csv"
                selected.to_csv(output_path, index=False, encoding='utf-8-sig')

                print(f"  保存: {output_path.name}")

                # サマリー表示
                if top_n == 10:  # 10銘柄の場合のみ詳細表示
                    print("\n  割安度上位10銘柄:")
                    print(selected[
                        ['Code', 'LatestOP', 'MarketCap', 'ValuationGap', 'EquityRatio', 'CAGR']
                    ].to_string(index=False))

    print(f"\n{'='*80}")
    print("完了")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
