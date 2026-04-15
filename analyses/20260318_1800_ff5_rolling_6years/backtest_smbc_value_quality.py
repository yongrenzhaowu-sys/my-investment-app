import pandas as pd
import numpy as np
import warnings
import os
import logging
from datetime import datetime

warnings.filterwarnings('ignore')

# ===================================
# ロギング設定
# ===================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest_smbc_value_quality.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===================================
# グローバル変数
# ===================================
CACHE_FILE = '../../legacy/_inbox/topix_quarterly_statements.csv'
PRICE_CACHE = {}

# 税金パラメータ
TAX_RATE = 0.20315  # 譲渡益税 20.315%

# 単位株制限
UNIT_SHARES = 100  # 100株単位

# ===================================
# A. 財務データ読み込み（列名自動判定版）
# ===================================

def load_financial_data(cache_filename: str = CACHE_FILE) -> pd.DataFrame:
    """財務諸表データをキャッシュから読み込み（列名を自動判定）"""

    if not os.path.exists(cache_filename):
        logger.error(f"財務データファイル '{cache_filename}' が見つかりません")
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            cache_filename,
            encoding='utf-8-sig',
            parse_dates=['DisclosedDate'],
            low_memory=False
        )

        logger.info(f"財務データ読み込み成功: {len(df):,}件")

        # 列名のマッピング
        column_mapping = {
            'IssuedShareTotal': ['IssuedShareTotal', 'NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock'],
            'Equity': ['Equity', 'NetAssets', 'TotalEquity'],
            'Profit': ['Profit', 'NetIncome', 'ProfitAttributableToOwnersOfParent']
        }

        available_cols = df.columns.tolist()
        required_columns = {}

        for target_col, possible_names in column_mapping.items():
            found = False
            for possible_name in possible_names:
                if possible_name in available_cols:
                    required_columns[target_col] = possible_name
                    found = True
                    break
            if not found:
                required_columns[target_col] = None

        rename_dict = {v: k for k, v in required_columns.items() if v is not None}
        df = df.rename(columns=rename_dict)

        for col in ['IssuedShareTotal', 'Equity', 'Profit']:
            if col not in df.columns:
                df[col] = 0

        base_cols = ['Code', 'DisclosedDate']
        if 'CompanyName' in df.columns:
            base_cols.append('CompanyName')

        final_cols = base_cols + ['Profit', 'Equity', 'IssuedShareTotal']
        df = df[final_cols].copy()

        logger.info(f"使用列: {df.columns.tolist()}")

        return df

    except Exception as e:
        logger.error(f"財務データ読み込みエラー: {e}", exc_info=True)
        return pd.DataFrame()

# ===================================
# B. 株価データ読み込み（メモリ効率化版）
# ===================================

