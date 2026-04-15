"""
SMBC「割安高質」戦略（低PBR × 高ROE）
J-Quantsデータ版（2021-03～2026-03）
"""
import pandas as pd
import numpy as np
import warnings
import os
import logging
from datetime import datetime
from pathlib import Path

warnings.filterwarnings('ignore')

# ===================================
# ロギング設定
# ===================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest_smbc_jquants.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===================================
# グローバル変数
# ===================================
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data/processed/jquants_historical_6years"

# 税金パラメータ
TAX_RATE = 0.20315  # 譲渡益税 20.315%

# 単位株制限
UNIT_SHARES = 100  # 100株単位

# ===================================
# データ読み込み
# ===================================

def load_jquants_data():
    """J-Quantsデータ読み込み"""

    logger.info("J-Quantsデータ読み込み中...")

    # 株価データ
    prices_path = DATA_DIR / "daily_bars_2021_2026.parquet"
    df_prices = pd.read_parquet(prices_path)
    logger.info(f"株価データ読み込み成功: {len(df_prices):,}件")

    # 財務データ
    fins_path = DATA_DIR / "financials_2021_2026.parquet"
    df_fins = pd.read_parquet(fins_path)
    logger.info(f"財務データ読み込み成功: {len(df_fins):,}件")

    # 日付型に変換
    df_prices['Date'] = pd.to_datetime(df_prices['Date'])
    df_fins['DiscDate'] = pd.to_datetime(df_fins['DiscDate'])

    # Codeを4桁に統一
    df_prices['Code'] = df_prices['Code'].astype(str).str[:4]
    df_fins['Code'] = df_fins['Code'].astype(str).str[:4]

    # 調整済み株価を計算
    df_prices['AdjC_Correct'] = df_prices['C'] * df_prices['AdjFactor']
    df_prices['Price'] = df_prices['AdjC_Correct']

    # 重複除外（同じCode×Dateで最も取引量が多いレコードを採用）
    df_prices = df_prices.sort_values(['Code', 'Date', 'Vo'], ascending=[True, True, False])
    df_prices = df_prices.drop_duplicates(subset=['Code', 'Date'], keep='first')

    logger.info(f"株価重複除外後: {len(df_prices):,}件")

    # 数値型に変換
    for col in ['Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS', 'ShOutFY', 'TrShFY', 'AvgSh']:
        if col in df_fins.columns:
            df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

    # BPS代替計算（前回のFF5戦略と同じロジック）
    df_fins['SharesOut'] = df_fins['ShOutFY'].fillna(df_fins['TrShFY']).fillna(df_fins['AvgSh'])
    df_fins['BPS_Calc'] = df_fins['Eq'] / df_fins['SharesOut']
    df_fins['BPS_Final'] = df_fins['BPS'].fillna(df_fins['BPS_Calc'])

    # 有効な財務データのみ（Eq > 0, SharesOut > 0）
    df_fins = df_fins[
        (df_fins['Eq'] > 0) &
        (df_fins['SharesOut'] > 0) &
        (df_fins['BPS_Final'] > 0)
    ].copy()

    logger.info(f"有効な財務データ: {len(df_fins):,}件")

    return df_prices, df_fins

# ===================================
# 財務指標計算
# ===================================

def calculate_financial_metrics(df_prices, df_fins, as_of_date):
    """
    特定日時点での財務指標を計算

    Args:
        df_prices: 株価データ
        df_fins: 財務データ
        as_of_date: 基準日

    Returns:
        DataFrame: Code, StockPrice, MarketCap, PBR, ROE
    """

    # as_of_date時点で利用可能なデータ
    available_fins = df_fins[df_fins['DiscDate'] <= as_of_date].copy()

    # 最新の財務データ
    latest_fins = available_fins.sort_values('DiscDate').groupby('Code').last().reset_index()

    # as_of_date前後5日間の株価（最も近い日の株価を取得）
    price_window = df_prices[
        (df_prices['Date'] >= as_of_date - pd.Timedelta(days=5)) &
        (df_prices['Date'] <= as_of_date + pd.Timedelta(days=5))
    ].copy()

    latest_prices = price_window.sort_values(['Code', 'Date']).groupby('Code').first().reset_index()
    latest_prices = latest_prices[['Code', 'Price']].rename(columns={'Price': 'StockPrice'})

    # マージ
    metrics = latest_fins.merge(latest_prices, on='Code', how='inner')

    # 時価総額・PBR・ROE計算
    metrics['MarketCap'] = metrics['StockPrice'] * metrics['SharesOut']
    metrics['PBR'] = metrics['StockPrice'] / metrics['BPS_Final']
    metrics['ROE'] = (metrics['NP'] / metrics['Eq']) * 100

    # 異常値除去
    metrics = metrics[
        (metrics['PBR'] > 0) &
        (metrics['PBR'] < 50) &
        (metrics['ROE'] > -100) &
        (metrics['ROE'] < 100) &
        (metrics['MarketCap'] > 1_000_000_000)
    ].copy()

    return metrics[['Code', 'StockPrice', 'MarketCap', 'PBR', 'ROE']]

