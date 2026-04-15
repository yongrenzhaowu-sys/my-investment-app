"""
年次リバランス（10月）バックテスト - 理論株価×モメンタム複合戦略【修正版】

【重要】ルックアヘッドバイアスを修正したバージョン
- return_6M: 未来のリターン → 過去6ヶ月のリターンに修正
- データ: prediction_scores_corrected.csv を使用

【戦略コンセプト】
1. カスタム成長率を用いて来期の理論株価を計算
2. 現株価との乖離が大きい銘柄（割安）を抽出
3. その中から過去6ヶ月のモメンタムが高い銘柄を購入（修正）

【理論株価の計算】
- 来期予想EPS = 直近EPS × (1 + custom_growth_rate)
- 理論株価 = 来期予想EPS × 業種平均PER
- 乖離率 = (理論株価 - 現株価) / 現株価

【選択ロジック】
1. 乖離率が上位50%（理論株価 > 現株価 = 割安）
2. その中から過去6Mリターンが高い上位20銘柄を選択（修正）
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("年次リバランス（10月）バックテスト - 理論株価×モメンタム複合戦略")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/5] データ読み込み...")

# 価格データ
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()
print(f"価格データ: {len(df_price):,} 行")

# 財務データ
df_fin = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin['disclosed_date'] = pd.to_datetime(df_fin['disclosed_date'])
df_fin = df_fin[df_fin['disclosed_date'] >= '2016-01-01'].copy()

# 年次決算のみ
if 'fiscal_quarter' in df_fin.columns:
    df_fin = df_fin[df_fin['fiscal_quarter'] == 'FY'].copy()

df_fin = df_fin[['disclosed_date', 'code', 'equity', 'net_profit', 'bps', 'eps']].copy()
df_fin['roe'] = (df_fin['net_profit'] / df_fin['equity']) * 100
df_fin = df_fin[
    (df_fin['roe'] > -100) & (df_fin['roe'] < 100) &
    (df_fin['bps'] > 0) & (df_fin['equity'] > 0) &
    (df_fin['eps'] > 0)  # EPSが正の銘柄のみ
].copy()

print(f"財務データ（年次）: {len(df_fin):,} 行")

# 予測スコアデータ（修正版：過去のリターンを使用）
df_scores = pd.read_csv(
    PROJECT_ROOT / 'analyses/20260222_0200_correct_lookahead_bias/prediction_scores_corrected.csv',
    dtype={'code': str},
    low_memory=False
)
df_scores['disclosed_date'] = pd.to_datetime(df_scores['disclosed_date'])
df_scores = df_scores[df_scores['disclosed_date'] >= '2016-01-01'].copy()

# 必要な列のみ抽出
df_scores = df_scores[['disclosed_date', 'code', 'custom_growth_rate', 'return_6M', 'market_cap', 'quarterly_per']].copy()
df_scores = df_scores.dropna(subset=['custom_growth_rate'])

print(f"予測スコアデータ: {len(df_scores):,} 行")

# ================================================================================
# 2. リバランス日の設定（10月1日）
# ================================================================================

print("\n[2/5] リバランス日を設定...")

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
# 3. 財務データとスコアデータの事前処理
# ================================================================================

print("\n[3/5] 財務データとスコアデータの事前処理...")

fin_by_date = {}
scores_by_date = {}

for rdate in rebalance_dates:
    # 財務データ
    available_fin = df_fin[df_fin['disclosed_date'] <= rdate].copy()
    latest_fin = available_fin.sort_values('disclosed_date').groupby('code').tail(1)
    latest_fin = latest_fin.set_index('code')[['bps', 'roe', 'eps']]
    fin_by_date[rdate] = latest_fin

    # スコアデータ
    six_months_ago = rdate - pd.Timedelta(days=180)
    available_scores = df_scores[
        (df_scores['disclosed_date'] <= rdate) &
        (df_scores['disclosed_date'] >= six_months_ago)
    ].copy()

    if len(available_scores) > 0:
        latest_scores = available_scores.sort_values('disclosed_date').groupby('code').tail(1)
        latest_scores = latest_scores.set_index('code')[['custom_growth_rate', 'return_6M', 'market_cap', 'quarterly_per']]
        scores_by_date[rdate] = latest_scores
    else:
        scores_by_date[rdate] = pd.DataFrame()

print("データ事前処理完了")

# ================================================================================
# 4. バックテスト実行（理論株価×モメンタム複合戦略）
# ================================================================================

print("\n[4/5] バックテストを実行（理論株価×モメンタム複合戦略）...")

INITIAL_CAPITAL = 10_000_000
N_STOCKS = 20
TAX_RATE = 0.20315
UNIT = 100

# 現金を明示的に追跡
cash = INITIAL_CAPITAL
portfolio = {}
results = []
annual_realized_pnl = 0
current_year = None

# 最後のリバランス日は除外
for i in range(len(rebalance_dates) - 1):
    start_date = rebalance_dates[i]
    end_date = rebalance_dates[i + 1]

    print(f"  {start_date.date()} -> {end_date.date()}")

    # 暦年が変わったら税金を支払う
    if current_year != start_date.year:
        if current_year is not None and annual_realized_pnl > 0:
            tax = annual_realized_pnl * TAX_RATE

            if tax > cash and len(portfolio) > 0:
                shortage = tax - cash
                print(f"    税金支払いのため株式を一部売却（不足額: {shortage:,.0f}円）")

                sell_for_tax_df = df_price[
                    (df_price['date'] >= start_date) &
                    (df_price['date'] <= start_date + pd.Timedelta(days=5))
                ].copy()

                if len(sell_for_tax_df) > 0:
                    sell_for_tax_prices_df = sell_for_tax_df.sort_values(['code', 'date']).groupby('code').first()
                    sell_for_tax_prices = sell_for_tax_prices_df['adjusted_close']

                    portfolio_values = []
                    for code, position in portfolio.items():
                        if code in sell_for_tax_prices.index and pd.notna(sell_for_tax_prices[code]):
                            value = position['shares'] * sell_for_tax_prices[code]
                            portfolio_values.append((code, value, sell_for_tax_prices[code]))

                    portfolio_values.sort(key=lambda x: x[1])

                    sold_for_tax = 0
                    codes_to_remove = []
                    for code, value, price in portfolio_values:
                        if sold_for_tax >= shortage:
                            break
                        sell_amount = portfolio[code]['shares'] * price
                        sold_for_tax += sell_amount
                        pnl = (price - portfolio[code]['buy_price']) * portfolio[code]['shares']
                        annual_realized_pnl += pnl
                        codes_to_remove.append(code)

                    for code in codes_to_remove:
                        del portfolio[code]

                    cash += sold_for_tax

            cash -= tax
            print(f"    {current_year}年の税金: {tax:,.0f}円（実現損益: {annual_realized_pnl:,.0f}円）")
        annual_realized_pnl = 0
        current_year = start_date.year

    # 既存ポートフォリオを売却
    sell_value = 0
    if len(portfolio) > 0:
        sell_window_df = df_price[
            (df_price['date'] >= start_date) &
            (df_price['date'] <= start_date + pd.Timedelta(days=5))
        ].copy()

        if len(sell_window_df) > 0:
            sell_prices_df = sell_window_df.sort_values(['code', 'date']).groupby('code').first()
            sell_prices = sell_prices_df['adjusted_close']

            for code, position in portfolio.items():
                if code in sell_prices.index and pd.notna(sell_prices[code]):
                    sell_price = sell_prices[code]
                    sell_amount = position['shares'] * sell_price
                    sell_value += sell_amount
                    pnl = (sell_price - position['buy_price']) * position['shares']
                    annual_realized_pnl += pnl

    cash += sell_value
    portfolio = {}

    # 銘柄選定（理論株価×モメンタム複合戦略）
    start_prices_df = df_price[
        (df_price['date'] >= start_date) &
        (df_price['date'] <= start_date + pd.Timedelta(days=5))
    ].copy()

    if len(start_prices_df) == 0:
        print(f"    スキップ: 価格データなし")
        continue

    start_prices_df = start_prices_df.sort_values(['code', 'date']).groupby('code').first()
    prices = start_prices_df['adjusted_close'].dropna()
    fin = fin_by_date[start_date]
    scores = scores_by_date.get(start_date, pd.DataFrame())

    if len(scores) == 0:
        print(f"    スキップ: スコアデータなし")
        continue

    # データをマージ
    merged = pd.DataFrame({
        'adjusted_close': prices,
        'eps': fin['eps'],
        'custom_growth_rate': scores['custom_growth_rate'],
        'return_6M': scores['return_6M'],
        'quarterly_per': scores['quarterly_per']
    }).dropna()

    if len(merged) < N_STOCKS:
        print(f"    スキップ: データ不足（{len(merged)} < {N_STOCKS}）")
        continue

    # 理論株価の計算
    # 来期予想EPS = 直近EPS × (1 + custom_growth_rate)
    merged['next_eps'] = merged['eps'] * (1 + merged['custom_growth_rate'])

    # 理論株価 = 来期予想EPS × 四半期PER（簡易的に使用）
    # より正確には業種平均PERを使うべきだが、データがないため四半期PERを使用
    merged['theoretical_price'] = merged['next_eps'] * merged['quarterly_per']

    # 乖離率 = (理論株価 - 現株価) / 現株価
    merged['divergence'] = (merged['theoretical_price'] - merged['adjusted_close']) / merged['adjusted_close']

    # 異常値を除外（乖離率が-50%～+200%の範囲内）
    merged = merged[(merged['divergence'] > -0.5) & (merged['divergence'] < 2.0)]

    if len(merged) < N_STOCKS:
        print(f"    スキップ: 乖離率フィルタ後データ不足（{len(merged)} < {N_STOCKS}）")
        continue

    # ステップ1: 乖離率が正（理論株価 > 現株価 = 割安）の銘柄を選択
    undervalued = merged[merged['divergence'] > 0].copy()

    if len(undervalued) < N_STOCKS:
        # 割安銘柄が不足している場合は、乖離率上位50%を使用
        divergence_median = merged['divergence'].median()
        undervalued = merged[merged['divergence'] >= divergence_median].copy()

    # ステップ2: その中から6Mリターンが高い上位20銘柄を選択
    selected = undervalued.nlargest(N_STOCKS, 'return_6M')

    print(f"    全体: {len(merged)}銘柄 → 割安: {len(undervalued)}銘柄 → モメンタム上位: {len(selected)}銘柄")
    print(f"    乖離率範囲: {selected['divergence'].min():.2%} ~ {selected['divergence'].max():.2%}")
    print(f"    6Mリターン範囲: {selected['return_6M'].min():.2%} ~ {selected['return_6M'].max():.2%}")

    # 現金を明示的に使って購入
    target_per_stock = cash / len(selected)
    total_invested = 0

    for code in selected.index:
        price = selected.loc[code, 'adjusted_close']
        shares = int(target_per_stock / (price * UNIT)) * UNIT

        if shares > 0:
            invest_amount = shares * price
            if invest_amount <= cash - total_invested:
                total_invested += invest_amount
                portfolio[code] = {'shares': shares, 'buy_price': price}

    cash -= total_invested

    print(f"    投資: {total_invested:,.0f}円, 現金残: {cash:,.0f}円, 銘柄数: {len(portfolio)}")

    # 期末時点での評価
    end_prices_df = df_price[
        (df_price['date'] >= end_date) &
        (df_price['date'] <= end_date + pd.Timedelta(days=5))
    ].copy()

    if len(end_prices_df) > 0:
        end_prices_df = end_prices_df.sort_values(['code', 'date']).groupby('code').first()
        end_prices = end_prices_df['adjusted_close']

        portfolio_value = 0
        valid_stocks = 0

        for code, position in portfolio.items():
            if code in end_prices.index and pd.notna(end_prices[code]):
                end_price = end_prices[code]
                portfolio_value += position['shares'] * end_price
                valid_stocks += 1

        total_value = cash + portfolio_value

        results.append({
            'start_date': start_date,
            'end_date': end_date,
            'cash': cash,
            'portfolio_value': portfolio_value,
            'total_value': total_value,
            'invested': total_invested,
            'n_stocks': len(portfolio),
            'valid_stocks': valid_stocks
        })

# 最終評価
final_eval_date = df_price_pivot.index.max()

# 最終税金
if annual_realized_pnl > 0:
    tax = annual_realized_pnl * TAX_RATE

    if tax > cash and len(portfolio) > 0:
        shortage = tax - cash
        print(f"    最終税金支払いのため株式を一部売却（不足額: {shortage:,.0f}円）")

        final_tax_sell_df = df_price[
            (df_price['date'] >= final_eval_date - pd.Timedelta(days=5)) &
            (df_price['date'] <= final_eval_date)
        ].copy()

        if len(final_tax_sell_df) > 0:
            final_tax_sell_prices_df = final_tax_sell_df.sort_values(['code', 'date']).groupby('code').last()
            final_tax_sell_prices = final_tax_sell_prices_df['adjusted_close']

            portfolio_values = []
            for code, position in portfolio.items():
                if code in final_tax_sell_prices.index and pd.notna(final_tax_sell_prices[code]):
                    value = position['shares'] * final_tax_sell_prices[code]
                    portfolio_values.append((code, value, final_tax_sell_prices[code]))

            portfolio_values.sort(key=lambda x: x[1])

            sold_for_tax = 0
            codes_to_remove = []
            for code, value, price in portfolio_values:
                if sold_for_tax >= shortage:
                    break
                sell_amount = portfolio[code]['shares'] * price
                sold_for_tax += sell_amount
                codes_to_remove.append(code)

            for code in codes_to_remove:
                del portfolio[code]

            cash += sold_for_tax

    cash -= tax
    print(f"    {current_year}年の税金: {tax:,.0f}円（実現損益: {annual_realized_pnl:,.0f}円）")

final_portfolio_value = 0

if len(portfolio) > 0:
    final_prices_df = df_price[
        (df_price['date'] >= final_eval_date - pd.Timedelta(days=5)) &
        (df_price['date'] <= final_eval_date)
    ].copy()

    if len(final_prices_df) > 0:
        final_prices_df = final_prices_df.sort_values(['code', 'date']).groupby('code').last()
        final_prices = final_prices_df['adjusted_close']

        for code, position in portfolio.items():
            if code in final_prices.index and pd.notna(final_prices[code]):
                final_portfolio_value += position['shares'] * final_prices[code]

final_total_value = cash + final_portfolio_value

print(f"\n最終評価日: {final_eval_date.date()}")
print(f"最終現金: {cash:,.0f}円")
print(f"最終株式時価: {final_portfolio_value:,.0f}円")
print(f"最終総資産: {final_total_value:,.0f}円")

# 結果に最終評価を追加
if len(results) > 0:
    results.append({
        'start_date': results[-1]['end_date'],
        'end_date': final_eval_date,
        'cash': cash,
        'portfolio_value': final_portfolio_value,
        'total_value': final_total_value,
        'invested': 0,
        'n_stocks': len(portfolio),
        'valid_stocks': len(portfolio)
    })

# ================================================================================
# 5. パフォーマンス分析
# ================================================================================

print("\n" + "="*80)
print("【理論株価×モメンタム複合戦略結果】")
print("="*80)

if len(results) == 0:
    print("\nエラー: バックテスト結果が生成されませんでした")
else:
    df_results = pd.DataFrame(results)

    # リターン計算
    df_results['return'] = df_results['total_value'].pct_change()
    df_results['cumulative_return'] = (1 + df_results['return']).cumprod() - 1

    # 総リターン
    total_return = (df_results['total_value'].iloc[-1] / INITIAL_CAPITAL - 1)

    # 期間（年）
    years = (df_results['end_date'].iloc[-1] - df_results['start_date'].iloc[0]).days / 365.25

    # 年率リターン
    annual_return = (1 + total_return) ** (1 / years) - 1

    # ボラティリティ
    volatility = df_results['return'].std() * np.sqrt(1)

    # シャープレシオ
    sharpe_ratio = (annual_return - 0.03) / volatility if volatility > 0 else 0

    # 最大ドローダウン
    df_results['peak'] = df_results['total_value'].cummax()
    df_results['drawdown'] = (df_results['total_value'] - df_results['peak']) / df_results['peak']
    max_drawdown = df_results['drawdown'].min()

    # 勝率
    win_rate = (df_results['return'] > 0).sum() / len(df_results['return'].dropna())

    # 平均投資比率
    df_results['investment_ratio'] = df_results['portfolio_value'] / df_results['total_value']
    avg_investment_ratio = df_results['investment_ratio'].mean()

    print(f"\n期間: {df_results['start_date'].iloc[0].date()} ~ {df_results['end_date'].iloc[-1].date()}")
    print(f"リバランス回数: {len(results)-1}回")
    print(f"初期資本: {INITIAL_CAPITAL:,}円")
    print(f"最終資産: {df_results['total_value'].iloc[-1]:,.0f}円")
    print(f"総リターン: {total_return*100:.2f}%")
    print(f"年率リターン: {annual_return*100:.2f}%")
    print(f"ボラティリティ: {volatility*100:.2f}%")
    print(f"シャープレシオ: {sharpe_ratio:.2f}")
    print(f"最大DD: {max_drawdown*100:.2f}%")
    print(f"勝率: {win_rate*100:.1f}%")
    print(f"平均投資比率: {avg_investment_ratio*100:.1f}%")

    # 保存
    output_dir = PROJECT_ROOT / 'analyses' / '20260222_0200_correct_lookahead_bias'
    output_dir.mkdir(exist_ok=True, parents=True)

    df_results.to_csv(output_dir / 'backtest_results_corrected.csv', index=False, encoding='utf-8-sig')

    with open(output_dir / 'theoretical_price_momentum_summary.txt', 'w', encoding='utf-8') as f:
        f.write("理論株価×モメンタム複合戦略\n")
        f.write("="*80 + "\n\n")
        f.write("【戦略詳細】\n")
        f.write("1. カスタム成長率で来期EPS予想\n")
        f.write("2. 理論株価 = 来期EPS × 四半期PER\n")
        f.write("3. 乖離率 = (理論株価 - 現株価) / 現株価\n")
        f.write("4. 割安銘柄（乖離率 > 0）を抽出\n")
        f.write("5. その中から6Mリターン上位20銘柄を選択\n\n")
        f.write("="*80 + "\n\n")
        f.write(f"期間: {df_results['start_date'].iloc[0].date()} ~ {df_results['end_date'].iloc[-1].date()}\n")
        f.write(f"リバランス回数: {len(results)-1}回\n")
        f.write(f"初期資本: {INITIAL_CAPITAL:,}円\n")
        f.write(f"最終資産: {df_results['total_value'].iloc[-1]:,.0f}円\n\n")
        f.write(f"年率リターン: {annual_return*100:.2f}%\n")
        f.write(f"シャープレシオ: {sharpe_ratio:.2f}\n")
        f.write(f"最大DD: {max_drawdown*100:.2f}%\n")
        f.write(f"勝率: {win_rate*100:.1f}%\n")
        f.write(f"平均投資比率: {avg_investment_ratio*100:.1f}%\n")

    print(f"\n保存先: {output_dir}")

    print("\n" + "="*80)
    print("比較:")
    print(f"  ベースライン（バリュー）:    年率+25.61%")
    print(f"  Simple 6Mモメンタム:         年率+24.94%")
    print(f"  理論株価×モメンタム:         年率{annual_return*100:+.2f}%")

    if annual_return > 0.2561:
        print(f"  → ✅ 理論株価版がベースラインを上回りました！（+{annual_return*100 - 25.61:.2f}%pt）")
    elif annual_return > 0.2494:
        print(f"  → ✅ 理論株価版が6M版を上回りました（+{annual_return*100 - 24.94:.2f}%pt）")
    else:
        print(f"  → 理論株価版はベースラインを下回りました（{annual_return*100 - 25.61:.2f}%pt）")
    print("="*80)

print("\n完了！")