def load_existing_price_data(ohlcv_dir: str = '../../legacy/_inbox/OHLCV_Adjusted') -> pd.DataFrame:
    """株価データ読み込み（メモリ効率化版）"""
    global PRICE_CACHE

    if not os.path.exists(ohlcv_dir):
        logger.error(f"株価データディレクトリ '{ohlcv_dir}' が見つかりません。")
        return pd.DataFrame()

    csv_files = sorted([
        f for f in os.listdir(ohlcv_dir)
        if f.startswith('OHLCV_Adjusted_') and f.endswith('.csv') and f != 'OHLCV_Adjusted_TOPIX.csv'
    ])

    if not csv_files:
        logger.error(f"ディレクトリ '{ohlcv_dir}' 内にCSVファイルが見つかりません。")
        return pd.DataFrame()

    logger.info(f"株価ファイル数: {len(csv_files)}個")

    all_dataframes = []
    usecols = ['Date', 'Ticker', 'AdjustmentClose']

    for idx, csv_file in enumerate(csv_files):
        if idx % 10 == 0:
            logger.info(f"株価ファイル読み込み中: {idx}/{len(csv_files)}")
        file_path = os.path.join(ohlcv_dir, csv_file)
        try:
            df = pd.read_csv(
                file_path,
                usecols=usecols,
                parse_dates=['Date'],
                dtype={'Ticker': 'Int64', 'AdjustmentClose': 'float32'}
            )

            df = df.drop_duplicates(subset=['Ticker', 'Date'], keep='first')
            all_dataframes.append(df)

        except Exception as e:
            logger.warning(f"ファイル読み込みエラー ({csv_file}): {e}")
            continue

    if not all_dataframes:
        return pd.DataFrame()

    logger.info("全ファイルを結合中...")
    df_all = pd.concat(all_dataframes, ignore_index=True)

    logger.info(f"結合完了: {len(df_all):,}件")

    df_all = df_all.rename(columns={'Ticker': 'Code', 'AdjustmentClose': 'Close'})
    df_all['Code'] = df_all['Code'].astype('str').str.replace('<NA>', '0').str.zfill(4)
    df_all = df_all.dropna(subset=['Close'])

    logger.info("重複除去 & ソート中...")
    df_all = df_all.sort_values(['Code', 'Date'])
    df_all = df_all.drop_duplicates(subset=['Code', 'Date'], keep='first')

    logger.info(f"重複除去後: {len(df_all):,}件")

    return df_all

# ===================================
# C. 財務指標計算（チャンク処理版）
# ===================================

def safe_code_to_int(code_series: pd.Series) -> pd.Series:
    """証券コードを整数に変換（ゼロ埋め対応）"""
    cleaned = code_series.astype(str).str.replace(r'\D', '', regex=True)
    cleaned = cleaned.replace('', '0')
    return pd.to_numeric(cleaned, errors='coerce').fillna(0).astype('int64')

