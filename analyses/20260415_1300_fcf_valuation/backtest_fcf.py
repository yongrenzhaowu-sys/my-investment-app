"""
営業利益バリュエーション戦略のバックテスト（時価総額別）

期間: 2022-2025年（4年間、年次リバランス）
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

    # 調整済み株価
    if 'AdjFactor' in prices_subset.columns:
        prices_subset['Price'] = prices_subset['C'] * prices_subset['AdjFactor']
    else:
        prices_subset['Price'] = prices_subset['C']

    latest_prices = prices_subset.sort_values(['Code', 'Date']).groupby('Code').last().reset_index()
    latest_prices['MarketCap'] = latest_prices['Price'] * latest_prices['Vo'] * 100
    latest_prices = latest_prices[latest_prices['MarketCap'] >= min_market_cap]

    # 分類
    large_cap_threshold = latest_prices['MarketCap'].quantile(0.70)
    small_cap_threshold = latest_prices['MarketCap'].quantile(0.30)

    latest_prices['CapGroup'] = 'Mid'
    latest_prices.loc[latest_prices['MarketCap'] >= large_cap_threshold, 'CapGroup'] = 'Large'
    latest_prices.loc[latest_prices['MarketCap'] <= small_cap_threshold, 'CapGroup'] = 'Small'

    return latest_prices[['Code', 'MarketCap', 'CapGroup']]

def detect_stock_consolidation(prices, target_codes):
    """株式併合検出"""
    if 'AdjFactor' not in prices.columns:
        return []

    prices_subset = prices[prices['Code'].isin(target_codes)].copy()
    consolidation_stocks = []

    for code in target_codes:
        code_data = prices_subset[prices_subset['Code'] == code].copy()
        if len(code_data) == 0:
            continue

        code_data = code_data.sort_values('Date')
        adjfactor_diff = code_data['AdjFactor'].diff().abs()

        if (adjfactor_diff > 0.5).any():
            consolidation_stocks.append(code)

    return consolidation_stocks

def calculate_screening_scores(financials, target_codes, reference_date):
    """スクリーニングスコア計算"""
    reference_dt = pd.to_datetime(reference_date)

    df = financials[financials['Code'].isin(target_codes)].copy()
    df = df[df['DiscDate'] <= reference_dt]

    df['OP'] = pd.to_numeric(df['OP'], errors='coerce')
    df = df[df['OP'].notna() & (df['OP'] > 0)]

    df['TA'] = pd.to_numeric(df['TA'], errors='coerce')
    df['Eq'] = pd.to_numeric(df['Eq'], errors='coerce')
    df['EquityRatio'] = df['Eq'] / df['TA']

    df = df.sort_values(['Code', 'CurPerEn'])

    results = []

    for code in target_codes:
        code_data = df[df['Code'] == code].copy()

        if len(code_data) < 3:
            continue

        recent = code_data.tail(5)
        op_values = recent['OP'].values

        is_growth_b = False
        if len(op_values) >= 3:
            is_growth_b = (op_values[-1] > op_values[-2]) and (op_values[-2] > op_values[-3])

        if len(op_values) >= 2 and op_values[0] > 0:
            years = len(op_values) - 1
            try:
                cagr = (op_values[-1] / op_values[0]) ** (1 / years) - 1
            except:
                cagr = 0
        else:
            cagr = 0

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
    """割安度スコア計算"""
    result = op_data.merge(
        market_cap_data[['Code', 'MarketCap', 'CapGroup']],
        on='Code',
        how='left'
    )

    result = result[result['MarketCap'].notna() & (result['MarketCap'] > 0)]
    result['TheoreticalValue'] = result['LatestOP'] * 10
    result['ValuationGap'] = (result['TheoreticalValue'] - result['MarketCap']) / result['MarketCap']

    return result

def get_portfolio_stocks(financials, prices, rebalance_date, cap_group, top_n=10, min_equity_ratio=0.20):
    """ポートフォリオ銘柄選定"""
    # 時価総額分類
    market_cap_data = classify_by_market_cap(prices, rebalance_date, min_market_cap=10e9)

    # グループフィルタ
    group_codes = market_cap_data[market_cap_data['CapGroup'] == cap_group]['Code'].tolist()

    if len(group_codes) == 0:
        return []

    # 株式併合除外
    consolidation_stocks = detect_stock_consolidation(prices, group_codes)
    group_codes = [c for c in group_codes if c not in consolidation_stocks]

    # スクリーニング
    op_scores = calculate_screening_scores(financials, group_codes, rebalance_date)

    if len(op_scores) == 0:
        return []

    # 割安度計算
    valuation = calculate_valuation_scores(op_scores, market_cap_data)

    # 増益基調B + 自己資本比率
    growth_stocks = valuation[
        (valuation['IsGrowthB']) &
        (valuation['EquityRatio'] >= min_equity_ratio)
    ].copy()

    if len(growth_stocks) == 0:
        return []

    # 割安度上位N銘柄
    top_stocks = growth_stocks.nlargest(top_n, 'ValuationGap')

    return top_stocks['Code'].tolist()

def calculate_returns(prices, codes, start_date, end_date):
    """期間リターン計算"""
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    prices_adj = prices.copy()
    if 'AdjFactor' in prices_adj.columns:
        prices_adj['Price'] = prices_adj['C'] * prices_adj['AdjFactor']
    else:
        prices_adj['Price'] = prices_adj['C']

    results = []

    for code in codes:
        code_prices = prices_adj[prices_adj['Code'] == code].copy()

        # エントリー
        entry_data = code_prices[code_prices['Date'] >= start_dt].sort_values('Date')
        if len(entry_data) == 0:
            continue

        entry_price = entry_data.iloc[0]['O'] * entry_data.iloc[0]['AdjFactor'] if 'AdjFactor' in entry_data.columns else entry_data.iloc[0]['O']
        entry_date = entry_data.iloc[0]['Date']

        # エグジット
        exit_data = code_prices[code_prices['Date'] <= end_dt].sort_values('Date')
        if len(exit_data) == 0:
            continue

        exit_price = exit_data.iloc[-1]['Price']
        exit_date = exit_data.iloc[-1]['Date']

        # リターン
        if entry_price > 0:
            ret = (exit_price - entry_price) / entry_price
        else:
            ret = 0

        results.append({
            'Code': code,
            'EntryDate': entry_date,
            'EntryPrice': entry_price,
            'ExitDate': exit_date,
            'ExitPrice': exit_price,
            'Return': ret,
        })

    return pd.DataFrame(results)

def run_backtest(financials, prices, cap_group, start_year=2021, end_year=2025, top_n=10):
    """バックテスト実行"""
    print(f"\n{'='*80}")
    print(f"バックテスト実行（{cap_group}型株、上位{top_n}銘柄、{start_year}-{end_year}）")
    print(f"{'='*80}")

    yearly_results = []

    for year in range(start_year, end_year + 1):
        rebalance_date = f"{year}-03-31"
        entry_date = f"{year}-04-01"
        exit_date = f"{year + 1}-03-31"

        print(f"\n【{year}年度】")

        # ポートフォリオ選定
        selected_codes = get_portfolio_stocks(financials, prices, rebalance_date, cap_group, top_n)

        if len(selected_codes) == 0:
            print(f"  選定銘柄なし")
            continue

        print(f"  選定銘柄: {len(selected_codes)}銘柄")

        # リターン計算
        returns_df = calculate_returns(prices, selected_codes, entry_date, exit_date)

        if len(returns_df) == 0:
            print(f"  リターン計算失敗")
            continue

        # ポートフォリオリターン
        portfolio_return = returns_df['Return'].mean()

        print(f"  ポートフォリオリターン: {portfolio_return:.2%}")
        print(f"  個別銘柄リターン範囲: {returns_df['Return'].min():.2%} ～ {returns_df['Return'].max():.2%}")

        yearly_results.append({
            'Year': year,
            'CapGroup': cap_group,
            'NumStocks': len(returns_df),
            'PortfolioReturn': portfolio_return,
            'MinReturn': returns_df['Return'].min(),
            'MaxReturn': returns_df['Return'].max(),
            'StdReturn': returns_df['Return'].std(),
        })

        # 詳細保存
        output_dir = Path(__file__).parent
        returns_df.to_csv(
            output_dir / f"backtest_details_{cap_group}_{year}_{top_n}stocks.csv",
            index=False,
            encoding='utf-8-sig'
        )

    return pd.DataFrame(yearly_results)

def calculate_performance_metrics(yearly_results):
    """パフォーマンス指標計算"""
    if len(yearly_results) == 0:
        return {}

    cumulative_return = (1 + yearly_results['PortfolioReturn']).prod() - 1
    years = len(yearly_results)
    cagr = (1 + cumulative_return) ** (1 / years) - 1

    sharpe = yearly_results['PortfolioReturn'].mean() / yearly_results['PortfolioReturn'].std() if yearly_results['PortfolioReturn'].std() > 0 else 0

    cumulative_rets = (1 + yearly_results['PortfolioReturn']).cumprod()
    running_max = cumulative_rets.cummax()
    drawdown = (cumulative_rets - running_max) / running_max
    max_drawdown = drawdown.min()

    win_rate = (yearly_results['PortfolioReturn'] > 0).mean()

    return {
        'CumulativeReturn': cumulative_return,
        'CAGR': cagr,
        'SharpeRatio': sharpe,
        'MaxDrawdown': max_drawdown,
        'WinRate': win_rate,
        'NumYears': years,
    }

def main():
    """メイン処理"""
    print("=" * 80)
    print("営業利益バリュエーション戦略のバックテスト（時価総額別）")
    print("=" * 80)

    # データ読み込み
    prices, financials = load_data()

    # バックテスト実行（各時価総額グループ × 各ポートフォリオサイズ）
    all_results = []

    # 軽量化: 上位10銘柄のみ、Large/Midのみ
    for cap_group in ['Large', 'Mid', 'Small']:
        for top_n in [10]:
            yearly_results = run_backtest(
                financials,
                prices,
                cap_group=cap_group,
                start_year=2023,
                end_year=2025,
                top_n=top_n
            )

            if len(yearly_results) == 0:
                continue

            # パフォーマンス指標
            metrics = calculate_performance_metrics(yearly_results)

            print(f"\n{'='*80}")
            print(f"【パフォーマンスサマリー: {cap_group}型株、上位{top_n}銘柄】")
            print(f"{'='*80}")
            print(f"  累積リターン: {metrics['CumulativeReturn']:.2%}")
            print(f"  年率リターン（CAGR）: {metrics['CAGR']:.2%}")
            print(f"  シャープレシオ: {metrics['SharpeRatio']:.2f}")
            print(f"  最大ドローダウン: {metrics['MaxDrawdown']:.2%}")
            print(f"  勝率: {metrics['WinRate']:.2%}")

            # 結果保存
            output_dir = Path(__file__).parent

            yearly_results.to_csv(
                output_dir / f"backtest_yearly_{cap_group}_{top_n}stocks.csv",
                index=False,
                encoding='utf-8-sig'
            )

            all_results.append({
                'CapGroup': cap_group,
                'PortfolioSize': top_n,
                **metrics
            })

    # 全結果の比較
    comparison_df = pd.DataFrame(all_results)
    output_dir = Path(__file__).parent
    comparison_df.to_csv(output_dir / "backtest_comparison_by_marketcap.csv", index=False, encoding='utf-8-sig')

    print(f"\n{'='*80}")
    print("時価総額別×ポートフォリオサイズ比較")
    print(f"{'='*80}")
    print(comparison_df.to_string(index=False))

    print(f"\n{'='*80}")
    print("完了")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