# ===================================
# ポートフォリオ構築
# ===================================

def build_unit_share_portfolio(stock_candidates: pd.DataFrame,
                               target_positions: int = 20,
                               initial_capital: float = 10_000_000) -> dict:
    """100株単位ポートフォリオ構築"""

    if len(stock_candidates) == 0:
        return {
            'stocks': [],
            'shares': [],
            'prices': [],
            'amounts': []
        }

    # 上位N銘柄を選択
    selected = stock_candidates.head(target_positions).copy()

    # 1銘柄あたりの配分資金
    capital_per_stock = initial_capital / len(selected)

    stocks = []
    shares_list = []
    prices_list = []
    amounts_list = []

    for _, row in selected.iterrows():
        code = row['Code']
        price = row['StockPrice']

        # 100株単位で購入可能な株数を計算
        required_amount = price * UNIT_SHARES

        if required_amount <= capital_per_stock:
            shares = int(capital_per_stock // required_amount) * UNIT_SHARES

            if shares > 0:
                stocks.append(code)
                shares_list.append(shares)
                prices_list.append(price)
                amounts_list.append(shares * price)

    return {
        'stocks': stocks,
        'shares': shares_list,
        'prices': prices_list,
        'amounts': amounts_list
    }

# ===================================
# リターン計算
# ===================================

def calculate_portfolio_return(
    portfolio: dict,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    df_prices: pd.DataFrame,
    initial_capital: float
) -> dict:
    """ポートフォリオのリターン計算"""

    if not portfolio['stocks']:
        return {
            'gross_return': 0.0,
            'net_return': 0.0,
            'tax': 0.0,
            'total_investment': 0.0,
            'cash_remaining': initial_capital,
            'investment_ratio': 0.0
        }

    stocks = portfolio['stocks']
    start_shares = portfolio['shares']
    start_prices = portfolio['prices']
    start_amounts = portfolio['amounts']

    total_investment = sum(start_amounts)
    cash_remaining = initial_capital - total_investment

    # 終了時点の価格取得
    end_window = df_prices[
        (df_prices['Code'].isin(stocks)) &
        (df_prices['Date'] >= end_date - pd.Timedelta(days=5)) &
        (df_prices['Date'] <= end_date + pd.Timedelta(days=5))
    ].sort_values(['Code', 'Date']).groupby('Code').last()

    # 各銘柄の損益計算
    total_profit = 0.0
    total_start_value = 0.0

    for i, code in enumerate(stocks):
        if code not in end_window.index:
            continue

        shares = start_shares[i]
        start_price = start_prices[i]
        end_price = end_window.loc[code, 'Price']

        start_value = shares * start_price
        end_value = shares * end_price
        profit = end_value - start_value

        total_start_value += start_value
        total_profit += profit

    if total_start_value == 0:
        return {
            'gross_return': 0.0,
            'net_return': 0.0,
            'tax': 0.0,
            'total_investment': total_investment,
            'cash_remaining': cash_remaining,
            'investment_ratio': 0.0
        }

    # 税引前リターン（全資本ベース）
    gross_return_total = total_profit / initial_capital

    # 税金計算（利益のみ課税）
    taxable_profit = max(total_profit, 0)
    tax = taxable_profit * TAX_RATE

    # 税引後リターン（全資本ベース）
    net_profit = total_profit - tax
    net_return_total = net_profit / initial_capital
    tax_rate_total = tax / initial_capital

    return {
        'gross_return': gross_return_total,
        'net_return': net_return_total,
        'tax': tax_rate_total,
        'total_investment': total_investment,
        'cash_remaining': cash_remaining,
        'investment_ratio': total_investment / initial_capital
    }

# ===================================
# バックテスト
# ===================================

def smbc_value_quality_backtest_jquants(
    df_prices: pd.DataFrame,
    df_fins: pd.DataFrame,
    initial_capital: float = 10_000_000
) -> pd.DataFrame:
    """SMBC割安高質戦略バックテスト（J-Quantsデータ版）"""

    logger.info(f"バックテスト開始（初期資本{initial_capital:,.0f}円）...")

    # 10月1日のリバランス日を生成（2021年10月〜2025年10月）
    rebalance_dates = [pd.Timestamp(f'{year}-10-01') for year in range(2021, 2026)]

    logger.info(f"リバランス日数: {len(rebalance_dates)}回")
    logger.info(f"リバランス日: {[d.strftime('%Y-%m-%d') for d in rebalance_dates]}")

    strategy_results = []

    for i, rebalance_date in enumerate(rebalance_dates[:-1]):
        next_rebalance = rebalance_dates[i+1]

        logger.info(f"リバランス処理: {i+1}/{len(rebalance_dates)-1} - {rebalance_date.strftime('%Y-%m-%d')}")

        # リバランス日時点での財務指標計算
        metrics = calculate_financial_metrics(df_prices, df_fins, rebalance_date)

        if len(metrics) < 100:
            logger.warning(f"{rebalance_date}: データ不足（{len(metrics)}銘柄）")
            continue

        # PBRとROEでランキング
        metrics['PBR_Rank'] = metrics['PBR'].rank(method='first', ascending=True)
        metrics['ROE_Rank'] = metrics['ROE'].rank(method='first', ascending=False)

        # 四分位分割
        metrics['PBR_Quartile'] = pd.qcut(metrics['PBR_Rank'], q=4, labels=[1, 2, 3, 4])
        metrics['ROE_Quartile'] = pd.qcut(metrics['ROE_Rank'], q=4, labels=[1, 2, 3, 4])

        # ロング候補：低PBR × 高ROE
        long_candidates = metrics[
            (metrics['PBR_Quartile'] == 1) &
            (metrics['ROE_Quartile'] == 4)
        ].nsmallest(50, 'PBR')

        logger.info(f"  低PBR×高ROE候補: {len(long_candidates)}銘柄")

        # 100株単位ポートフォリオ構築
        portfolio = build_unit_share_portfolio(
            long_candidates,
            target_positions=20,
            initial_capital=initial_capital
        )

        logger.info(f"  選定: {len(portfolio['stocks'])}銘柄、投資額{sum(portfolio['amounts']):,.0f}円")

        # リターン計算
        result = calculate_portfolio_return(
            portfolio, rebalance_date, next_rebalance, df_prices, initial_capital
        )

        strategy_results.append({
            'date': next_rebalance,
            'strategy_return_gross': result['gross_return'],
            'strategy_return_net': result['net_return'],
            'tax': result['tax'],
            'long_count': len(portfolio['stocks']),
            'investment_ratio': result['investment_ratio']
        })

    return pd.DataFrame(strategy_results)

# ===================================
# パフォーマンス分析
# ===================================

def calculate_annual_performance(returns: pd.Series, dates: pd.Series = None) -> float:
    """年率リターン計算"""
    if len(returns) == 0:
        return 0.0

    cumulative = (1 + returns).prod()

    if dates is not None and len(dates) >= 2:
        start_date = dates.iloc[0]
        end_date = dates.iloc[-1]
        years = (end_date - start_date).days / 365.25
    else:
        years = len(returns)

    if years > 0:
        return ((cumulative ** (1/years)) - 1) * 100
    else:
        return 0.0

def calculate_metrics(results_df: pd.DataFrame) -> dict:
    """パフォーマンス指標計算"""

    returns = results_df['strategy_return_net']
    dates = results_df['date']

    # 累積リターン
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative / running_max) - 1

    # 年率リターン
    annual_return = calculate_annual_performance(returns, dates)

    # ボラティリティ（年率換算）
    start_date = dates.iloc[0]
    end_date = dates.iloc[-1]
    years = (end_date - start_date).days / 365.25
    periods_per_year = len(returns) / years if years > 0 else 1
    volatility = returns.std() * np.sqrt(periods_per_year) * 100

    # シャープレシオ
    sharpe = (returns.mean() / returns.std()) * np.sqrt(periods_per_year) if returns.std() > 0 else 0

    metrics = {
        'annual_return': annual_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe,
        'max_drawdown': drawdown.min() * 100,
        'win_rate': (returns > 0).sum() / len(returns) * 100,
        'avg_win': returns[returns > 0].mean() * 100 if (returns > 0).any() else 0,
        'avg_loss': returns[returns < 0].mean() * 100 if (returns < 0).any() else 0,
        'cumulative_return': (cumulative.iloc[-1] - 1) * 100,
        'avg_investment_ratio': results_df['investment_ratio'].mean() * 100,
        'avg_tax': results_df['tax'].mean() * 100,
        'total_tax': results_df['tax'].sum() * 100,
    }

    return metrics