def calculate_market_metrics_fast_chunked(statements_df: pd.DataFrame,
                                          prices_df: pd.DataFrame,
                                          chunk_size: int = 200) -> pd.DataFrame:
    """時価総額・PBR・ROE計算（チャンク処理版）"""

    logger.info("時価総額・PBR・ROE計算中（チャンク処理版）...")

    # prices_dfが空または必要な列が存在しない場合のチェック
    if prices_df.empty:
        logger.error("株価データが空です。株価データを読み込んでください。")
        return pd.DataFrame()

    if 'Code' not in prices_df.columns or 'Date' not in prices_df.columns or 'Close' not in prices_df.columns:
        logger.error(f"株価データに必要な列が存在しません。存在する列: {prices_df.columns.tolist()}")
        return pd.DataFrame()

    statements_df = statements_df.copy()
    statements_df['Profit'] = pd.to_numeric(statements_df['Profit'], errors='coerce').fillna(0)
    statements_df['Equity'] = pd.to_numeric(statements_df['Equity'], errors='coerce').fillna(0)
    statements_df['IssuedShareTotal'] = pd.to_numeric(statements_df['IssuedShareTotal'], errors='coerce').fillna(1)

    statements_df = statements_df[
        (statements_df['Equity'] > 0) &
        (statements_df['IssuedShareTotal'] > 0)
    ]
    logger.info(f"有効な財務データ: {len(statements_df):,}件")

    # Code変換
    logger.info("Code列を整数型に変換中...")
    statements_df['Code_int'] = safe_code_to_int(statements_df['Code'])
    prices_df['Code_int'] = safe_code_to_int(prices_df['Code'])

    statements_df = statements_df[statements_df['Code_int'] > 0]
    prices_df = prices_df[prices_df['Code_int'] > 0]

    # ソート
    statements_df = statements_df.sort_values(['Code_int', 'DisclosedDate']).reset_index(drop=True)
    prices_df = prices_df.sort_values(['Code_int', 'Date']).reset_index(drop=True)

    # 重複除去
    statements_df = statements_df.drop_duplicates(subset=['Code_int', 'DisclosedDate'], keep='first')
    prices_df = prices_df.drop_duplicates(subset=['Code_int', 'Date'], keep='first')

    logger.info(f"ソート・重複除去後: 財務 {len(statements_df):,}件, 株価 {len(prices_df):,}件")

    # 銘柄ごとにマージ
    logger.info("銘柄ごとにマージ中...")

    statements_groups = list(statements_df.groupby('Code_int'))
    prices_dict = {code: group for code, group in prices_df.groupby('Code_int')}

    merged_list = []
    num_chunks = (len(statements_groups) + chunk_size - 1) // chunk_size

    for chunk_idx in range(num_chunks):
        if chunk_idx % 5 == 0:
            logger.info(f"マージ処理: {chunk_idx}/{num_chunks}")
        start_idx = chunk_idx * chunk_size
        end_idx = min((chunk_idx + 1) * chunk_size, len(statements_groups))

        chunk_groups = statements_groups[start_idx:end_idx]

        for code, stmt_code in chunk_groups:
            if code not in prices_dict:
                continue

            price_code = prices_dict[code]

            if len(price_code) == 0:
                continue

            stmt_code = stmt_code.sort_values('DisclosedDate').reset_index(drop=True)
            price_code = price_code.sort_values('Date').reset_index(drop=True)

            try:
                merged = pd.merge_asof(
                    stmt_code,
                    price_code[['Date', 'Close']],
                    left_on='DisclosedDate',
                    right_on='Date',
                    direction='backward',
                    tolerance=pd.Timedelta(days=10)
                )

                if not merged.empty:
                    merged_list.append(merged)
            except Exception:
                continue

    if not merged_list:
        logger.error("マージ結果が空です")
        return pd.DataFrame()

    df_merged = pd.concat(merged_list, ignore_index=True)
    df_merged = df_merged.dropna(subset=['Close'])

    logger.info(f"マージ完了: {len(df_merged):,}件")

    # 財務指標計算
    df_merged['MarketCap'] = df_merged['Close'] * df_merged['IssuedShareTotal']
    df_merged['PBR'] = df_merged['MarketCap'] / df_merged['Equity']
    df_merged['ROE'] = (df_merged['Profit'] / df_merged['Equity']) * 100

    result_cols = ['Code', 'DisclosedDate', 'Close', 'MarketCap', 'PBR', 'ROE', 'Date']

    if 'CompanyName' in df_merged.columns:
        result_cols.insert(1, 'CompanyName')

    result_df = df_merged[result_cols].copy()
    result_df = result_df.rename(columns={'Close': 'StockPrice', 'Date': 'PriceDate'})

    # 異常値除去
    mask = (
        (result_df['PBR'] > 0) &
        (result_df['PBR'] < 50) &
        (result_df['ROE'] > -100) &
        (result_df['ROE'] < 100) &
        (result_df['MarketCap'] > 1_000_000_000)
    )

    result_df = result_df[mask].copy()

    logger.info(f"計算完了: {len(result_df):,}件")

    return result_df

# ===================================
# D. ポートフォリオ構築（100株単位制限版）
# ===================================

def build_unit_share_portfolio(stock_candidates: pd.DataFrame,
                               target_positions: int = 20,
                               initial_capital: float = 10_000_000) -> dict:
    """
    100株単位ポートフォリオ構築（実運用制約版）

    Args:
        stock_candidates: 候補銘柄データ
        target_positions: 目標銘柄数
        initial_capital: 初期資金

    Returns:
        dict: {
            'stocks': 選択された銘柄コードのリスト,
            'shares': 各銘柄の株数,
            'prices': 各銘柄の価格,
            'amounts': 各銘柄の投資額
        }
    """

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
# E. リターン計算（100株単位版）
# ===================================

