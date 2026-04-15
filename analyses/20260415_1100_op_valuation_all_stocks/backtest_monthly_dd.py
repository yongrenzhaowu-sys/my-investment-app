"""
月次ドローダウン計算

月次リバランスでバックテストを実行し、より正確なドローダウンを計測
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

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

        equity_ratio = recent['EquityRatio'].iloc[-1] if len(recent) > 0 else 0

        results.append({
            'Code': code,
            'LatestOP': op_values[-1],
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

def get_portfolio_stocks(financials, prices, rebalance_date, cap_group='Mid', top_n=10, min_equity_ratio=0.20):
    """ポートフォリオ銘柄選定"""
    market_cap_data = classify_by_market_cap(prices, rebalance_date, min_market_cap=10e9)
    group_codes = market_cap_data[market_cap_data['CapGroup'] == cap_group]['Code'].tolist()

    if len(group_codes) == 0:
        return []

    consolidation_stocks = detect_stock_consolidation(prices, group_codes)
    group_codes = [c for c in group_codes if c not in consolidation_stocks]

    op_scores = calculate_screening_scores(financials, group_codes, rebalance_date)

    if len(op_scores) == 0:
        return []

    valuation = calculate_valuation_scores(op_scores, market_cap_data)

    growth_stocks = valuation[
        (valuation['IsGrowthB']) &
        (valuation['EquityRatio'] >= min_equity_ratio)
    ].copy()

    if len(growth_stocks) == 0:
        return []

    top_stocks = growth_stocks.nlargest(top_n, 'ValuationGap')

    return top_stocks['Code'].tolist()

def calculate_monthly_return(prices, codes, start_date, end_date):
    """月次リターン計算"""
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    prices_adj = prices.copy()
    if 'AdjFactor' in prices_adj.columns:
        prices_adj['Price'] = prices_adj['C'] * prices_adj['AdjFactor']
    else:
        prices_adj['Price'] = prices_adj['C']

    returns = []

    for code in codes:
        code_prices = prices_adj[prices_adj['Code'] == code].copy()

        # エントリー
        entry_data = code_prices[code_prices['Date'] >= start_dt].sort_values('Date')
        if len(entry_data) == 0:
            continue

        entry_price = entry_data.iloc[0]['O'] * entry_data.iloc[0]['AdjFactor'] if 'AdjFactor' in entry_data.columns else entry_data.iloc[0]['O']

        # エグジット
        exit_data = code_prices[code_prices['Date'] <= end_dt].sort_values('Date')
        if len(exit_data) == 0:
            continue

        exit_price = exit_data.iloc[-1]['Price']

        # リターン
        if entry_price > 0:
            ret = (exit_price - entry_price) / entry_price
        else:
            ret = 0

        returns.append(ret)

    if len(returns) == 0:
        return 0.0

    return np.mean(returns)

def run_monthly_backtest(financials, prices, cap_group='Mid', start_date='2024-01-01', end_date='2025-12-31', top_n=10):
    """月次バックテスト実行"""
    print(f"\n{'='*80}")
    print(f"月次バックテスト実行（{cap_group}型株、上位{top_n}銘柄）")
    print(f"期間: {start_date} ～ {end_date}")
    print(f"{'='*80}")

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    monthly_results = []
    current_date = start_dt

    while current_date <= end_dt:
        # 月末の前日をリバランス日とする
        month_end = current_date + relativedelta(months=1) - timedelta(days=1)

        # 翌月の最初の営業日をエントリー日とする
        entry_date = current_date + relativedelta(months=1)

        # 翌々月の最終営業日をエグジット日とする
        exit_date = entry_date + relativedelta(months=1) - timedelta(days=1)

        if exit_date > end_dt:
            break

        print(f"\n【{current_date.strftime('%Y年%m月')}】")
        print(f"  リバランス基準日: {month_end.strftime('%Y-%m-%d')}")
        print(f"  エントリー目標日: {entry_date.strftime('%Y-%m-%d')}")
        print(f"  エグジット目標日: {exit_date.strftime('%Y-%m-%d')}")

        # ポートフォリオ選定
        selected_codes = get_portfolio_stocks(
            financials,
            prices,
            month_end.strftime('%Y-%m-%d'),
            cap_group,
            top_n
        )

        if len(selected_codes) == 0:
            print(f"  選定銘柄なし")
            monthly_return = 0.0
        else:
            print(f"  選定銘柄: {len(selected_codes)}銘柄")

            # 月次リターン計算
            monthly_return = calculate_monthly_return(
                prices,
                selected_codes,
                entry_date.strftime('%Y-%m-%d'),
                exit_date.strftime('%Y-%m-%d')
            )

            print(f"  月次リターン: {monthly_return:.2%}")

        monthly_results.append({
            'Month': current_date.strftime('%Y-%m'),
            'NumStocks': len(selected_codes),
            'MonthlyReturn': monthly_return,
        })

        current_date = current_date + relativedelta(months=1)

    return pd.DataFrame(monthly_results)

def calculate_monthly_drawdown(monthly_results):
    """月次ドローダウン計算"""
    if len(monthly_results) == 0:
        return {}

    # 累積リターン
    cumulative_rets = (1 + monthly_results['MonthlyReturn']).cumprod()

    # ランニング最大値
    running_max = cumulative_rets.cummax()

    # ドローダウン
    drawdown = (cumulative_rets - running_max) / running_max

    # 最大ドローダウン
    max_drawdown = drawdown.min()

    # 累積リターン
    cumulative_return = cumulative_rets.iloc[-1] - 1

    # 月次平均リターン
    avg_monthly_return = monthly_results['MonthlyReturn'].mean()

    # 月次標準偏差
    std_monthly_return = monthly_results['MonthlyReturn'].std()

    # シャープレシオ（月次）
    sharpe_monthly = avg_monthly_return / std_monthly_return if std_monthly_return > 0 else 0

    # 年率換算
    cagr = (1 + cumulative_return) ** (12 / len(monthly_results)) - 1
    sharpe_annual = sharpe_monthly * np.sqrt(12)

    # 勝率
    win_rate = (monthly_results['MonthlyReturn'] > 0).mean()

    return {
        'CumulativeReturn': cumulative_return,
        'CAGR': cagr,
        'AvgMonthlyReturn': avg_monthly_return,
        'StdMonthlyReturn': std_monthly_return,
        'SharpeRatioMonthly': sharpe_monthly,
        'SharpeRatioAnnual': sharpe_annual,
        'MaxDrawdown': max_drawdown,
        'WinRate': win_rate,
        'NumMonths': len(monthly_results),
        'CumulativeReturns': cumulative_rets,
        'Drawdowns': drawdown,
    }

def main():
    """メイン処理"""
    print("=" * 80)
    print("月次ドローダウン計算")
    print("=" * 80)

    # データ読み込み
    prices, financials = load_data()

    # 月次バックテスト実行（中型株、2024-2025年、2年間）
    monthly_results = run_monthly_backtest(
        financials,
        prices,
        cap_group='Mid',
        start_date='2024-01-01',
        end_date='2025-12-31',
        top_n=10
    )

    if len(monthly_results) == 0:
        print("ERROR: 月次リターンを計算できませんでした")
        return

    # ドローダウン計算
    metrics = calculate_monthly_drawdown(monthly_results)

    print(f"\n{'='*80}")
    print("【月次パフォーマンスサマリー】")
    print(f"{'='*80}")
    print(f"  累積リターン: {metrics['CumulativeReturn']:.2%}")
    print(f"  年率リターン（CAGR）: {metrics['CAGR']:.2%}")
    print(f"  平均月次リターン: {metrics['AvgMonthlyReturn']:.2%}")
    print(f"  月次標準偏差: {metrics['StdMonthlyReturn']:.2%}")
    print(f"  シャープレシオ（月次）: {metrics['SharpeRatioMonthly']:.2f}")
    print(f"  シャープレシオ（年率）: {metrics['SharpeRatioAnnual']:.2f}")
    print(f"  🔴 最大ドローダウン: {metrics['MaxDrawdown']:.2%}")
    print(f"  勝率: {metrics['WinRate']:.2%}")
    print(f"  計測期間: {metrics['NumMonths']}ヶ月")

    # 結果保存
    output_dir = Path(__file__).parent

    # 月次リターン
    monthly_results.to_csv(
        output_dir / "backtest_monthly_returns.csv",
        index=False,
        encoding='utf-8-sig'
    )

    # 累積リターンとドローダウン
    dd_df = pd.DataFrame({
        'Month': monthly_results['Month'],
        'MonthlyReturn': monthly_results['MonthlyReturn'],
        'CumulativeReturn': metrics['CumulativeReturns'],
        'Drawdown': metrics['Drawdowns'],
    })

    dd_df.to_csv(
        output_dir / "backtest_monthly_drawdown.csv",
        index=False,
        encoding='utf-8-sig'
    )

    print(f"\n結果保存:")
    print(f"  - backtest_monthly_returns.csv")
    print(f"  - backtest_monthly_drawdown.csv")

    # ドローダウンの詳細
    print(f"\n{'='*80}")
    print("【ドローダウン詳細】")
    print(f"{'='*80}")

    # 最大DDが発生した月
    max_dd_idx = metrics['Drawdowns'].idxmin()
    max_dd_month = monthly_results.iloc[max_dd_idx]['Month']

    print(f"\n最大ドローダウン発生:")
    print(f"  月: {max_dd_month}")
    print(f"  ドローダウン: {metrics['MaxDrawdown']:.2%}")

    # 月次ドローダウン推移（上位5ヶ月）
    dd_sorted = dd_df.sort_values('Drawdown').head(5)
    print(f"\nドローダウン最大5ヶ月:")
    print(dd_sorted[['Month', 'MonthlyReturn', 'Drawdown']].to_string(index=False))

    print(f"\n{'='*80}")
    print("完了")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