# ===================================
# 結果出力
# ===================================

def print_performance_report(results_df: pd.DataFrame, metrics: dict):
    """パフォーマンスレポート出力"""

    print("\n" + "=" * 80)
    print("[パフォーマンス結果] SMBC割安高質戦略（J-Quantsデータ版）")
    print("=" * 80)

    gross_returns = results_df['strategy_return_gross']
    gross_dates = results_df['date']
    gross_annual = calculate_annual_performance(gross_returns, gross_dates)

    print(f"\n[戦略設定]")
    print(f"  戦略名:              割安高質（低PBR × 高ROE）")
    print(f"  データ期間:          2021-10 ~ 2025-10")
    print(f"  リバランス頻度:      年次（10月1日）")
    print(f"  制約:                100株単位購入制限")
    print(f"  平均ロング銘柄数:    {results_df['long_count'].mean():.1f}銘柄")
    print(f"  平均投資比率:        {metrics['avg_investment_ratio']:.1f}%")

    print(f"\n[税引き前パフォーマンス]")
    print(f"  累積リターン:        {(results_df['strategy_return_gross'] + 1).prod() - 1:>8.2%}")
    print(f"  年率リターン:        {gross_annual:8.2f}%")

    print(f"\n[税引き後パフォーマンス（実質）]")
    print(f"  累積リターン:        {metrics['cumulative_return']:8.2f}%")
    print(f"  年率リターン:        {metrics['annual_return']:8.2f}%")
    print(f"  シャープレシオ:      {metrics['sharpe_ratio']:8.2f}")
    print(f"  最大DD（年次）:      {metrics['max_drawdown']:8.2f}%")
    print(f"  年率ボラティリティ:  {metrics['volatility']:8.2f}%")

    print(f"\n[勝率・損益]")
    print(f"  年次勝率:            {metrics['win_rate']:8.1f}%")
    print(f"  平均利益（年次）:    {metrics['avg_win']:8.2f}%")
    print(f"  平均損失（年次）:    {metrics['avg_loss']:8.2f}%")

    print(f"\n[税金コストの影響]")
    print(f"  平均年次税負担:      {metrics['avg_tax']:8.3f}%")
    print(f"  累積税負担:          {metrics['total_tax']:8.2f}%")

    print("\n" + "=" * 100)
    print("[年次パフォーマンス詳細]（10月〜翌年10月）")
    print("=" * 100)

    print(f"\n{'期間':^20} {'税引前':>10} {'税引後':>10} {'税負担':>8} {'銘柄数':>6} {'投資比率':>8}")
    print(f"{'':^20} {'リターン':>10} {'リターン':>10} {'(%)':>8} {'':>6} {'(%)':>8}")
    print("-" * 100)

    for _, row in results_df.iterrows():
        start_year = row['date'].year - 1
        end_year = row['date'].year
        period_str = f"{start_year}年10月～{end_year}年10月"
        print(f"{period_str:^20} "
              f"{row['strategy_return_gross']*100:>9.2f}% "
              f"{row['strategy_return_net']*100:>9.2f}% "
              f"{row['tax']*100:>7.3f}% "
              f"{int(row['long_count']):>6d} "
              f"{row['investment_ratio']*100:>7.1f}%")

    print("\n" + "=" * 100)