def calculate_long_portfolio_return_with_units(
    portfolio: dict,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    prices_df: pd.DataFrame,
    initial_capital: float
) -> dict:
    """100株単位ポートフォリオのリターン計算"""

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
    end_window = prices_df[
        (prices_df['Code'].isin(stocks)) &
        (prices_df['Date'] >= end_date - pd.Timedelta(days=5)) &
        (prices_df['Date'] <= end_date + pd.Timedelta(days=5))
    ].sort_values(['Code', 'Date']).groupby('Code').last()

    # 各銘柄の損益計算
    total_profit = 0.0
    total_start_value = 0.0

    for i, code in enumerate(stocks):
        if code not in end_window.index:
            continue

        shares = start_shares[i]
        start_price = start_prices[i]
        end_price = end_window.loc[code, 'Close']

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

def calculate_topix_return(start_date: pd.Timestamp, end_date: pd.Timestamp,
                          prices_df: pd.DataFrame) -> float:
    """TOPIX基準リターン計算（全銘柄等ウェイト）"""
    all_stocks = prices_df['Code'].unique()[:100].tolist()

    # 開始時点の価格
    start_window = prices_df[
        (prices_df['Code'].isin(all_stocks)) &
        (prices_df['Date'] >= start_date - pd.Timedelta(days=5)) &
        (prices_df['Date'] <= start_date + pd.Timedelta(days=5))
    ].sort_values(['Code', 'Date']).groupby('Code').first()

    # 終了時点の価格
    end_window = prices_df[
        (prices_df['Code'].isin(all_stocks)) &
        (prices_df['Date'] >= end_date - pd.Timedelta(days=5)) &
        (prices_df['Date'] <= end_date + pd.Timedelta(days=5))
    ].sort_values(['Code', 'Date']).groupby('Code').last()

    common_codes = start_window.index.intersection(end_window.index)

    if len(common_codes) == 0:
        return 0.0

    start_prices = start_window.loc[common_codes, 'Close'].values
    end_prices = end_window.loc[common_codes, 'Close'].values
    returns = (end_prices - start_prices) / start_prices

    return np.mean(returns)

# ===================================
# F. バックテスト（10月1日リバランス・100株単位版）
# ===================================

def smbc_value_quality_backtest_october_unit(enhanced_financial_data: pd.DataFrame,
                                            prices_df: pd.DataFrame,
                                            initial_capital: float = 10_000_000) -> pd.DataFrame:
    """SMBC割安高質戦略（10月1日リバランス・100株単位制限版）"""

    logger.info(f"10月1日リバランス戦略バックテスト実行中（100株単位・初期資本{initial_capital:,.0f}円）...")

    # 10月1日のリバランス日を生成（2016年10月〜2025年10月）
    rebalance_dates = [pd.Timestamp(f'{year}-10-01') for year in range(2016, 2026)]

    logger.info(f"リバランス日数: {len(rebalance_dates)}回")
    logger.info(f"リバランス日: {[d.strftime('%Y-%m-%d') for d in rebalance_dates]}")

    strategy_results = []

    for i, rebalance_date in enumerate(rebalance_dates[:-1]):
        logger.info(f"リバランス処理: {i+1}/{len(rebalance_dates)-1} - {rebalance_date.strftime('%Y-%m-%d')}")
        next_rebalance = rebalance_dates[i+1]

        current_data = enhanced_financial_data[
            enhanced_financial_data['DisclosedDate'] <= rebalance_date
        ].copy()

        current_data = current_data.sort_values('DisclosedDate').groupby('Code').tail(1)

        if len(current_data) < 100:
            logger.warning(f"{rebalance_date}: データ不足（{len(current_data)}銘柄）")
            continue

        # PBRとROEでランキング
        current_data['PBR_Rank'] = current_data['PBR'].rank(method='first', ascending=True)
        current_data['ROE_Rank'] = current_data['ROE'].rank(method='first', ascending=False)

        # 四分位分割
        current_data['PBR_Quartile'] = pd.qcut(current_data['PBR_Rank'], q=4, labels=[1, 2, 3, 4])
        current_data['ROE_Quartile'] = pd.qcut(current_data['ROE_Rank'], q=4, labels=[1, 2, 3, 4])

        # ロング候補：低PBR × 高ROE
        long_candidates = current_data[
            (current_data['PBR_Quartile'] == 1) &
            (current_data['ROE_Quartile'] == 4)
        ].nsmallest(50, 'PBR')  # 上位50銘柄から選択

        # 100株単位ポートフォリオ構築
        long_portfolio = build_unit_share_portfolio(
            long_candidates,
            target_positions=20,
            initial_capital=initial_capital
        )

        logger.info(f"{rebalance_date.strftime('%Y-%m')}: {len(long_portfolio['stocks'])}銘柄選定、"
                   f"投資額{sum(long_portfolio['amounts']):,.0f}円")

        # リターン計算
        long_result = calculate_long_portfolio_return_with_units(
            long_portfolio, rebalance_date, next_rebalance, prices_df, initial_capital
        )

        topix_return = calculate_topix_return(rebalance_date, next_rebalance, prices_df)

        strategy_results.append({
            'date': next_rebalance,
            'strategy_return_gross': long_result['gross_return'],
            'strategy_return_net': long_result['net_return'],
            'long_return_gross': long_result['gross_return'],
            'long_return_net': long_result['net_return'],
            'tax': long_result['tax'],
            'topix_return': topix_return,
            'long_count': len(long_portfolio['stocks']),
            'investment_ratio': long_result['investment_ratio']
        })

    return pd.DataFrame(strategy_results)

