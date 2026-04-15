"""
年次リバランス（10月）バックテスト - R2補正モメンタム戦略（数学的に正確）

【モメンタム指標の計算方法】
1. 過去90日分の対数終値を用いて線形回帰 → SLOPE（対数リターン）を抽出
2. 年率換算: annualized_return = exp(SLOPE * 250) - 1 （数学的に正確）
3. R2（決定係数）で補正: momentum_score = annualized_return × R2

【オプション1との違い】
- オプション1: (1 + exp(SLOPE) - 1)^250 - 1 （ユーザーの式）
- オプション2: exp(SLOPE * 250) - 1 （数学的に正確）
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("年次リバランス（10月）バックテスト - R2補正モメンタム（数学的に正確）")
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
# 3. モメンタム指標の計算（R2補正、数学的に正確）
# ================================================================================

print("\n[3/4] R2補正モメンタム指標を計算（数学的に正確）...")

def calculate_r2_adjusted_momentum_exp(prices_df, date, lookback_days=90):
    """
    R2補正モメンタム指標を計算（数学的に正確な方法）

    Parameters:
    - prices_df: 価格データ（pivot形式、index=date, columns=code）
    - date: 計算基準日
    - lookback_days: 遡る日数（デフォルト90日）

    Returns:
    - Series: {code: momentum_score}
    """
    # 過去90日分のデータを取得
    end_date = date
    start_date = end_date - pd.Timedelta(days=lookback_days * 2)  # 余裕を持って取得

    historical = prices_df.loc[start_date:end_date].copy()

    if len(historical) < lookback_days * 0.7:  # 最低70%のデータが必要
        return pd.Series(dtype=float)

    # 最新のlookback_days分のデータを使用
    historical = historical.tail(lookback_days)

    momentum_scores = {}

    for code in historical.columns:
        prices = historical[code].dropna()

        if len(prices) < lookback_days * 0.7:  # 最低70%のデータが必要
            continue

        # 対数価格
        log_prices = np.log(prices)

        # 時間軸（0, 1, 2, ..., n-1）
        time_index = np.arange(len(log_prices))

        # 線形回帰
        coefficients = np.polyfit(time_index, log_prices, deg=1)
        slope = coefficients[0]
        intercept = coefficients[1]

        # 異常なSLOPEを除外
        if abs(slope) > 0.05:
            continue

        # R2（決定係数）を計算
        predicted = slope * time_index + intercept
        ss_res = np.sum((log_prices - predicted) ** 2)
        ss_tot = np.sum((log_prices - np.mean(log_prices)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # 年率換算（数学的に正確な方法）
        # slope は1日あたりの対数リターン
        # 年率リターン = exp(slope * 250) - 1
        annualized_return = np.exp(slope * 250) - 1

        # 異常な年率リターンを除外
        if annualized_return < -0.95 or annualized_return > 10.0:
            continue

        # R2補正モメンタムスコア
        momentum_score = annualized_return * r_squared

        momentum_scores[code] = momentum_score

    return pd.Series(momentum_scores)

# 各リバランス日でモメンタムを計算
momentum_by_date = {}
for i, rdate in enumerate(rebalance_dates):
    print(f"  {i+1}/{len(rebalance_dates)}: {rdate.date()}")
    momentum = calculate_r2_adjusted_momentum_exp(df_price_pivot, rdate, lookback_days=90)
    momentum_by_date[rdate] = momentum

print("R2補正モメンタム計算完了（数学的に正確）")

# ================================================================================
# 4. バックテスト実行（R2補正モメンタム戦略、数学的に正確）
# ================================================================================

print("\n[4/4] バックテストを実行（R2補正モメンタム戦略、数学的に正確）...")

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

    # 銘柄選定（R2補正モメンタム戦略、数学的に正確）
    start_prices_df = df_price[
        (df_price['date'] >= start_date) &
        (df_price['date'] <= start_date + pd.Timedelta(days=5))
    ].copy()

    if len(start_prices_df) == 0:
        print(f"    スキップ: 価格データなし")
        continue

    start_prices_df = start_prices_df.sort_values(['code', 'date']).groupby('code').first()
    prices = start_prices_df['adjusted_close'].dropna()
    momentum = momentum_by_date.get(start_date, pd.Series(dtype=float))

    if len(momentum) == 0:
        print(f"    スキップ: モメンタムデータなし")
        continue

    # 価格とモメンタムデータをマージ
    merged = pd.DataFrame({
        'adjusted_close': prices,
        'momentum_score': momentum
    }).dropna()

    if len(merged) < N_STOCKS:
        print(f"    スキップ: データ不足（{len(merged)} < {N_STOCKS}）")
        continue

    # モメンタムスコア上位20銘柄を選択
    selected = merged.nlargest(N_STOCKS, 'momentum_score')

    print(f"    モメンタムフィルタ: {len(merged)} → {len(selected)} 銘柄, スコア範囲: {selected['momentum_score'].min():.4f} ~ {selected['momentum_score'].max():.4f}")

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
print("【R2補正モメンタム戦略結果（数学的に正確）】")
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
    output_dir = PROJECT_ROOT / 'analyses' / '20260221_1500_annual_backtest_improved'
    output_dir.mkdir(exist_ok=True, parents=True)

    df_results.to_csv(output_dir / 'momentum_r2_exp_results.csv', index=False, encoding='utf-8-sig')

    with open(output_dir / 'momentum_r2_exp_summary.txt', 'w', encoding='utf-8') as f:
        f.write("R2補正モメンタム戦略（数学的に正確）\n")
        f.write("="*80 + "\n\n")
        f.write("【計算方法】\n")
        f.write("1. 過去90日分の対数終値で線形回帰 → SLOPE\n")
        f.write("2. 年率換算: exp(SLOPE * 250) - 1\n")
        f.write("3. R2で補正: momentum_score = annualized_return × R2\n\n")
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
    print(f"  ベースライン:         年率+25.61%")
    print(f"  R2補正（オプション1）: 年率-2.96%")
    print(f"  R2補正（オプション2）: 年率{annual_return*100:+.2f}%")

    if annual_return > -0.0296:
        print(f"  → オプション2の方が優れています（+{annual_return*100 - (-2.96):.2f}%pt）")
    else:
        print(f"  → オプション1の方が優れています（{annual_return*100 - (-2.96):.2f}%pt）")
    print("="*80)

print("\n完了！")
