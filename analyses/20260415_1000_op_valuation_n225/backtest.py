"""
営業利益バリュエーション戦略のバックテスト

仮説: 営業利益×10と時価総額の乖離が大きい銘柄（割安度が高い銘柄）は、
     その後のリターンが高い

検証期間: 2021-04 ～ 2026-03（5年間、年次リバランス）
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# データパス
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "jquants_historical_6years"

PRICES_PATH = DATA_DIR / "daily_bars_2021_2026.parquet"
FINANCIALS_PATH = DATA_DIR / "financials_2021_2026.parquet"

def load_data():
    """データ読み込み"""
    # 株価データ
    prices = pd.read_parquet(PRICES_PATH)
    prices['Date'] = pd.to_datetime(prices['Date'])

    # 財務データ
    financials = pd.read_parquet(FINANCIALS_PATH)
    financials['DiscDate'] = pd.to_datetime(financials['DiscDate'])
    financials['CurPerEn'] = pd.to_datetime(financials['CurPerEn'])

    return prices, financials

def get_top225_marketcap(prices, base_date):
    """時価総額上位225銘柄を取得"""
    base_date_dt = pd.to_datetime(base_date)
    prices_subset = prices[prices['Date'] <= base_date_dt].copy()

    # 調整済み株価（CRITICAL）
    if 'AdjFactor' in prices_subset.columns:
        prices_subset['Price'] = prices_subset['C'] * prices_subset['AdjFactor']
    else:
        prices_subset['Price'] = prices_subset['C']

    latest_prices = prices_subset.sort_values(['Code', 'Date']).groupby('Code').last().reset_index()
    latest_prices['MarketCap'] = latest_prices['Price'] * latest_prices['Vo'] * 100

    top225 = latest_prices.nlargest(225, 'MarketCap')
    return top225['Code'].tolist()

def calculate_screening_scores(financials, target_codes, reference_date):
    """
    スクリーニングスコア計算

    Returns:
        DataFrame with Code, LatestOP, CAGR, IsGrowthB
    """
    reference_dt = pd.to_datetime(reference_date)

    df = financials[financials['Code'].isin(target_codes)].copy()
    df = df[df['DiscDate'] <= reference_dt]

    # 営業利益を数値に変換
    df['OP'] = pd.to_numeric(df['OP'], errors='coerce')
    df = df[df['OP'].notna() & (df['OP'] != 0)]

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
            # 最新3期で2回連続増益を確認
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

        results.append({
            'Code': code,
            'LatestOP': op_values[-1],
            'CAGR': cagr,
            'IsGrowthB': is_growth_b,
        })

    return pd.DataFrame(results)

def calculate_valuation_scores(op_data, prices, base_date):
    """割安度スコア計算"""
    base_date_dt = pd.to_datetime(base_date)
    prices_subset = prices[prices['Date'] <= base_date_dt].copy()

    # 調整済み株価（CRITICAL）
    if 'AdjFactor' in prices_subset.columns:
        prices_subset['Price'] = prices_subset['C'] * prices_subset['AdjFactor']
    else:
        prices_subset['Price'] = prices_subset['C']

    latest_prices = prices_subset.sort_values(['Code', 'Date']).groupby('Code').last().reset_index()
    latest_prices['MarketCap'] = latest_prices['Price'] * latest_prices['Vo'] * 100

    result = op_data.merge(
        latest_prices[['Code', 'MarketCap', 'Price']],
        on='Code',
        how='left'
    )

    result = result[result['MarketCap'].notna() & (result['MarketCap'] > 0)]

    # 割安度スコア
    result['TheoreticalValue'] = result['LatestOP'] * 10
    result['ValuationGap'] = (result['TheoreticalValue'] - result['MarketCap']) / result['MarketCap']

    return result

def get_portfolio_stocks(financials, prices, rebalance_date, top_n=10):
    """
    リバランス日にポートフォリオ銘柄を選定

    Args:
        rebalance_date: リバランス日（この日までに公開されたデータを使用）
        top_n: 上位何銘柄を選定するか

    Returns:
        選定銘柄のCodeリスト
    """
    # 日経225代替リスト
    nikkei225 = get_top225_marketcap(prices, rebalance_date)

    # スクリーニングスコア計算
    op_scores = calculate_screening_scores(financials, nikkei225, rebalance_date)

    if len(op_scores) == 0:
        return []

    # 割安度計算
    valuation = calculate_valuation_scores(op_scores, prices, rebalance_date)

    # 増益基調B（直近3年連続増益）のみ
    growth_stocks = valuation[valuation['IsGrowthB']].copy()

    if len(growth_stocks) == 0:
        return []

    # 割安度上位N銘柄
    top_stocks = growth_stocks.nlargest(top_n, 'ValuationGap')

    return top_stocks['Code'].tolist()

def calculate_returns(prices, codes, start_date, end_date):
    """
    期間リターン計算

    Args:
        codes: 銘柄コードリスト
        start_date: 開始日（エントリー日）
        end_date: 終了日（エグジット日）

    Returns:
        各銘柄のリターン（DataFrame）
    """
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    # 調整済み株価（CRITICAL）
    prices_adj = prices.copy()
    if 'AdjFactor' in prices_adj.columns:
        prices_adj['Price'] = prices_adj['C'] * prices_adj['AdjFactor']
    else:
        prices_adj['Price'] = prices_adj['C']

    results = []

    for code in codes:
        code_prices = prices_adj[prices_adj['Code'] == code].copy()

        # エントリー価格（start_date以降の最初の営業日の始値）
        entry_data = code_prices[code_prices['Date'] >= start_dt].sort_values('Date')

        if len(entry_data) == 0:
            continue

        entry_price = entry_data.iloc[0]['O'] * entry_data.iloc[0]['AdjFactor'] if 'AdjFactor' in entry_data.columns else entry_data.iloc[0]['O']
        entry_date = entry_data.iloc[0]['Date']

        # エグジット価格（end_date以前の最終営業日の終値）
        exit_data = code_prices[code_prices['Date'] <= end_dt].sort_values('Date')

        if len(exit_data) == 0:
            continue

        exit_price = exit_data.iloc[-1]['Price']
        exit_date = exit_data.iloc[-1]['Date']

        # リターン計算
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

def run_backtest(financials, prices, start_year=2021, end_year=2025, top_n=10):
    """
    バックテスト実行

    Args:
        start_year: 開始年
        end_year: 終了年
        top_n: ポートフォリオ銘柄数

    Returns:
        年次リターン（DataFrame）
    """
    print(f"\n{'='*80}")
    print(f"バックテスト実行（上位{top_n}銘柄、{start_year}-{end_year}）")
    print(f"{'='*80}")

    yearly_results = []

    for year in range(start_year, end_year + 1):
        # リバランス日: 各年3月末（この日までに公開されたデータを使用）
        rebalance_date = f"{year}-03-31"

        # エントリー日: 4月第1営業日
        entry_date = f"{year}-04-01"

        # エグジット日: 翌年3月最終営業日
        exit_date = f"{year + 1}-03-31"

        print(f"\n【{year}年度】")
        print(f"  リバランス基準日: {rebalance_date}")
        print(f"  エントリー目標日: {entry_date}")
        print(f"  エグジット目標日: {exit_date}")

        # ポートフォリオ銘柄選定
        selected_codes = get_portfolio_stocks(financials, prices, rebalance_date, top_n)

        if len(selected_codes) == 0:
            print(f"  選定銘柄なし")
            continue

        print(f"  選定銘柄: {len(selected_codes)}銘柄")

        # リターン計算
        returns_df = calculate_returns(prices, selected_codes, entry_date, exit_date)

        if len(returns_df) == 0:
            print(f"  リターン計算失敗")
            continue

        # ポートフォリオリターン（等金額加重平均）
        portfolio_return = returns_df['Return'].mean()

        print(f"  ポートフォリオリターン: {portfolio_return:.2%}")
        print(f"  個別銘柄リターン範囲: {returns_df['Return'].min():.2%} ～ {returns_df['Return'].max():.2%}")

        yearly_results.append({
            'Year': year,
            'NumStocks': len(returns_df),
            'PortfolioReturn': portfolio_return,
            'MinReturn': returns_df['Return'].min(),
            'MaxReturn': returns_df['Return'].max(),
            'StdReturn': returns_df['Return'].std(),
        })

        # 詳細保存
        output_dir = Path(__file__).parent
        returns_df.to_csv(output_dir / f"backtest_details_{year}_{top_n}stocks.csv", index=False, encoding='utf-8-sig')

    return pd.DataFrame(yearly_results)

def calculate_performance_metrics(yearly_results):
    """パフォーマンス指標計算"""
    if len(yearly_results) == 0:
        return {}

    # 累積リターン
    cumulative_return = (1 + yearly_results['PortfolioReturn']).prod() - 1

    # 年率リターン（CAGR）
    years = len(yearly_results)
    cagr = (1 + cumulative_return) ** (1 / years) - 1

    # シャープレシオ（リスクフリーレート0%と仮定）
    sharpe = yearly_results['PortfolioReturn'].mean() / yearly_results['PortfolioReturn'].std() if yearly_results['PortfolioReturn'].std() > 0 else 0

    # 最大ドローダウン
    cumulative_rets = (1 + yearly_results['PortfolioReturn']).cumprod()
    running_max = cumulative_rets.cummax()
    drawdown = (cumulative_rets - running_max) / running_max
    max_drawdown = drawdown.min()

    # 勝率
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
    print("営業利益バリュエーション戦略のバックテスト")
    print("=" * 80)

    # データ読み込み
    prices, financials = load_data()

    # バックテスト実行（複数のポートフォリオサイズで比較）
    all_results = []

    for top_n in [5, 10, 20]:
        yearly_results = run_backtest(financials, prices, start_year=2021, end_year=2025, top_n=top_n)

        if len(yearly_results) == 0:
            continue

        # パフォーマンス指標
        metrics = calculate_performance_metrics(yearly_results)

        print(f"\n{'='*80}")
        print(f"【パフォーマンスサマリー: 上位{top_n}銘柄】")
        print(f"{'='*80}")
        print(f"  累積リターン: {metrics['CumulativeReturn']:.2%}")
        print(f"  年率リターン（CAGR）: {metrics['CAGR']:.2%}")
        print(f"  シャープレシオ: {metrics['SharpeRatio']:.2f}")
        print(f"  最大ドローダウン: {metrics['MaxDrawdown']:.2%}")
        print(f"  勝率: {metrics['WinRate']:.2%}")

        # 結果保存
        output_dir = Path(__file__).parent

        yearly_results.to_csv(
            output_dir / f"backtest_yearly_{top_n}stocks.csv",
            index=False,
            encoding='utf-8-sig'
        )

        all_results.append({
            'PortfolioSize': top_n,
            **metrics
        })

    # 全結果の比較
    comparison_df = pd.DataFrame(all_results)
    output_dir = Path(__file__).parent
    comparison_df.to_csv(output_dir / "backtest_comparison.csv", index=False, encoding='utf-8-sig')

    print(f"\n{'='*80}")
    print("ポートフォリオサイズ比較")
    print(f"{'='*80}")
    print(comparison_df.to_string(index=False))

    print(f"\n{'='*80}")
    print("完了")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