# ===================================
# G. パフォーマンス分析
# ===================================

def calculate_annual_performance(returns: pd.Series, dates: pd.Series = None) -> float:
    """年率リターン計算"""
    if len(returns) == 0:
        return 0.0

    cumulative = (1 + returns).prod()

    if dates is not None and len(dates) >= 2:
        start_date = dates.iloc[0] if isinstance(dates.iloc[0], pd.Timestamp) else pd.Timestamp(dates.iloc[0])
        end_date = dates.iloc[-1] if isinstance(dates.iloc[-1], pd.Timestamp) else pd.Timestamp(dates.iloc[-1])
        years = (end_date - start_date).days / 365.25
    else:
        years = len(returns)

    if years > 0:
        return ((cumulative ** (1/years)) - 1) * 100
    else:
        return 0.0

def calculate_volatility_annualized(returns: pd.Series, dates: pd.Series = None) -> float:
    """年率換算ボラティリティ計算"""
    if len(returns) == 0:
        return 0.0

    period_std = returns.std()

    if dates is not None and len(dates) >= 2:
        start_date = dates.iloc[0] if isinstance(dates.iloc[0], pd.Timestamp) else pd.Timestamp(dates.iloc[0])
        end_date = dates.iloc[-1] if isinstance(dates.iloc[-1], pd.Timestamp) else pd.Timestamp(dates.iloc[-1])
        years = (end_date - start_date).days / 365.25
        periods_per_year = len(returns) / years if years > 0 else len(returns)
    else:
        periods_per_year = 1

    if periods_per_year > 0:
        return period_std * np.sqrt(periods_per_year) * 100
    else:
        return 0.0

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, dates: pd.Series = None) -> float:
    """シャープレシオ計算（年率換算）"""
    if len(returns) == 0 or returns.std() == 0:
        return 0.0

    excess_returns = returns - risk_free_rate
    mean_return = excess_returns.mean()
    std_return = excess_returns.std()

    if dates is not None and len(dates) >= 2:
        start_date = dates.iloc[0] if isinstance(dates.iloc[0], pd.Timestamp) else pd.Timestamp(dates.iloc[0])
        end_date = dates.iloc[-1] if isinstance(dates.iloc[-1], pd.Timestamp) else pd.Timestamp(dates.iloc[-1])
        years = (end_date - start_date).days / 365.25
        periods_per_year = len(returns) / years if years > 0 else len(returns)
    else:
        periods_per_year = 1

    if std_return > 0:
        return (mean_return / std_return) * np.sqrt(periods_per_year)
    else:
        return 0.0