# ===================================
# メイン実行
# ===================================

if __name__ == "__main__":

    print("=" * 80)
    print("SMBC「割安高質」戦略バックテスト（J-Quantsデータ版）")
    print("=" * 80)
    print(f"\n[検証概要]")
    print(f"  戦略名: 割安高質（低PBR × 高ROE）")
    print(f"  データソース: J-Quants API（2021-03～2026-03）")
    print(f"  検証期間: 2021年10月～2025年10月")
    print(f"  リバランス: 年次（10月1日）")
    print(f"  制約: 100株単位購入制限")
    print(f"  譲渡益税: {TAX_RATE*100:.3f}%")
    print(f"  実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # データ読み込み
    df_prices, df_fins = load_jquants_data()

    # バックテスト実行
    results = smbc_value_quality_backtest_jquants(df_prices, df_fins)

    if results.empty:
        logger.error("バックテスト実行失敗")
        exit(1)

    # パフォーマンス指標計算
    metrics = calculate_metrics(results)

    # 結果出力
    print_performance_report(results, metrics)

    # 結果保存
    output_dir = Path('results')
    output_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_dir / 'backtest_smbc_jquants.csv', index=False, encoding='utf-8-sig')

    logger.info(f"結果をCSVに保存: {output_dir / 'backtest_smbc_jquants.csv'}")

    print("\n" + "=" * 80)
    print("バックテスト完了")
    print("=" * 80)
    print(f"\n[出力ファイル]")
    print(f"  - バックテスト結果: {output_dir / 'backtest_smbc_jquants.csv'}")
    print(f"  - ログファイル: backtest_smbc_jquants.log")
    print("\n")
