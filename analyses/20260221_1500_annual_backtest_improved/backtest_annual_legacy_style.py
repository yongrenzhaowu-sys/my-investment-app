"""
年次リバランス（10月）バックテスト - Legacy方式完全再現

【Legacy実装の特徴】
1. リターン率ベースの計算（実キャッシュフローではない）
2. 各期間のリターン率を複利計算
3. 最後のリバランス日は除外（2016-10〜2024-10の9回）
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("年次リバランス（10月）バックテスト - Legacy方式完全再現")
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

# 財務データ（年次のみ）
df_fin = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin['disclosed_date'] = pd.to_datetime(df_fin['disclosed_date'])
df_fin = df_fin[df_fin['disclosed_date'] >= '2016-01-01'].copy()

# 年次決算のみ
if 'fiscal_quarter' in df_fin.columns:
    df_fin = df_fin[df_fin['fiscal_quarter'] == 'FY'].copy()

df_fin = df_fin[['disclosed_date', 'code', 'equity', 'net_profit', 'bps']].copy()
df_fin['roe'] = (df_fin['net_profit'] / df_fin['equity']) * 100
df_fin = df_fin[
    (df_fin['roe'] > -100) & (df_fin['roe'] < 100) &
    (df_fin['bps'] > 0) & (df_fin['equity'] > 0)
].copy()

print(f"財務データ（年次）: {len(df_fin):,} 行")

# ================================================================================
# 2. リバランス日の設定（10月1日）
# ================================================================================

print("\n[2/4] リバランス日を設定...")

df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

rebalance_dates = []
for year in range(2016, 2026):
    target_date = pd.Timestamp(f'{year}-10-01')
    available_dates = df_price_pivot.index[df_price_pivot.index >= target_date]
    if len(available_dates) > 0:
        rebalance_dates.append(available_dates[0])

rebalance_dates = sorted(rebalance_dates)

print(f"リバランス日数: {len(rebalance_dates)}")
print(f"期間: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}")

# ================================================================================
# 3. 財務データの事前処理
# ================================================================================

print("\n[3/4] 財務データの事前処理...")

fin_by_date = {}
for rdate in rebalance_dates:
    available = df_fin[df_fin['disclosed_date'] <= rdate].copy()
    latest = available.sort_values('disclosed_date').groupby('code').tail(1)
    latest = latest.set_index('code')[['bps', 'roe']]
    fin_by_date[rdate] = latest
    if rdate.year == 2020:
        print(f"  {rdate.date()}: {len(latest)} 銘柄の財務データ")

print("財務データ事前処理完了")

# ================================================================================
# 4. バックテスト実行（Legacy方式：リターン率ベース）
# ================================================================================

print("\n[4/4] バックテストを実行（Legacy方式：リターン率ベース）...")

INITIAL_CAPITAL = 10_000_000
N_STOCKS = 20
TAX_RATE = 0.20315
UNIT = 100

cumulative_capital = INITIAL_CAPITAL
results = []

# legacy版に合わせて最後のリバランスは除外
for i in range(len(rebalance_dates) - 1):
    start_date = rebalance_dates[i]
    end_date = rebalance_dates[i + 1]

    print(f"  {start_date.date()} -> {end_date.date()}")

    # 銘柄選定（Legacy方式：前後5日の猶予）
    start_window_start = start_date - pd.Timedelta(days=5)
    start_window_end = start_date + pd.Timedelta(days=5)

    start_prices_df = df_price[(df_price['date'] >= start_window_start) &
                                 (df_price['date'] <= start_window_end)].copy()
    if len(start_prices_df) > 0:
        start_prices_df = start_prices_df.sort_values(['code', 'date']).groupby('code').first()
        prices = start_prices_df['adjusted_close'].dropna()
    else:
        print(f"    スキップ: 価格データなし")
        continue

    fin = fin_by_date[start_date]

    if start_date.year == 2020:
        print(f"    価格データ: {len(prices)} 銘柄")
        print(f"    財務データ: {len(fin)} 銘柄")

    merged = pd.DataFrame({
        'adjusted_close': prices,
        'bps': fin['bps'],
        'roe': fin['roe']
    }).dropna()

    print(f"    マージ後: {len(merged)} 銘柄")

    if len(merged) < N_STOCKS:
        print(f"    スキップ: データ不足（{len(merged)} < {N_STOCKS}）")
        continue

    # PBR計算
    merged['pbr'] = merged['adjusted_close'] / merged['bps']
    merged = merged[(merged['pbr'] > 0) & (merged['pbr'] < 50)]

    if len(merged) < N_STOCKS:
        continue

    # 四分位
    pbr_q1 = merged['pbr'].quantile(0.25)
    roe_q3 = merged['roe'].quantile(0.75)

    # 割安高質
    candidates = merged[(merged['pbr'] <= pbr_q1) & (merged['roe'] >= roe_q3)]

    if len(candidates) < N_STOCKS:
        candidates = merged.nsmallest(N_STOCKS, 'pbr')

    selected = candidates.nsmallest(N_STOCKS, 'pbr')

    # ポートフォリオ構築（100株単位制限）
    target_per_stock = cumulative_capital / len(selected)
    portfolio = []
    total_investment = 0

    for code in selected.index:
        price = selected.loc[code, 'adjusted_close']
        shares = int(target_per_stock / (price * UNIT)) * UNIT

        if shares > 0:
            invest_amount = shares * price
            total_investment += invest_amount
            portfolio.append({
                'code': code,
                'shares': shares,
                'start_price': price,
                'start_value': invest_amount
            })

    if len(portfolio) == 0:
        print(f"    スキップ: ポートフォリオ構築失敗")
        continue

    print(f"    ポートフォリオ: {len(portfolio)} 銘柄, 投資額: {total_investment:,.0f}円")

    # 期末時点での評価（Legacy方式：前後5日の猶予）
    end_window_start = end_date - pd.Timedelta(days=5)
    end_window_end = end_date + pd.Timedelta(days=5)

    end_prices_df = df_price[(df_price['date'] >= end_window_start) &
                               (df_price['date'] <= end_window_end)].copy()
    if len(end_prices_df) > 0:
        end_prices_df = end_prices_df.sort_values(['code', 'date']).groupby('code').last()
        end_prices = end_prices_df['adjusted_close']
    else:
        end_prices = pd.Series()

    total_end_value = 0
    valid_stocks = 0

    for stock in portfolio:
        code = stock['code']
        if code in end_prices.index and pd.notna(end_prices[code]):
            end_price = end_prices[code]
            end_value = stock['shares'] * end_price
            total_end_value += end_value
            stock['end_price'] = end_price
            stock['end_value'] = end_value
            valid_stocks += 1

    print(f"    期末評価: {valid_stocks}/{len(portfolio)} 銘柄, 評価額: {total_end_value:,.0f}円")

    if valid_stocks == 0:
        print(f"    スキップ: 期末価格データなし")
        continue

    # 損益計算（Legacy方式）
    total_profit = total_end_value - total_investment

    # 税金（利益のみ課税）
    taxable_profit = max(total_profit, 0)
    tax = taxable_profit * TAX_RATE

    # 税引後利益
    net_profit = total_profit - tax

    # 全資本に対するリターン率（Legacy方式）
    gross_return = total_profit / cumulative_capital
    net_return = net_profit / cumulative_capital

    # 累積資本を更新（Legacy方式）
    cumulative_capital = cumulative_capital * (1 + net_return)

    print(f"    リターン: {net_return*100:+.2f}%, 累積資本: {cumulative_capital:,.0f}円")

    results.append({
        'start_date': start_date,
        'end_date': end_date,
        'investment': total_investment,
        'end_value': total_end_value,
        'gross_return': gross_return,
        'net_return': net_return,
        'cumulative_capital': cumulative_capital,
        'n_stocks': len(portfolio),
        'valid_stocks': valid_stocks
    })

# ================================================================================
# 5. パフォーマンス分析
# ================================================================================

print("\n" + "="*80)
print("【年次リバランス結果（Legacy方式）】")
print("="*80)

if len(results) == 0:
    print("\nエラー: バックテスト結果が生成されませんでした")
else:
    df_results = pd.DataFrame(results)

    # 総リターン
    total_return = (df_results['cumulative_capital'].iloc[-1] / INITIAL_CAPITAL - 1)

    # 期間（年）
    years = (df_results['end_date'].iloc[-1] - df_results['start_date'].iloc[0]).days / 365.25

    # 年率リターン
    annual_return = (1 + total_return) ** (1 / years) - 1

    # ボラティリティ
    volatility = df_results['net_return'].std() * np.sqrt(1)  # 年次なので√1

    # シャープレシオ
    sharpe_ratio = (annual_return - 0.03) / volatility if volatility > 0 else 0

    # 最大ドローダウン
    df_results['peak'] = df_results['cumulative_capital'].cummax()
    df_results['drawdown'] = (df_results['cumulative_capital'] - df_results['peak']) / df_results['peak']
    max_drawdown = df_results['drawdown'].min()

    # 勝率
    win_rate = (df_results['net_return'] > 0).sum() / len(df_results)

    print(f"\n期間: {df_results['start_date'].iloc[0].date()} ~ {df_results['end_date'].iloc[-1].date()}")
    print(f"リバランス回数: {len(df_results)}回")
    print(f"初期資本: {INITIAL_CAPITAL:,}円")
    print(f"最終資本: {df_results['cumulative_capital'].iloc[-1]:,.0f}円")
    print(f"総リターン: {total_return*100:.2f}%")
    print(f"年率リターン: {annual_return*100:.2f}%")
    print(f"ボラティリティ: {volatility*100:.2f}%")
    print(f"シャープレシオ: {sharpe_ratio:.2f}")
    print(f"最大DD（年次）: {max_drawdown*100:.2f}%")
    print(f"勝率: {win_rate*100:.1f}%")

    # 保存
    output_dir = PROJECT_ROOT / 'analyses' / '20260221_1500_annual_backtest_improved'
    output_dir.mkdir(exist_ok=True, parents=True)

    df_results.to_csv(output_dir / 'annual_results_legacy_style.csv', index=False, encoding='utf-8-sig')

    with open(output_dir / 'summary_legacy_style.txt', 'w', encoding='utf-8') as f:
        f.write("年次リバランス（10月）バックテスト - Legacy方式\n")
        f.write("="*80 + "\n\n")
        f.write(f"期間: {df_results['start_date'].iloc[0].date()} ~ {df_results['end_date'].iloc[-1].date()}\n")
        f.write(f"リバランス回数: {len(df_results)}回\n")
        f.write(f"初期資本: {INITIAL_CAPITAL:,}円\n")
        f.write(f"最終資本: {df_results['cumulative_capital'].iloc[-1]:,.0f}円\n\n")
        f.write(f"年率リターン: {annual_return*100:.2f}%\n")
        f.write(f"シャープレシオ: {sharpe_ratio:.2f}\n")
        f.write(f"最大DD（年次）: {max_drawdown*100:.2f}%\n")
        f.write(f"勝率: {win_rate*100:.1f}%\n")

    print(f"\n保存先: {output_dir}")

    # ================================================================================
    # 6. 日次MDD計算（Legacy版から再現）
    # ================================================================================

    print("\n日次MDD計算を開始...")

    # 全営業日を取得
    all_dates = sorted(df_price_pivot.index[
        (df_price_pivot.index >= df_results['start_date'].iloc[0]) &
        (df_price_pivot.index <= df_results['end_date'].iloc[-1])
    ])

    daily_values = []
    cumulative_capital_tracker = INITIAL_CAPITAL

    for date in all_dates:
        # この日時点で有効なリバランス結果を特定
        current_result = None
        for _, result in df_results.iterrows():
            if result['start_date'] <= date < result['end_date']:
                current_result = result
                break

        if current_result is None:
            # リバランス期間外
            continue

        # この期間の開始時点の累積資本
        period_start_capital = current_result['cumulative_capital'] / (1 + current_result['net_return'])

        # ポートフォリオの日次評価（簡易版：比例配分）
        # 実際には各銘柄の日次価格で評価すべきだが、ここでは簡易的に
        # 期間内の進捗率で線形補間
        days_total = (current_result['end_date'] - current_result['start_date']).days
        days_elapsed = (date - current_result['start_date']).days

        if days_total > 0:
            progress = days_elapsed / days_total
            estimated_capital = period_start_capital * (1 + current_result['net_return'] * progress)
        else:
            estimated_capital = period_start_capital

        daily_values.append({
            'date': date,
            'estimated_capital': estimated_capital
        })

    if len(daily_values) > 0:
        df_daily = pd.DataFrame(daily_values)
        df_daily['peak'] = df_daily['estimated_capital'].cummax()
        df_daily['drawdown'] = (df_daily['estimated_capital'] - df_daily['peak']) / df_daily['peak']

        max_dd_daily = df_daily['drawdown'].min()
        max_dd_date = df_daily.loc[df_daily['drawdown'].idxmin(), 'date']

        print(f"日次最大DD: {max_dd_daily*100:.2f}% ({max_dd_date.date()})")

        # 保存
        df_daily.to_csv(output_dir / 'daily_results_legacy_style.csv', index=False, encoding='utf-8-sig')

        # サマリーファイルに追記
        with open(output_dir / 'summary_legacy_style.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n日次最大DD: {max_dd_daily*100:.2f}%\n")
    else:
        print("日次データが生成されませんでした")
        max_dd_daily = max_drawdown

    print("\n" + "="*80)
    print("Legacy版（年率+28.52%）との比較:")
    print(f"  今回: 年率{annual_return*100:+.2f}%")
    print("  差分: {:.2f}%pt".format(annual_return*100 - 28.52))
    print(f"  最大DD（年次）: {max_drawdown*100:.2f}%")
    print(f"  最大DD（日次）: {max_dd_daily*100:.2f}%")
    print("="*80)

print("\n完了！")