def calculate_sortino_ratio(returns: pd.Series, target: float = 0.0) -> float:
    """ソルティノレシオ計算"""
    excess_returns = returns - target
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0:
        return np.inf if excess_returns.mean() > 0 else 0.0
    elif len(downside_returns) == 1:
        downside_std = abs(downside_returns.iloc[0])
    else:
        downside_std = downside_returns.std()

    if downside_std > 0:
        return (excess_returns.mean() / downside_std) * np.sqrt(1)
    else:
        return 0.0

def calculate_calmar_ratio(returns: pd.Series, dates: pd.Series = None) -> float:
    """カルマーレシオ計算"""
    annual_return = calculate_annual_performance(returns, dates)
    mdd_result = calculate_max_drawdown(returns, dates)
    max_dd = abs(mdd_result['max_drawdown'])
    return annual_return / max_dd if max_dd > 0 else 0

def calculate_max_drawdown(returns: pd.Series, dates: pd.Series = None) -> dict:
    """最大ドローダウン計算（発生日も返す）"""
    if len(returns) == 0:
        return {
            'max_drawdown': 0.0,
            'mdd_date': None,
            'mdd_period': None
        }

    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max

    min_dd_idx = drawdown.idxmin()
    max_dd_value = drawdown.min() * 100

    mdd_date = None
    mdd_period = None

    if dates is not None and len(dates) > 0:
        if min_dd_idx in dates.index:
            mdd_date = dates.loc[min_dd_idx]
        elif isinstance(min_dd_idx, (int, np.integer)) and 0 <= min_dd_idx < len(dates):
            mdd_date = dates.iloc[min_dd_idx]

        if mdd_date is not None:
            if isinstance(min_dd_idx, (int, np.integer)) and min_dd_idx > 0 and min_dd_idx < len(dates):
                prev_date = dates.iloc[min_dd_idx - 1]
                if isinstance(prev_date, pd.Timestamp) and isinstance(mdd_date, pd.Timestamp):
                    prev_year = prev_date.year - 1
                    curr_year = mdd_date.year
                    mdd_period = f"{prev_year}年10月〜{curr_year}年10月"
            elif isinstance(mdd_date, pd.Timestamp):
                prev_year = mdd_date.year - 1
                curr_year = mdd_date.year
                mdd_period = f"{prev_year}年10月〜{curr_year}年10月"

    return {
        'max_drawdown': max_dd_value,
        'mdd_date': mdd_date,
        'mdd_period': mdd_period
    }

def calculate_additional_metrics(results_df: pd.DataFrame) -> dict:
    """追加パフォーマンス指標の計算"""

    returns = results_df['strategy_return_net']
    dates = results_df.get('date', None)

    mdd_result = calculate_max_drawdown(returns, dates)

    metrics = {
        'annual_return': calculate_annual_performance(returns, dates),
        'sharpe_ratio': calculate_sharpe_ratio(returns, risk_free_rate=0.0, dates=dates),
        'sortino_ratio': calculate_sortino_ratio(returns),
        'calmar_ratio': calculate_calmar_ratio(returns, dates),
        'max_drawdown': mdd_result['max_drawdown'],
        'mdd_date': mdd_result['mdd_date'],
        'mdd_period': mdd_result['mdd_period'],
        'win_rate': (returns > 0).sum() / len(returns) * 100,
        'avg_win': returns[returns > 0].mean() * 100 if (returns > 0).any() else 0,
        'avg_loss': returns[returns < 0].mean() * 100 if (returns < 0).any() else 0,
        'profit_factor': abs(returns[returns > 0].sum() / returns[returns < 0].sum()) if (returns < 0).any() else np.inf,
        'var_95': np.percentile(returns, 5) * 100,
        'cvar_95': returns[returns <= np.percentile(returns, 5)].mean() * 100,
        'volatility': calculate_volatility_annualized(returns, dates),
        'avg_annual_tax': results_df['tax'].mean() * 100,
        'total_tax': results_df['tax'].sum() * 100,
        'avg_investment_ratio': results_df['investment_ratio'].mean() * 100,
    }

    return metrics

