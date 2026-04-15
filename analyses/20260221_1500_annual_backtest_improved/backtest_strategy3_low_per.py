"""
年次リバランス（10月）バックテスト - 戦略3: ベースライン + 低PER

【ベースラインからの変更点】
- 四半期PER（低い方が良い）を追加フィルタとして使用
- PERが下位25%の銘柄のみを対象に、ベースライン選択（低PBR × 高ROE）を適用
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("年次リバランス（10月）バックテスト - 戦略3: ベースライン + 低PER")
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

# 【戦略3追加】予測スコアデータ（四半期PERを含む）
df_scores = pd.read_csv(
    PROJECT_ROOT / 'analyses/growth_yield_prediction/prediction_scores.csv',
    dtype={'code': str},
    low_memory=False
)
df_scores['disclosed_date'] = pd.to_datetime(df_scores['disclosed_date'])
df_scores = df_scores[df_scores['disclosed_date'] >= '2016-01-01'].copy()

# 必要な列のみ抽出
df_scores = df_scores[['disclosed_date', 'code', 'quarterly_per']].copy()

# PERが正の値のみ（負のPERは無効）
df_scores = df_scores[df_scores['quarterly_per'] > 0].copy()

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
# 3. 財務データの事前処理
# ================================================================================

print("\n[3/5] 財務データの事前処理...")

fin_by_date = {}
for rdate in rebalance_dates:
    available = df_fin[df_fin['disclosed_date'] <= rdate].copy()
    latest = available.sort_values('disclosed_date').groupby('code').tail(1)
    latest = latest.set_index('code')[['bps', 'roe']]
    fin_by_date[rdate] = latest

print("財務データ事前処理完了")

# ================================================================================
# 3b. 【戦略3追加】予測スコアデータの事前処理
# ================================================================================

print("\n[3b/5] 予測スコアデータの事前処理...")

scores_by_date = {}
for rdate in rebalance_dates:
    available = df_scores[df_scores['disclosed_date'] <= rdate].copy()
    latest = available.sort_values('disclosed_date').groupby('code').tail(1)
    latest = latest.set_index('code')[['quarterly_per']]
    scores_by_date[rdate] = latest

print("予測スコアデータ事前処理完了")

# ================================================================================
# 4. バックテスト実行（戦略3: ベースライン + 低PER）
# ================================================================================

print("\n[4/5] バックテストを実行（戦略3: ベースライン + 低PER）...")

INITIAL_CAPITAL = 10_000_000
N_STOCKS = 20
TAX_RATE = 0.20315
UNIT = 100

# 現金を明示的に追跡
cash = INITIAL_CAPITAL
portfolio = {}  # {code: {'shares': int, 'buy_price': float}}
results = []
annual_realized_pnl = 0  # 暦年の実現損益
current_year = None

# 最後のリバランス日は除外（保有期間確保のため）
for i in range(len(rebalance_dates) - 1):
    start_date = rebalance_dates[i]
    end_date = rebalance_dates[i + 1]

    print(f"  {start_date.date()} -> {end_date.date()}")

    # 暦年が変わったら税金を支払う
    if current_year != start_date.year:
        if current_year is not None and annual_realized_pnl > 0:
            tax = annual_realized_pnl * TAX_RATE

            # 現金不足の場合は株式を売却して税金を支払う
            if tax > cash and len(portfolio) > 0:
                shortage = tax - cash
                print(f"    税金支払いのため株式を一部売却（不足額: {shortage:,.0f}円）")

                # 売却価格取得
                sell_for_tax_df = df_price[
                    (df_price['date'] >= start_date) &
                    (df_price['date'] <= start_date + pd.Timedelta(days=5))
                ].copy()

                if len(sell_for_tax_df) > 0:
                    sell_for_tax_prices_df = sell_for_tax_df.sort_values(['code', 'date']).groupby('code').first()
                    sell_for_tax_prices = sell_for_tax_prices_df['adjusted_close']

                    # 必要な分だけ売却（時価総額が小さい銘柄から）
                    portfolio_values = []
                    for code, position in portfolio.items():
                        if code in sell_for_tax_prices.index and pd.notna(sell_for_tax_prices[code]):
                            value = position['shares'] * sell_for_tax_prices[code]
                            portfolio_values.append((code, value, sell_for_tax_prices[code]))

                    portfolio_values.sort(key=lambda x: x[1])  # 時価総額でソート

                    sold_for_tax = 0
                    codes_to_remove = []
                    for code, value, price in portfolio_values:
                        if sold_for_tax >= shortage:
                            break
                        sell_amount = portfolio[code]['shares'] * price
                        sold_for_tax += sell_amount
                        pnl = (price - portfolio[code]['buy_price']) * portfolio[code]['shares']
                        annual_realized_pnl += pnl  # 売却益も損益に含める
                        codes_to_remove.append(code)

                    for code in codes_to_remove:
                        del portfolio[code]

                    cash += sold_for_tax

            cash -= tax
            print(f"    {current_year}年の税金: {tax:,.0f}円（実現損益: {annual_realized_pnl:,.0f}円、税引後現金: {cash:,.0f}円）")
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

    # 銘柄選定（戦略3: 低PER追加）
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

    # 【戦略3】価格、財務、PERデータをマージ
    merged = pd.DataFrame({
        'adjusted_close': prices,
        'bps': fin['bps'],
        'roe': fin['roe']
    })

    # PERデータを結合
    if len(scores) > 0:
        merged = merged.join(scores['quarterly_per'], how='inner')  # PERデータがある銘柄のみ
    else:
        print(f"    スキップ: PERデータなし")
        continue

    merged = merged.dropna()

    if len(merged) < N_STOCKS:
        print(f"    スキップ: データ不足（{len(merged)} < {N_STOCKS}）")
        continue

    # PBR計算
    merged['pbr'] = merged['adjusted_close'] / merged['bps']
    merged = merged[(merged['pbr'] > 0) & (merged['pbr'] < 50)]

    if len(merged) < N_STOCKS:
        print(f"    スキップ: PBRフィルタ後データ不足（{len(merged)} < {N_STOCKS}）")
        continue

    # 【戦略3のフィルタ】低PER（下位25%）のみ選択
    per_q1 = merged['quarterly_per'].quantile(0.25)
    low_per_stocks = merged[merged['quarterly_per'] <= per_q1].copy()

    if len(low_per_stocks) < 10:  # 最低10銘柄は確保
        low_per_stocks = merged.nsmallest(max(10, N_STOCKS), 'quarterly_per')

    print(f"    低PERフィルタ: {len(merged)} → {len(low_per_stocks)} 銘柄")

    # ベースライン選択（低PBR × 高ROE）
    pbr_q1 = low_per_stocks['pbr'].quantile(0.25)
    roe_q3 = low_per_stocks['roe'].quantile(0.75)

    # 割安高質
    candidates = low_per_stocks[(low_per_stocks['pbr'] <= pbr_q1) & (low_per_stocks['roe'] >= roe_q3)]

    if len(candidates) < N_STOCKS:
        candidates = low_per_stocks.nsmallest(N_STOCKS, 'pbr')

    selected = candidates.nsmallest(N_STOCKS, 'pbr')

    # 現金を明示的に使って購入
    target_per_stock = cash / len(selected)
    total_invested = 0

    for code in selected.index:
        price = selected.loc[code, 'adjusted_close']
        shares = int(target_per_stock / (price * UNIT)) * UNIT

        if shares > 0:
            invest_amount = shares * price
            if invest_amount <= cash - total_invested:  # 現金残高チェック
                total_invested += invest_amount
                portfolio[code] = {'shares': shares, 'buy_price': price}

    cash -= total_invested

    print(f"    投資: {total_invested:,.0f}円, 現金残: {cash:,.0f}円, 銘柄数: {len(portfolio)}")

    # 期末時点での評価（次のリバランス日で評価）
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

        # 総資産 = 現金 + 株式時価
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

# 最終評価（保有株式を最新日で評価）
final_eval_date = df_price_pivot.index.max()

# 最終税金
if annual_realized_pnl > 0:
    tax = annual_realized_pnl * TAX_RATE

    # 現金不足の場合は株式を売却して税金を支払う
    if tax > cash and len(portfolio) > 0:
        shortage = tax - cash
        print(f"    最終税金支払いのため株式を一部売却（不足額: {shortage:,.0f}円）")

        # 最終日の価格で売却
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
print("【戦略3結果: ベースライン + 低PER】")
print("="*80)

if len(results) == 0:
    print("\nエラー: バックテスト結果が生成されませんでした")
else:
    df_results = pd.DataFrame(results)

    # リターン計算（total_valueベース）
    df_results['return'] = df_results['total_value'].pct_change()
    df_results['cumulative_return'] = (1 + df_results['return']).cumprod() - 1

    # 総リターン
    total_return = (df_results['total_value'].iloc[-1] / INITIAL_CAPITAL - 1)

    # 期間（年）
    years = (df_results['end_date'].iloc[-1] - df_results['start_date'].iloc[0]).days / 365.25

    # 年率リターン
    annual_return = (1 + total_return) ** (1 / years) - 1

    # ボラティリティ（リバランス期間ベース）
    volatility = df_results['return'].std() * np.sqrt(1)  # 年次リバランスなので√1

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
    output_dir = PROJECT_ROOT / 'analyses' / '20260221_1500_annual_backtest_improved'
    output_dir.mkdir(exist_ok=True, parents=True)

    df_results.to_csv(output_dir / 'strategy3_low_per_results.csv', index=False, encoding='utf-8-sig')

    with open(output_dir / 'strategy3_low_per_summary.txt', 'w', encoding='utf-8') as f:
        f.write("戦略3: ベースライン + 低PER\n")
        f.write("="*80 + "\n\n")
        f.write("【戦略詳細】\n")
        f.write("1. 四半期PERが下位25%の銘柄のみ選択\n")
        f.write("2. その中から低PBR × 高ROEで20銘柄を選択\n")
        f.write("3. 年次リバランス（10月）\n\n")
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
    print("ベースライン（年率+25.61%）との比較:")
    print(f"  ベースライン: 年率+25.61%")
    print(f"  戦略3:        年率{annual_return*100:+.2f}%")
    print(f"  差分:         {annual_return*100 - 25.61:+.2f}%pt")

    if annual_return > 0.2561:
        print(f"  → ✅ 戦略3がベースラインを上回りました！")
    else:
        print(f"  → ❌ 戦略3はベースラインを下回りました")
    print("="*80)

print("\n完了！")
