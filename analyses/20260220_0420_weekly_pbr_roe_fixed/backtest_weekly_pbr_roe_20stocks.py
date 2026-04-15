"""PBR×ROE週次ロングオンリー戦略 バックテスト実行スクリプト（Phase 2改良版 - 高速化）
- しきい値ベースリバランス（必要時のみリバランス）
- ボラティリティベースのポジションサイジング（低ボラ銘柄に高ウェイト）
- 高速化: 価格データピボット化、計算最適化、プログレス表示
"""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("tqdmが利用できません。プログレス表示なしで実行します。")

# ===== Config =====
FINANCIAL_DATA_PATH = 'topix_quarterly_statements.csv'
PRICE_DATA_PATH     = 'all_prices_cache.parquet'
TOPIX_PATH          = './OHLCV_Adjusted/OHLCV_Adjusted_TOPIX.csv'
INITIAL_CAPITAL     = 10_000_000
START_DATE          = '2016-01-01'
END_DATE            = '2025-11-30'
SLIPPAGE            = 0.003
TAX_RATE            = 0.20315
MAX_STOCKS          = 20  # 銘柄数変更: 50 → 20
MIN_STOCKS          = 10
MIN_EQUITY          = 1_000_000
MIN_ISSUED_SHARES   = 1_000
MIN_PRICE           = 100
MAX_PBR             = 10.0
MIN_ROE             = -1.0
MAX_ROE             = 5.0
# Phase 2改良パラメータ
REBALANCE_THRESHOLD = 0.3  # ポートフォリオ重複率が70%未満の場合のみリバランス
VOL_LOOKBACK        = 60   # ボラティリティ計算期間（日）

t0 = time.time()
print('データ読み込み中...')

# Load financial data - 必要な列のみ
shares_col = 'NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock'
needed_cols = ['Code', 'DisclosedDate', 'TypeOfCurrentPeriod', 'Profit', 'Equity', shares_col]
optional_cols = ['CompanyName', 'Sector33CodeName']

# Check which optional columns exist
df_sample = pd.read_csv(FINANCIAL_DATA_PATH, encoding='utf-8-sig', nrows=1)
available_optional = [c for c in optional_cols if c in df_sample.columns]
cols_to_read = needed_cols + available_optional

df = pd.read_csv(
    FINANCIAL_DATA_PATH,
    encoding='utf-8-sig',
    parse_dates=['DisclosedDate'],
    usecols=cols_to_read,
    low_memory=False
)
df = df.rename(columns={shares_col: 'IssuedShareTotal'})
df_fy = df[df['TypeOfCurrentPeriod'] == 'FY'].copy()
df_fy['Code'] = df_fy['Code'].astype(str)
for col in ['Profit', 'Equity', 'IssuedShareTotal']:
    df_fy[col] = pd.to_numeric(df_fy[col], errors='coerce')
df_fy = df_fy[
    (df_fy['Equity'] > MIN_EQUITY) &
    (df_fy['IssuedShareTotal'] > MIN_ISSUED_SHARES) &
    (df_fy['Profit'].notna())
].copy()
df_fy['ROE'] = df_fy['Profit'] / df_fy['Equity']
df_fy['BPS'] = df_fy['Equity'] / df_fy['IssuedShareTotal']
df_fy = df_fy[
    (df_fy['ROE'] >= MIN_ROE) & (df_fy['ROE'] <= MAX_ROE) & (df_fy['BPS'] > 0)
].sort_values(['Code', 'DisclosedDate']).copy()
print(f'財務データ: {len(df_fy):,}件, {df_fy["Code"].nunique():,}銘柄')

# Load prices - 必要な列のみ
prices = pd.read_parquet(PRICE_DATA_PATH, columns=['Code', 'Date', 'Close'])
prices['Date'] = pd.to_datetime(prices['Date'])
prices['Code'] = prices['Code'].astype(str)
prices['Close'] = pd.to_numeric(prices['Close'], errors='coerce')
prices = prices[
    (prices['Close'] > 0) &
    (prices['Date'] >= pd.Timestamp(START_DATE)) &
    (prices['Date'] <= pd.Timestamp(END_DATE))
].copy()
print(f'株価データ: {len(prices):,}件, {prices["Code"].nunique():,}銘柄')

# 高速化: 価格データをピボットテーブルに変換（日付×銘柄コード）
print('価格データをピボット化中...')
price_pivot = prices.pivot_table(index='Date', columns='Code', values='Close')
print(f'ピボットテーブル: {price_pivot.shape[0]:,}日 × {price_pivot.shape[1]:,}銘柄')