# ===================================
# H. 結果出力（10月1日リバランス・100株単位版）
# ===================================

def print_performance_report_october_unit(results_df: pd.DataFrame, metrics: dict):
    """パフォーマンスレポート出力（10月1日リバランス・100株単位版）"""

    print("\n" + "=" * 80)
    print("[パフォーマンス結果] 10月1日リバランス戦略（100株単位制限）")
    print("=" * 80)

    gross_returns = results_df['strategy_return_gross']
    gross_dates = results_df.get('date', None)
    gross_annual = calculate_annual_performance(gross_returns, gross_dates)
    gross_sharpe = calculate_sharpe_ratio(gross_returns, risk_free_rate=0.0, dates=gross_dates)
    gross_mdd_result = calculate_max_drawdown(gross_returns, gross_dates)
    gross_dd = gross_mdd_result['max_drawdown']

    topix_annual = calculate_annual_performance(results_df['topix_return'])

    print(f"\n【戦略設定】")
    print(f"  ポジション:          ロングのみ（ショートなし）")
    print(f"  リバランス頻度:      年次（10月1日）")
    print(f"  制約:                100株単位購入制限")
    print(f"  平均ロング銘柄数:    {results_df['long_count'].mean():.1f}銘柄")
    print(f"  平均投資比率:        {metrics['avg_investment_ratio']:.1f}%")

    print(f"\n【税引き前パフォーマンス】")
    print(f"  年率リターン:        {gross_annual:8.2f}%")
    print(f"  シャープレシオ:      {gross_sharpe:8.2f}")
    print(f"  最大DD:              {gross_dd:8.2f}%")

    print(f"\n【税引き後パフォーマンス（実質）】")
    print(f"  年率リターン:        {metrics['annual_return']:8.2f}%")
    print(f"  シャープレシオ:      {metrics['sharpe_ratio']:8.2f}")
    sortino_display = metrics['sortino_ratio']
    if np.isinf(sortino_display):
        print(f"  ソルティノレシオ:    {'無限大':>8s} (損失なし)")
    else:
        print(f"  ソルティノレシオ:    {sortino_display:8.2f}")
    print(f"  カルマーレシオ:      {metrics['calmar_ratio']:8.2f}")
    print(f"  最大DD:              {metrics['max_drawdown']:8.2f}%")
    if metrics.get('mdd_date') is not None:
        mdd_date_str = metrics['mdd_date'].strftime('%Y年%m月%d日') if isinstance(metrics['mdd_date'], pd.Timestamp) else str(metrics['mdd_date'])
        if metrics.get('mdd_period'):
            print(f"  MDD発生日:          {mdd_date_str} ({metrics['mdd_period']})")
        else:
            print(f"  MDD発生日:          {mdd_date_str}")
    print(f"  年率ボラティリティ:  {metrics['volatility']:8.2f}%")

    print(f"\n【勝率・損益】")
    print(f"  年次勝率:            {metrics['win_rate']:8.1f}%")
    print(f"  平均利益（年次）:    {metrics['avg_win']:8.2f}%")
    print(f"  平均損失（年次）:    {metrics['avg_loss']:8.2f}%")
    print(f"  プロフィットファクター: {metrics['profit_factor']:8.2f}")

    print(f"\n【税金コストの影響】")
    print(f"  リターン減少:        {gross_annual - metrics['annual_return']:8.2f}%")
    print(f"  平均年次税負担:      {metrics['avg_annual_tax']:8.3f}%")
    print(f"  累積税負担:          {metrics['total_tax']:8.2f}%")

    print(f"\n【ベンチマーク比較】")
    print(f"  TOPIX年率リターン:   {topix_annual:8.2f}%")
    print(f"  税引き前 vs TOPIX:   {gross_annual - topix_annual:+8.2f}%")
    print(f"  税引き後 vs TOPIX:   {metrics['annual_return'] - topix_annual:+8.2f}%")

    print(f"\n【S&P500比較（参考年率12.0%）】")
    print(f"  税引き前 vs S&P500:  {gross_annual - 12.0:+8.2f}%")
    print(f"  税引き後 vs S&P500:  {metrics['annual_return'] - 12.0:+8.2f}%")

    print("\n" + "=" * 110)
    print("[年次パフォーマンス詳細]（10月〜翌年10月）")
    print("=" * 110)

    print(f"\n{'期間':^20} {'税引前':>10} {'税引後':>10} {'TOPIX':>10} {'超過':>10} {'税負担':>8} {'銘柄数':>6} {'投資比率':>8}")
    print(f"{'':^20} {'リターン':>10} {'リターン':>10} {'リターン':>10} {'リターン':>10} {'(%)':>8} {'':>6} {'(%)':>8}")
    print("-" * 110)

    for _, row in results_df.iterrows():
        start_year = row['date'].year - 1
        end_year = row['date'].year
        period_str = f"{start_year}年10月〜{end_year}年10月"
        print(f"{period_str:^20} "
              f"{row['strategy_return_gross']*100:>9.2f}% "
              f"{row['strategy_return_net']*100:>9.2f}% "
              f"{row['topix_return']*100:>9.2f}% "
              f"{(row['strategy_return_net'] - row['topix_return'])*100:>+9.2f}% "
              f"{row['tax']*100:>7.3f}% "
              f"{int(row['long_count']):>6d} "
              f"{row['investment_ratio']*100:>7.1f}%")

    print("\n" + "=" * 110)

