"""
複数戦略 × 複数リバランス頻度の総合比較

戦略：
1. ベースライン（低PBR×高ROE）
2. + 高出来高
3. + 低PER
4. + 高PEG的スコア
5. + 高成長率
6. + 高益利回り
7. 複合戦略

リバランス頻度：
- 年次（10月）
- 月次（月初）
- 週次（月曜）
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("複数戦略 × 複数リバランス頻度の総合比較")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/4] データ読み込み...")

# 価格データ
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()
print(f"価格データ: {len(df_price):,} 行")

# 財務データ（年次）
df_fin = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin['disclosed_date'] = pd.to_datetime(df_fin['disclosed_date'])
df_fin = df_fin[df_fin['disclosed_date'] >= '2016-01-01'].copy()

if 'fiscal_quarter' in df_fin.columns:
    df_fin = df_fin[df_fin['fiscal_quarter'] == 'FY'].copy()

df_fin = df_fin[['disclosed_date', 'code', 'equity', 'net_profit', 'bps']].copy()
df_fin['roe'] = (df_fin['net_profit'] / df_fin['equity']) * 100
df_fin = df_fin[
    (df_fin['roe'] > -100) & (df_fin['roe'] < 100) &
    (df_fin['bps'] > 0) & (df_fin['equity'] > 0)
].copy()

print(f"財務データ（年次）: {len(df_fin):,} 行")

# 予測スコアデータ
scores_path = PROJECT_ROOT / 'analyses/growth_yield_prediction/prediction_scores.csv'
if scores_path.exists():
    df_scores = pd.read_csv(scores_path, dtype={'code': str})
    df_scores['disclosed_date'] = pd.to_datetime(df_scores['disclosed_date'])

    if 'peg_score' not in df_scores.columns:
        df_scores['peg_score'] = (df_scores['custom_growth_rate'] * 100) / df_scores['quarterly_per']

    print(f"予測スコアデータ: {len(df_scores):,} 行")
    has_scores = True
else:
    print("予測スコアデータなし（ベースラインのみ）")
    has_scores = False

# 出来高データ準備
df_price_vol = df_price[['date', 'code', 'volume']].copy()
df_price_vol = df_price_vol.sort_values(['code', 'date'])
df_price_vol['volume_ma20'] = df_price_vol.groupby('code')['volume'].transform(
    lambda x: x.rolling(window=20, min_periods=10).mean()
)

# ================================================================================
# 2. 銘柄選定戦略の定義
# ================================================================================

print("\n[2/4] 戦略を定義...")

def select_baseline(merged, n_stocks=20):
    """ベースライン: 低PBR × 高ROE"""
    pbr_q1 = merged['pbr'].quantile(0.25)
    roe_q3 = merged['roe'].quantile(0.75)
    candidates = merged[(merged['pbr'] <= pbr_q1) & (merged['roe'] >= roe_q3)]

    if len(candidates) < n_stocks:
        candidates = merged.nsmallest(n_stocks, 'pbr')

    return candidates.nsmallest(n_stocks, 'pbr')

def select_with_volume(merged, n_stocks=20):
    """+ 高出来高"""
    if 'volume_ma20' not in merged.columns or merged['volume_ma20'].isna().all():
        return select_baseline(merged, n_stocks)

    vol_median = merged['volume_ma20'].median()
    high_vol = merged[merged['volume_ma20'] >= vol_median]

    if len(high_vol) < n_stocks:
        return select_baseline(merged, n_stocks)

    return select_baseline(high_vol, n_stocks)

def select_with_low_per(merged, n_stocks=20):
    """+ 低PER"""
    if 'quarterly_per' not in merged.columns:
        return select_baseline(merged, n_stocks)

    per_valid = merged[merged['quarterly_per'] > 0]
    if len(per_valid) < n_stocks:
        return select_baseline(merged, n_stocks)

    per_q1 = per_valid['quarterly_per'].quantile(0.25)
    low_per = per_valid[per_valid['quarterly_per'] <= per_q1]

    if len(low_per) < n_stocks:
        return select_baseline(merged, n_stocks)

    return select_baseline(low_per, n_stocks)

def select_with_high_peg(merged, n_stocks=20):
    """+ 高PEG的スコア"""
    if 'peg_score' not in merged.columns:
        return select_baseline(merged, n_stocks)

    peg_valid = merged[merged['peg_score'].notna() & (merged['peg_score'] > 0)]
    if len(peg_valid) < n_stocks:
        return select_baseline(merged, n_stocks)

    peg_q3 = peg_valid['peg_score'].quantile(0.75)
    high_peg = peg_valid[peg_valid['peg_score'] >= peg_q3]

    if len(high_peg) < n_stocks:
        return select_baseline(merged, n_stocks)

    return select_baseline(high_peg, n_stocks)

def select_with_growth(merged, n_stocks=20):
    """+ 高成長率"""
    if 'custom_growth_rate' not in merged.columns:
        return select_baseline(merged, n_stocks)

    growth_valid = merged[merged['custom_growth_rate'] > 0]
    if len(growth_valid) < n_stocks:
        return select_baseline(merged, n_stocks)

    growth_q3 = growth_valid['custom_growth_rate'].quantile(0.75)
    high_growth = growth_valid[growth_valid['custom_growth_rate'] >= growth_q3]

    if len(high_growth) < n_stocks:
        return select_baseline(merged, n_stocks)

    return select_baseline(high_growth, n_stocks)

def select_with_yield(merged, n_stocks=20):
    """+ 高益利回り"""
    if 'earnings_yield' not in merged.columns:
        return select_baseline(merged, n_stocks)

    yield_valid = merged[merged['earnings_yield'] > 0]
    if len(yield_valid) < n_stocks:
        return select_baseline(merged, n_stocks)

    yield_q3 = yield_valid['earnings_yield'].quantile(0.75)
    high_yield = yield_valid[yield_valid['earnings_yield'] >= yield_q3]

    if len(high_yield) < n_stocks:
        return select_baseline(merged, n_stocks)

    return select_baseline(high_yield, n_stocks)

def select_composite(merged, n_stocks=20):
    """複合戦略"""
    filtered = merged.copy()

    # 出来高フィルタ
    if 'volume_ma20' in filtered.columns and not filtered['volume_ma20'].isna().all():
        vol_median = filtered['volume_ma20'].median()
        filtered = filtered[filtered['volume_ma20'] >= vol_median]
        if len(filtered) < n_stocks:
            return select_baseline(merged, n_stocks)

    # 低PERフィルタ
    if 'quarterly_per' in filtered.columns:
        per_valid = filtered[filtered['quarterly_per'] > 0]
        if len(per_valid) >= n_stocks:
            per_q2 = per_valid['quarterly_per'].quantile(0.50)
            filtered = per_valid[per_valid['quarterly_per'] <= per_q2]
            if len(filtered) < n_stocks:
                return select_baseline(merged, n_stocks)

    # 高成長フィルタ
    if 'custom_growth_rate' in filtered.columns:
        growth_valid = filtered[filtered['custom_growth_rate'] > 0]
        if len(growth_valid) >= n_stocks:
            growth_q2 = growth_valid['custom_growth_rate'].quantile(0.50)
            filtered = growth_valid[growth_valid['custom_growth_rate'] >= growth_q2]
            if len(filtered) < n_stocks:
                return select_baseline(merged, n_stocks)

    return select_baseline(filtered, n_stocks)

strategies = {
    'ベースライン': select_baseline,
    '+ 高出来高': select_with_volume,
    '+ 低PER': select_with_low_per,
    '+ 高PEG': select_with_high_peg,
    '+ 高成長': select_with_growth,
    '+ 高益利回り': select_with_yield,
    '複合戦略': select_composite,
}

print(f"戦略数: {len(strategies)}")

# ================================================================================
# 3. バックテスト関数
# ================================================================================

print("\n[3/4] バックテスト関数を準備...")

INITIAL_CAPITAL = 10_000_000
N_STOCKS = 20
TAX_RATE = 0.20315
UNIT = 100

def run_backtest(rebalance_dates, select_func, freq_name='年次'):
    """バックテスト実行"""

    cash = INITIAL_CAPITAL
    portfolio = {}
    results = []
    annual_pnl = 0
    current_year = None

    # 財務データ準備
    fin_by_date = {}
    for rdate in rebalance_dates:
        available = df_fin[df_fin['disclosed_date'] <= rdate].copy()
        latest = available.sort_values('disclosed_date').groupby('code').tail(1)
        fin_by_date[rdate] = latest.set_index('code')[['bps', 'roe']]

    # スコアデータ準備
    if has_scores:
        scores_by_date = {}
        for rdate in rebalance_dates:
            available = df_scores[df_scores['disclosed_date'] <= rdate].copy()
            latest = available.sort_values('disclosed_date').groupby('code').tail(1)
            scores_by_date[rdate] = latest.set_index('code')[[
                'quarterly_per', 'custom_growth_rate', 'peg_score', 'earnings_yield'
            ]]

    for i in range(len(rebalance_dates) - 1):
        start_date = rebalance_dates[i]
        end_date = rebalance_dates[i + 1]

        # 税金処理
        if current_year != start_date.year:
            if current_year is not None and annual_pnl > 0:
                tax = annual_pnl * TAX_RATE
                # 現金不足時は税金をスキップ（簡略化）
                if tax <= cash:
                    cash -= tax
            annual_pnl = 0
            current_year = start_date.year

        # 売却
        sell_value = 0
        if len(portfolio) > 0:
            sell_df = df_price[
                (df_price['date'] >= start_date) &
                (df_price['date'] <= start_date + pd.Timedelta(days=5))
            ].copy()

            if len(sell_df) > 0:
                sell_prices = sell_df.sort_values(['code', 'date']).groupby('code').first()['adjusted_close']

                for code, pos in portfolio.items():
                    if code in sell_prices.index and pd.notna(sell_prices[code]):
                        sell_value += pos['shares'] * sell_prices[code]
                        annual_pnl += (sell_prices[code] - pos['buy_price']) * pos['shares']

        cash += sell_value
        portfolio = {}

        # 銘柄選定
        start_prices_df = df_price[
            (df_price['date'] >= start_date) &
            (df_price['date'] <= start_date + pd.Timedelta(days=5))
        ].copy()

        if len(start_prices_df) == 0:
            continue

        prices = start_prices_df.sort_values(['code', 'date']).groupby('code').first()['adjusted_close'].dropna()
        fin = fin_by_date.get(start_date, pd.DataFrame())

        merged = pd.DataFrame({'adjusted_close': prices, 'bps': fin['bps'], 'roe': fin['roe']}).dropna()

        if len(merged) < N_STOCKS:
            continue

        merged['pbr'] = merged['adjusted_close'] / merged['bps']
        merged = merged[(merged['pbr'] > 0) & (merged['pbr'] < 50)]

        if len(merged) < N_STOCKS:
            continue

        # スコア追加
        if has_scores and start_date in scores_by_date:
            for col in scores_by_date[start_date].columns:
                merged[col] = scores_by_date[start_date][col]

        # 出来高追加
        vol_window = df_price_vol[
            (df_price_vol['date'] >= start_date - pd.Timedelta(days=30)) &
            (df_price_vol['date'] <= start_date)
        ].copy()
        if len(vol_window) > 0:
            vol_latest = vol_window.sort_values(['code', 'date']).groupby('code').last()['volume_ma20']
            merged['volume_ma20'] = vol_latest

        # 戦略適用
        selected = select_func(merged, N_STOCKS)

        # 購入
        target_per_stock = cash / len(selected)
        total_invested = 0

        for code in selected.index:
            price = selected.loc[code, 'adjusted_close']
            shares = int(target_per_stock / (price * UNIT)) * UNIT

            if shares > 0 and total_invested + shares * price <= cash:
                total_invested += shares * price
                portfolio[code] = {'shares': shares, 'buy_price': price}

        cash -= total_invested

        # 期末評価
        end_prices_df = df_price[
            (df_price['date'] >= end_date) &
            (df_price['date'] <= end_date + pd.Timedelta(days=5))
        ].copy()

        if len(end_prices_df) > 0:
            end_prices = end_prices_df.sort_values(['code', 'date']).groupby('code').first()['adjusted_close']

            portfolio_value = sum(
                pos['shares'] * end_prices[code]
                for code, pos in portfolio.items()
                if code in end_prices.index and pd.notna(end_prices[code])
            )

            results.append({
                'date': end_date,
                'total_value': cash + portfolio_value
            })

    if len(results) == 0:
        return None

    df_result = pd.DataFrame(results)
    df_result['return'] = df_result['total_value'].pct_change()

    total_return = (df_result['total_value'].iloc[-1] / INITIAL_CAPITAL - 1)
    years = (df_result['date'].iloc[-1] - df_result['date'].iloc[0]).days / 365.25
    annual_return = (1 + total_return) ** (1 / years) - 1

    volatility = df_result['return'].std() * np.sqrt(252 / len(df_result) * years)
    sharpe = (annual_return - 0.03) / volatility if volatility > 0 else 0

    df_result['peak'] = df_result['total_value'].cummax()
    df_result['dd'] = (df_result['total_value'] - df_result['peak']) / df_result['peak']
    max_dd = df_result['dd'].min()

    return {
        'annual_return': annual_return,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'final_value': df_result['total_value'].iloc[-1],
        'rebalances': len(results)
    }

# ================================================================================
# 4. 全組み合わせ実行
# ================================================================================

print("\n[4/4] 全組み合わせを実行中...")

# リバランス日生成
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

# 年次（10月）
annual_dates = []
for year in range(2016, 2026):
    dates = df_price_pivot.index[df_price_pivot.index >= pd.Timestamp(f'{year}-10-01')]
    if len(dates) > 0:
        annual_dates.append(dates[0])

# 月次（月初）
monthly_dates = []
for year in range(2016, 2026):
    for month in range(1, 13):
        dates = df_price_pivot.index[df_price_pivot.index >= pd.Timestamp(f'{year}-{month:02d}-01')]
        if len(dates) > 0:
            monthly_dates.append(dates[0])
monthly_dates = sorted(list(set(monthly_dates)))

# 週次（月曜）
weekly_dates = []
all_dates = df_price_pivot.index[(df_price_pivot.index >= '2016-01-01') & (df_price_pivot.index <= '2025-12-31')]
for date in all_dates:
    if date.dayofweek == 0:  # 月曜日
        weekly_dates.append(date)

rebalance_configs = {
    '年次': annual_dates,
    '月次': monthly_dates[:len(monthly_dates)//2],  # 高速化のため半分
    '週次': weekly_dates[:len(weekly_dates)//4],   # 高速化のため1/4
}

print(f"年次: {len(annual_dates)}回")
print(f"月次: {len(monthly_dates[:len(monthly_dates)//2])}回")
print(f"週次: {len(weekly_dates[:len(weekly_dates)//4])}回")

all_results = {}

for freq_name, rebalance_dates in rebalance_configs.items():
    print(f"\n{freq_name}リバランス:")

    for idx, (strategy_name, select_func) in enumerate(strategies.items(), 1):
        print(f"  [{idx}/{len(strategies)}] {strategy_name}...", end=' ', flush=True)
        result = run_backtest(rebalance_dates, select_func, freq_name)

        if result:
            key = f"{freq_name}_{strategy_name}"
            all_results[key] = {
                'freq': freq_name,
                'strategy': strategy_name,
                **result
            }
            print(f"年率{result['annual_return']*100:+.2f}%")
        else:
            print("スキップ")

# ================================================================================
# 5. 結果出力
# ================================================================================

print("\n" + "="*80)
print("【総合比較結果】")
print("="*80)

df_summary = pd.DataFrame(list(all_results.values()))
df_summary_sorted = df_summary.sort_values('annual_return', ascending=False)

print(f"\n{'順位':<4} {'頻度':<6} {'戦略':<20} {'年率':<10} {'シャープ':<8} {'MDD':<10} {'最終資産'}")
print("-"*85)

for rank, row in df_summary_sorted.head(15).iterrows():
    print(f"{rank+1:<4} {row['freq']:<6} {row['strategy']:<20} {row['annual_return']*100:>6.2f}%  "
          f"{row['sharpe']:>6.2f}  {row['max_dd']*100:>7.2f}%  ¥{row['final_value']:>13,.0f}")

# 保存
output_dir = PROJECT_ROOT / 'analyses' / '20260221_1500_annual_backtest_improved'
df_summary.to_csv(output_dir / 'multi_strategies_comparison.csv', index=False, encoding='utf-8-sig')

print(f"\n保存先: {output_dir}/multi_strategies_comparison.csv")

# ベスト戦略
best = df_summary_sorted.iloc[0]
print("\n" + "="*80)
print("【最強の組み合わせ】")
print("="*80)
print(f"  頻度: {best['freq']}")
print(f"  戦略: {best['strategy']}")
print(f"  年率リターン: {best['annual_return']*100:.2f}%")
print(f"  シャープレシオ: {best['sharpe']:.2f}")
print(f"  最大DD: {best['max_dd']*100:.2f}%")
print(f"  リバランス回数: {best['rebalances']}回")
print(f"  改善版ベースライン（+25.61%）比: {(best['annual_return']-0.2561)*100:+.2f}%pt")
print("="*80)

print("\n完了！")