# Load TOPIX
topix = pd.read_csv(TOPIX_PATH)
topix['Date'] = pd.to_datetime(topix['Date'].astype(str), format='%Y%m%d')
topix = topix.rename(columns={'AdjustmentClose': 'TOPIX'})
topix = topix[
    (topix['Date'] >= pd.Timestamp(START_DATE)) &
    (topix['Date'] <= pd.Timestamp(END_DATE))
][['Date', 'TOPIX']].sort_values('Date')

print(f'データ読み込み完了: {time.time()-t0:.1f}秒')

# Weekly rebalance dates (first trading day of each week)
trading_days = pd.Series(sorted(price_pivot.index))
rebalance_dates = trading_days.groupby(trading_days.dt.to_period('W')).first().values
rebalance_dates = sorted([pd.Timestamp(d) for d in rebalance_dates])
print(f'リバランス日数: {len(rebalance_dates)}件 ({rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()})')

# ===== Phase 2改良: しきい値ベースリバランス =====
def need_rebalance(current_portfolio, new_portfolio, threshold=REBALANCE_THRESHOLD):
    """ポートフォリオの重複率が (1-threshold) 未満の場合のみリバランス"""
    if current_portfolio.empty or new_portfolio.empty:
        return True

    current_set = set(current_portfolio['Code'])
    new_set = set(new_portfolio['Code'])

    overlap = len(current_set & new_set)
    overlap_ratio = overlap / max(len(current_set), 1)

    return overlap_ratio < (1 - threshold)

# ===== Phase 2改良: ボラティリティベースのウェイト計算（高速化版） =====
def calculate_volatility_weights(selected_codes, price_pivot_df, rebal_date, lookback=VOL_LOOKBACK):
    """
    過去のボラティリティに基づいてウェイトを計算（ピボットテーブル版）
    低ボラティリティ銘柄に高いウェイトを配分
    """
    weights = {}
    end_date = rebal_date
    start_date = end_date - pd.Timedelta(days=lookback * 2)

    # 期間の価格データを一括取得
    mask = (price_pivot_df.index >= start_date) & (price_pivot_df.index <= end_date)
    period_prices = price_pivot_df.loc[mask, selected_codes].copy()

    for code in selected_codes:
        if code not in period_prices.columns:
            weights[code] = 0
            continue

        stock_prices = period_prices[code].dropna().tail(lookback)

        if len(stock_prices) < 20:
            weights[code] = 0
            continue

        returns = stock_prices.pct_change().dropna()
        volatility = returns.std()

        # 逆ボラティリティウェイト
        weights[code] = 1 / max(volatility, 0.001)

    # 正規化
    total = sum(weights.values())
    if total > 0:
        return {k: v/total for k, v in weights.items()}
    else:
        # フォールバック: 均等ウェイト
        return {k: 1.0/len(selected_codes) for k in selected_codes}

# Helper: get latest financials as of date (no look-ahead)
def get_latest_financials(financial_df, as_of_date):
    avail = financial_df[financial_df['DisclosedDate'] < as_of_date]
    if avail.empty:
        return pd.DataFrame()
    return avail.sort_values('DisclosedDate').groupby('Code').last().reset_index()

# Helper: get prices on date（高速化版：ピボットテーブル使用）
def get_prices_on_date(price_pivot_df, target_date, tolerance_days=5):
    """ピボットテーブルから指定日の価格を取得"""
    start = target_date - pd.Timedelta(days=tolerance_days)
    end = target_date + pd.Timedelta(days=tolerance_days)

    # 期間内のデータを取得
    mask = (price_pivot_df.index >= start) & (price_pivot_df.index <= end)
    period_data = price_pivot_df.loc[mask]

    if period_data.empty:
        return {}

    # 最も近い日付のデータを選択
    date_diffs = abs(period_data.index - target_date)
    closest_idx = date_diffs.argmin()
    closest_date = period_data.index[closest_idx]

    # Seriesをdictに変換（NaNを除外）
    prices_series = period_data.loc[closest_date].dropna()
    return prices_series.to_dict()

