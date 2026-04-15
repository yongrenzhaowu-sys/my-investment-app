"""
FCF vs 営業利益のパフォーマンス比較

2026年3月末時点でスクリーニングされた銘柄の過去リターンを比較
"""

import pandas as pd
import numpy as np
from pathlib import Path

# データパス
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "jquants_historical_6years"

PRICES_PATH = DATA_DIR / "daily_bars_2021_2026.parquet"

# スクリーニング結果
FCF_SCREENING = Path(__file__).parent / "screening_results_fcf_Mid_10stocks_20260331.csv"
OP_SCREENING = BASE_DIR / "analyses" / "20260415_1100_op_valuation_all_stocks" / "screening_results_Mid_10stocks_20260331.csv"

def load_prices():
    """株価データ読み込み"""
    prices = pd.read_parquet(PRICES_PATH)
    prices['Date'] = pd.to_datetime(prices['Date'])

    if 'AdjFactor' in prices.columns:
        prices['Price'] = prices['C'] * prices['AdjFactor']
    else:
        prices['Price'] = prices['C']

    return prices

def calculate_portfolio_return(prices, codes, start_date, end_date):
    """ポートフォリオリターン計算"""
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    returns = []

    for code in codes:
        code_prices = prices[prices['Code'] == code].copy()

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

def backtest_portfolio(prices, codes, portfolio_name):
    """ポートフォリオのバックテスト"""
    print(f"\n{'='*80}")
    print(f"【{portfolio_name}】バックテスト")
    print(f"{'='*80}")
    print(f"銘柄数: {len(codes)}")
    print(f"銘柄コード: {codes[:10]}")  # 最初の10銘柄

    # 2022-2025年の年次リターン
    years = [
        ('2022年度', '2022-04-01', '2023-03-31'),
        ('2023年度', '2023-04-01', '2024-03-31'),
        ('2024年度', '2024-04-01', '2025-03-31'),
        ('2025年度', '2025-04-01', '2026-03-31'),
    ]

    yearly_returns = []

    for year_name, start_date, end_date in years:
        ret = calculate_portfolio_return(prices, codes, start_date, end_date)
        yearly_returns.append(ret)

        print(f"{year_name}: {ret:.2%}")

    # パフォーマンス指標
    cumulative_return = (1 + pd.Series(yearly_returns)).prod() - 1
    cagr = (1 + cumulative_return) ** (1 / len(yearly_returns)) - 1
    sharpe = pd.Series(yearly_returns).mean() / pd.Series(yearly_returns).std() if pd.Series(yearly_returns).std() > 0 else 0
    win_rate = (pd.Series(yearly_returns) > 0).mean()

    print(f"\n累積リターン: {cumulative_return:.2%}")
    print(f"年率リターン（CAGR）: {cagr:.2%}")
    print(f"シャープレシオ: {sharpe:.2f}")
    print(f"勝率: {win_rate:.2%}")

    return {
        'Portfolio': portfolio_name,
        'CumulativeReturn': cumulative_return,
        'CAGR': cagr,
        'SharpeRatio': sharpe,
        'WinRate': win_rate,
    }

def main():
    """メイン処理"""
    print("=" * 80)
    print("FCF vs 営業利益のパフォーマンス比較")
    print("=" * 80)

    # 株価データ読み込み
    prices = load_prices()

    # スクリーニング結果読み込み
    fcf_screening = pd.read_csv(FCF_SCREENING)
    op_screening = pd.read_csv(OP_SCREENING)

    fcf_codes = fcf_screening['Code'].astype(str).str.zfill(5).tolist()
    op_codes = op_screening['Code'].astype(str).str.zfill(5).tolist()

    # バックテスト
    fcf_result = backtest_portfolio(prices, fcf_codes, "現金+FCF×10")
    op_result = backtest_portfolio(prices, op_codes, "営業利益×10")

    # 比較
    comparison = pd.DataFrame([fcf_result, op_result])

    print(f"\n{'='*80}")
    print("パフォーマンス比較")
    print(f"{'='*80}")
    print(comparison.to_string(index=False))

    # 結果保存
    output_path = Path(__file__).parent / "comparison_fcf_vs_op.csv"
    comparison.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\n結果保存: {output_path}")

    # 勝者判定
    print(f"\n{'='*80}")
    print("勝者判定")
    print(f"{'='*80}")

    if fcf_result['CAGR'] > op_result['CAGR']:
        print(f"[WINNER] 現金+FCF×10: {fcf_result['CAGR']:.2%} vs 営業利益×10: {op_result['CAGR']:.2%}")
    else:
        print(f"[WINNER] 営業利益×10: {op_result['CAGR']:.2%} vs 現金+FCF×10: {fcf_result['CAGR']:.2%}")

    if fcf_result['SharpeRatio'] > op_result['SharpeRatio']:
        print(f"[BETTER RISK-ADJUSTED] 現金+FCF×10: {fcf_result['SharpeRatio']:.2f} vs 営業利益×10: {op_result['SharpeRatio']:.2f}")
    else:
        print(f"[BETTER RISK-ADJUSTED] 営業利益×10: {op_result['SharpeRatio']:.2f} vs 現金+FCF×10: {fcf_result['SharpeRatio']:.2f}")

    print(f"\n{'='*80}")
    print("完了")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