# ===================================
# I. メイン実行
# ===================================

if __name__ == "__main__":

    print("=" * 80)
    print("SMBC「割安高質」戦略 - 10月1日リバランス版（100株単位制限）")
    print("=" * 80)
    print(f"\n[検証概要]")
    print(f"  戦略名: 割安高質（ロングオンリー）")
    print(f"  検証期間: 2016年10月〜2025年10月")
    print(f"  リバランス: 年次（10月1日）")
    print(f"  ポジション: ロングのみ（ショートなし）")
    print(f"  制約: 100株単位購入制限")
    print(f"  譲渡益税: {TAX_RATE*100:.3f}%")
    print(f"  実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # データ読み込み
    statements_df = load_financial_data()
    if statements_df.empty:
        logger.error("財務データ読み込み失敗")
        exit(1)

    prices_df = load_existing_price_data()
    if prices_df.empty:
        logger.error("株価データ読み込み失敗")
        exit(1)

    # 財務指標計算
    enhanced_financial_data = calculate_market_metrics_fast_chunked(statements_df, prices_df, chunk_size=200)
    if enhanced_financial_data.empty:
        logger.error("財務指標計算失敗")
        exit(1)

    # バックテスト実行
    results = smbc_value_quality_backtest_october_unit(enhanced_financial_data, prices_df)
    if results.empty:
        logger.error("バックテスト実行失敗")
        exit(1)

    # パフォーマンス指標計算
    metrics = calculate_additional_metrics(results)

    # 結果出力
    print_performance_report_october_unit(results, metrics)

    # 結果保存
    output_dir = 'analyses/20260318_1800_ff5_rolling_6years/results'
    os.makedirs(output_dir, exist_ok=True)
    results.to_csv(f'{output_dir}/backtest_smbc_value_quality.csv', index=False, encoding='utf-8-sig')

    logger.info(f"結果をCSVに保存: {output_dir}/backtest_smbc_value_quality.csv")

    print("\n" + "=" * 80)
    print("10月1日リバランス戦略検証完了（100株単位制限版）")
    print("=" * 80)
    print(f"\n[出力ファイル]")
    print(f"  - バックテスト結果: {output_dir}/backtest_smbc_value_quality.csv")
    print(f"  - ログファイル: backtest_smbc_value_quality.log")
    print("\n")