# Helper: select portfolio（高速化版）
def select_portfolio(financial_df, price_pivot_df, rebal_date):
    latest_fin = get_latest_financials(financial_df, rebal_date)
    if latest_fin.empty:
        return pd.DataFrame()
    prices_dict = get_prices_on_date(price_pivot_df, rebal_date)
    if not prices_dict:
        return pd.DataFrame()
    latest_fin = latest_fin[latest_fin['Code'].isin(prices_dict)].copy()
    latest_fin['Price'] = latest_fin['Code'].map(prices_dict)
    if len(latest_fin) < MIN_STOCKS:
        return pd.DataFrame()
    latest_fin['PBR'] = latest_fin['Price'] / latest_fin['BPS']
    merged = latest_fin[
        (latest_fin['Price'] >= MIN_PRICE) &
        (latest_fin['PBR'] > 0) &
        (latest_fin['PBR'] <= MAX_PBR)
    ].copy()
    if len(merged) < MIN_STOCKS:
        return pd.DataFrame()
    merged['PBR_Q'] = pd.qcut(merged['PBR'], q=4, labels=[1, 2, 3, 4], duplicates='drop').astype(float)
    merged['ROE_Q'] = pd.qcut(
        merged['ROE'].rank(method='first', ascending=False),
        q=4, labels=[1, 2, 3, 4], duplicates='drop'
    ).astype(float)
    cands = merged[(merged['PBR_Q'] == 1) & (merged['ROE_Q'] == 1)].nsmallest(MAX_STOCKS, 'PBR').copy()
    if len(cands) < MIN_STOCKS:
        return pd.DataFrame()
    cands['Weight'] = 1.0 / len(cands)
    return cands

# Phase 2改良: ボラティリティウェイト版のselect_portfolio（高速化版）
# 修正: ボラティリティウェイトを無効化して均等ウェイトで実行
def select_portfolio_with_vol_weights(financial_df, price_pivot_df, rebal_date):
    """均等ウェイト版（ボラティリティウェイトを無効化）"""
    # 通常の方法で銘柄を選択（すでに均等ウェイトが設定されている）
    portfolio = select_portfolio(financial_df, price_pivot_df, rebal_date)
    return portfolio

# ===== MAIN BACKTEST =====
print()
print('週次バックテスト実行中（Phase 2改良版 - 高速化）...')
results        = []
capital        = INITIAL_CAPITAL
equity_curve   = [{'date': rebalance_dates[0], 'value': capital}]
prev_portfolio = pd.DataFrame()

# 年間損益通算用
annual_pnl_yen = 0.0   # 年間累積実現損益（円）
prev_year      = None
annual_tax_log = []    # 年末税金精算ログ

# Phase 2改良: リバランス統計
rebalance_count = 0
skipped_count = 0

# プログレスバー設定
iterator = tqdm(enumerate(rebalance_dates), total=len(rebalance_dates), desc='バックテスト進行') if TQDM_AVAILABLE else enumerate(rebalance_dates)

for i, rebal_date in iterator:
    curr_year        = rebal_date.year
    curr_prices_dict = get_prices_on_date(price_pivot, rebal_date)

    # ---- 年末税金精算: 新しい年に入ったタイミングで前年分を精算 ----
    if prev_year is not None and curr_year != prev_year:
        annual_tax = max(annual_pnl_yen, 0) * TAX_RATE
        capital   -= annual_tax
        # 直近のequity_curveの値を税引後に更新
        if equity_curve:
            equity_curve[-1]['value'] = capital
        annual_tax_log.append({
            'year':          prev_year,
            'pnl_yen':       annual_pnl_yen,
            'tax_yen':       annual_tax,
            'tax_rate_eff':  annual_tax / annual_pnl_yen * 100 if annual_pnl_yen > 0 else 0.0
        })
        annual_pnl_yen = 0.0  # リセット

    prev_year = curr_year

    # Compute return on PREV portfolio over this period
    if i > 0 and not prev_portfolio.empty and curr_prices_dict:
        capital_before = capital
        gross_returns  = []
        weights        = []
        for _, row in prev_portfolio.iterrows():
            code        = row['Code']
            start_price = row['Price']
            w           = row['Weight']
            end_price   = curr_prices_dict.get(code, None)
            if end_price and end_price > 0 and start_price > 0:
                gross_returns.append((end_price - start_price) / start_price)
            else:
                gross_returns.append(0.0)
            weights.append(w)

        total_w      = sum(weights)
        gross_return = sum(r * w for r, w in zip(gross_returns, weights)) / total_w if total_w > 0 else 0.0

        # Transaction cost (turnover-based)
        prev_codes  = set(prev_portfolio['Code'].tolist())
        new_pf_temp = select_portfolio(df_fy, price_pivot, rebal_date)
        new_codes   = set(new_pf_temp['Code'].tolist()) if not new_pf_temp.empty else set()
        sold        = len(prev_codes - new_codes)
        bought      = len(new_codes - prev_codes)
        n_prev      = max(len(prev_codes), 1)
        txn_cost    = (sold + bought) * SLIPPAGE / n_prev

        # 年間損益を累積（月次での税引きなし）
        pnl_yen         = gross_return * capital_before
        annual_pnl_yen += pnl_yen

        # 月次ネットリターン（税なし）
        net_return = gross_return - txn_cost
        capital    = capital * (1 + net_return)

        results.append({
            'date':            rebal_date,
            'gross_return':    gross_return * 100,
            'txn_cost':        txn_cost * 100,
            'net_return':      net_return * 100,   # 税引き前（年末精算）
            'capital':         capital,
            'n_stocks':        len(prev_portfolio),
            'annual_pnl_yen':  annual_pnl_yen
        })
        equity_curve.append({'date': rebal_date, 'value': capital})

    # 修正: 毎週必ずリバランス（閾値チェックを無効化）
    new_portfolio_candidate = select_portfolio_with_vol_weights(df_fy, price_pivot, rebal_date)

    # 常にリバランスを実行
    prev_portfolio = new_portfolio_candidate
    rebalance_count += 1

    # tqdmが無い場合の進捗表示
    if not TQDM_AVAILABLE and (i + 1) % 50 == 0:
        n_held = len(prev_portfolio) if not prev_portfolio.empty else 0
        print(f'  {i+1}/{len(rebalance_dates)} ({rebal_date.strftime("%Y-%m")}) '
              f'資本={capital:,.0f}円  保有={n_held}銘柄  RB={rebalance_count}/{i+1}  経過={time.time()-t0:.0f}秒')

# ---- 最終年の税金精算 ----
final_annual_tax = max(annual_pnl_yen, 0) * TAX_RATE
capital         -= final_annual_tax
if equity_curve:
    equity_curve[-1]['value'] = capital
annual_tax_log.append({
    'year':          prev_year,
    'pnl_yen':       annual_pnl_yen,
    'tax_yen':       final_annual_tax,
    'tax_rate_eff':  final_annual_tax / annual_pnl_yen * 100 if annual_pnl_yen > 0 else 0.0
})

print(f'\nバックテスト完了: {time.time()-t0:.1f}秒')

results_df   = pd.DataFrame(results)
equity_df    = pd.DataFrame(equity_curve)
tax_log_df   = pd.DataFrame(annual_tax_log)

print(f'\n年末税金精算ログ:')
print(tax_log_df.to_string(index=False))

# Phase 2改良: リバランス統計
print(f'\nPhase 2リバランス統計:')
print(f'  総リバランス機会: {len(rebalance_dates)}回')
print(f'  実際にリバランス: {rebalance_count}回 ({rebalance_count/len(rebalance_dates)*100:.1f}%)')
print(f'  スキップ: {skipped_count}回 ({skipped_count/len(rebalance_dates)*100:.1f}%)')
print(f'  取引削減率: {skipped_count/len(rebalance_dates)*100:.1f}%')

# ===== PERFORMANCE METRICS =====
monthly_returns = results_df['net_return'].values / 100
years           = (results_df['date'].max() - results_df['date'].min()).days / 365.25
total_return    = (capital / INITIAL_CAPITAL) - 1
annual_return   = (1 + total_return) ** (1 / years) - 1
monthly_vol     = np.std(monthly_returns, ddof=1)
annual_vol      = monthly_vol * np.sqrt(12)
mean_monthly    = np.mean(monthly_returns)
sharpe          = (mean_monthly * 12) / annual_vol if annual_vol > 0 else 0.0
downside        = monthly_returns[monthly_returns < 0]
downside_vol    = np.std(downside, ddof=1) * np.sqrt(12) if len(downside) > 1 else 1.0
sortino         = (mean_monthly * 12) / downside_vol if downside_vol > 0 else 0.0
equity_vals     = equity_df['value'].values
rolling_max     = np.maximum.accumulate(equity_vals)
drawdowns       = (equity_vals - rolling_max) / rolling_max
max_dd          = drawdowns.min() * 100
calmar          = (annual_return * 100) / abs(max_dd) if abs(max_dd) > 0 else 0.0
win_rate        = (monthly_returns > 0).mean() * 100
wins            = monthly_returns[monthly_returns > 0].sum()
losses          = abs(monthly_returns[monthly_returns < 0].sum())
profit_factor   = wins / losses if losses > 0 else float('inf')

# TOPIX comparison
topix_a = topix[(topix['Date'] >= results_df['date'].min()) & (topix['Date'] <= results_df['date'].max())]
topix_total  = (topix_a['TOPIX'].iloc[-1] / topix_a['TOPIX'].iloc[0] - 1)
topix_annual = (1 + topix_total) ** (1 / years) - 1
alpha        = (annual_return - topix_annual) * 100

print()
print('=' * 80)
print('  PBR×ROE週次ロングオンリー戦略 パフォーマンス（年間損益通算）')
print('  - 毎週リバランス（閾値チェック無効化）')
print('  - 均等ウェイト版')
print('  - 銘柄数: 20銘柄（感度分析用）')
print('=' * 80)
print(f'バックテスト期間:  {results_df["date"].min().strftime("%Y/%m/%d")} ~ {results_df["date"].max().strftime("%Y/%m/%d")} ({years:.1f}年)')
print(f'初期資本:          {INITIAL_CAPITAL:>15,.0f} 円')
print(f'最終資本:          {capital:>15,.0f} 円')
print('-' * 65)
print(f'総リターン:        {total_return*100:>13.2f}%')
print(f'年率リターン:      {annual_return*100:>13.2f}%')
print(f'年率ボラティリティ:{annual_vol*100:>13.2f}%')
print('-' * 65)
print(f'シャープレシオ:    {sharpe:>13.2f}')
print(f'ソルティノレシオ:  {sortino:>13.2f}')
print(f'最大ドローダウン:  {max_dd:>13.2f}%')
print(f'カルマーレシオ:    {calmar:>13.2f}')
print('-' * 65)
print(f'勝率:              {win_rate:>13.1f}%')
print(f'プロフィットファクタ:{profit_factor:>11.2f}')
print('=' * 65)
print(f'[ベンチマーク TOPIX]')
print(f'TOPIX 総リターン:  {topix_total*100:>13.2f}%')
print(f'TOPIX 年率リターン:{topix_annual*100:>13.2f}%')
print(f'超過リターン(年率):{alpha:>13.2f}%')
print('=' * 65)

# Annual returns + tax log
results_df['year'] = pd.to_datetime(results_df['date']).dt.year
tax_dict = {row['year']: row for row in annual_tax_log}

print()
print('年次リターン（税引後、年間損益通算）:')
print(f"{'年':>4} | {'戦略(税後)':>9} | {'TOPIX':>7} | {'超過':>7} | {'年税額(万円)':>11} | {'銘柄数':>6}")
print('-' * 62)
for year in sorted(results_df['year'].unique()):
    yr      = results_df[results_df['year'] == year]
    yr_ret  = (np.prod(1 + yr['net_return'].values / 100) - 1) * 100
    t_yr    = topix[topix['Date'].dt.year == year]
    t_ret   = (t_yr['TOPIX'].iloc[-1] / t_yr['TOPIX'].iloc[0] - 1) * 100 if len(t_yr) >= 2 else 0
    excess  = yr_ret - t_ret
    n_s     = yr['n_stocks'].mean()
    tax_yen = tax_dict.get(year, {}).get('tax_yen', 0) / 10000
    sign    = '+' if yr_ret >= 0 else ''
    tsign   = '+' if t_ret  >= 0 else ''
    xsign   = '+' if excess >= 0 else ''
    print(f'{year:>4} | {sign}{yr_ret:>8.2f}% | {tsign}{t_ret:>6.2f}% | {xsign}{excess:>6.2f}% | {tax_yen:>10.1f} | {n_s:>6.0f}')

print()
print('年末税金精算サマリー:')
total_tax = sum(r['tax_yen'] for r in annual_tax_log)
total_pnl = sum(r['pnl_yen'] for r in annual_tax_log)
for r in annual_tax_log:
    net_flag = '損失' if r['pnl_yen'] <= 0 else ''
    print(f"  {r['year']}年: 年間損益={r['pnl_yen']/1e6:+.2f}百万円  税額={r['tax_yen']/10000:.1f}万円 {net_flag}")
print(f'  合計税額: {total_tax/10000:.1f}万円  (実効税率: {total_tax/max(total_pnl,1)*100:.2f}%)')

# Save results
results_df.to_csv('backtest_results_20stocks.csv', index=False, encoding='utf-8-sig')
tax_log_df.to_csv('tax_log_20stocks.csv', index=False, encoding='utf-8-sig')
print()
print('週次結果をCSV保存: backtest_results_20stocks.csv')
print('税金ログをCSV保存: tax_log_20stocks.csv')
