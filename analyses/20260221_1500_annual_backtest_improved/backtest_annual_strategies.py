"""
年次リバランス（10月）改善戦略バックテスト

ベースライン：低PBR × 高ROE（年率28.52%、実績あり）

改善戦略：
1. 低PBR × 高ROE × 出来高フィルタ
2. 低PBR × 高ROE × 低四半期PER
3. 低PBR × 高ROE × 高成長率
4. 低PBR × 高ROE × PEG的スコア
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("年次リバランス（10月）改善戦略バックテスト")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/6] データ読み込み...")

# 価格データ
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()
print(f"価格データ: {len(df_price):,} 行")

# 財務データ（年次）
df_fin_annual = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin_annual['disclosed_date'] = pd.to_datetime(df_fin_annual['disclosed_date'])
df_fin_annual = df_fin_annual[df_fin_annual['disclosed_date'] >= '2016-01-01'].copy()

# 年次決算のみ
if 'fiscal_quarter' in df_fin_annual.columns:
    df_fin_annual = df_fin_annual[df_fin_annual['fiscal_quarter'] == 'FY'].copy()

df_fin_annual = df_fin_annual[['disclosed_date', 'code', 'equity', 'net_profit', 'bps']].copy()
df_fin_annual['roe'] = (df_fin_annual['net_profit'] / df_fin_annual['equity']) * 100
df_fin_annual = df_fin_annual[
    (df_fin_annual['roe'] > -100) & (df_fin_annual['roe'] < 100) &
    (df_fin_annual['bps'] > 0) & (df_fin_annual['equity'] > 0)
].copy()

print(f"財務データ（年次）: {len(df_fin_annual):,} 行")

# 財務データ（四半期）- PER、成長率、PEG計算用
df_fin_quarterly = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin_quarterly['disclosed_date'] = pd.to_datetime(df_fin_quarterly['disclosed_date'])
df_fin_quarterly = df_fin_quarterly[df_fin_quarterly['disclosed_date'] >= '2016-01-01'].copy()
df_fin_quarterly = df_fin_quarterly[['disclosed_date', 'code', 'fiscal_quarter', 'ordinary_profit', 'equity', 'bps']].copy()
df_fin_quarterly = df_fin_quarterly.dropna(subset=['ordinary_profit'])

print(f"財務データ（四半期）: {len(df_fin_quarterly):,} 行")

# ================================================================================
# 2. 四半期指標の計算
# ================================================================================

print("\n[2/6] 四半期指標を計算...")

# カスタム成長率の計算
df_fin_quarterly = df_fin_quarterly.sort_values(['code', 'disclosed_date'])

results = []
for code, group in df_fin_quarterly.groupby('code'):
    group = group.reset_index(drop=True)

    for i in range(len(group)):
        current_row = group.iloc[i]
        current_date = current_row['disclosed_date']
        current_profit = current_row['ordinary_profit']
        current_quarter = current_row['fiscal_quarter']
        equity = current_row['equity']
        bps = current_row['bps']

        # 前年同期
        previous_year_data = group[
            (group['fiscal_quarter'] == current_quarter) &
            (group['disclosed_date'] < current_date) &
            (group['disclosed_date'] >= current_date - pd.Timedelta(days=400)) &
            (group['disclosed_date'] <= current_date - pd.Timedelta(days=300))
        ]

        if len(previous_year_data) == 0:
            previous_year_data = group[
                (group['disclosed_date'] < current_date) &
                (group['disclosed_date'] >= current_date - pd.Timedelta(days=400))
            ]

        if len(previous_year_data) == 0:
            continue

        previous_year_profit = previous_year_data.iloc[-1]['ordinary_profit']

        # 直近4四半期
        recent_4q = group[group['disclosed_date'] <= current_date].tail(4)

        if len(recent_4q) < 4:
            continue

        denominator = recent_4q['ordinary_profit'].abs().sum()

        if denominator == 0:
            continue

        # カスタム成長率
        growth_rate = (current_profit - previous_year_profit) / denominator

        results.append({
            'code': code,
            'disclosed_date': current_date,
            'current_profit': current_profit,
            'growth_rate': growth_rate,
            'equity': equity,
            'bps': bps
        })

df_quarterly_metrics = pd.DataFrame(results)

# 異常値除外
df_quarterly_metrics = df_quarterly_metrics[
    (df_quarterly_metrics['growth_rate'] >= -5) &
    (df_quarterly_metrics['growth_rate'] <= 5)
].copy()

print(f"四半期指標計算完了: {len(df_quarterly_metrics):,} レコード")

# ================================================================================
# 3. 出来高データの準備
# ================================================================================

print("\n[3/6] 出来高データを準備...")

# 20日移動平均出来高
df_price = df_price.sort_values(['code', 'date'])
df_price['volume_ma20'] = df_price.groupby('code')['volume'].transform(
    lambda x: x.rolling(window=20, min_periods=10).mean()
)

print("出来高データ準備完了")

# ================================================================================
# 4. リバランス日の設定（10月1日）
# ================================================================================

print("\n[4/6] リバランス日を設定...")

# 10月1日またはその直後の営業日
rebalance_dates = []
for year in range(2016, 2026):
    target_date = pd.Timestamp(f'{year}-10-01')
    # 10月1日以降の最初の営業日
    available_dates = df_price[df_price['date'] >= target_date]['date'].unique()
    if len(available_dates) > 0:
        rebalance_dates.append(available_dates[0])

rebalance_dates = sorted(rebalance_dates)

print(f"リバランス日数: {len(rebalance_dates)}")
print(f"期間: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}")
print(f"リバランス日: {[d.strftime('%Y-%m-%d') for d in rebalance_dates]}")

# ================================================================================
# 5. 戦略定義
# ================================================================================

print("\n[5/6] 戦略を定義...")

# 価格データをピボット化
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

# 各リバランス日での利用可能データを事前計算
def prepare_data_for_date(rebalance_date):
    """指定日時点での利用可能な全データを準備"""

    # 年次財務データ（PBR、ROE）
    fin_annual = df_fin_annual[df_fin_annual['disclosed_date'] <= rebalance_date].copy()
    fin_annual = fin_annual.sort_values('disclosed_date').groupby('code').tail(1)
    fin_annual = fin_annual.set_index('code')

    # 四半期財務データ（成長率、PER計算用）
    fin_quarterly = df_quarterly_metrics[df_quarterly_metrics['disclosed_date'] <= rebalance_date].copy()
    fin_quarterly = fin_quarterly.sort_values('disclosed_date').groupby('code').tail(1)
    fin_quarterly = fin_quarterly.set_index('code')

    # 価格データ
    if rebalance_date not in df_price_pivot.index:
        return None

    prices = df_price_pivot.loc[rebalance_date].dropna()

    # 出来高データ
    volume_data = df_price[df_price['date'] == rebalance_date].set_index('code')['volume_ma20']

    # マージ
    merged = pd.DataFrame({
        'price': prices,
        'bps_annual': fin_annual['bps'],
        'roe': fin_annual['roe'],
        'volume_ma20': volume_data
    })

    # 四半期データをマージ
    merged = merged.join(fin_quarterly[['current_profit', 'growth_rate', 'equity', 'bps']], rsuffix='_q')

    # PBR計算（年次BPSを使用）
    merged['pbr'] = merged['price'] / merged['bps_annual']

    # 四半期PER計算（時価総額 / 四半期経常利益）
    merged['estimated_shares'] = merged['equity'] / merged['bps']
    merged['market_cap'] = merged['price'] * merged['estimated_shares']
    merged['quarterly_per'] = merged['market_cap'] / merged['current_profit']

    # PEG的スコア
    merged['peg_score'] = (merged['growth_rate'] * 100) / merged['quarterly_per']

    # 異常値除外
    merged = merged[
        (merged['pbr'] > 0) & (merged['pbr'] < 50) &
        (merged['quarterly_per'] > 0) & (merged['quarterly_per'] < 1000)
    ]

    return merged.dropna(subset=['pbr', 'roe'])

strategies = {
    'ベースライン（低PBR×高ROE）': {
        'filter': lambda df: (
            (df['pbr'] <= df['pbr'].quantile(0.25)) &
            (df['roe'] >= df['roe'].quantile(0.75))
        ),
        'score': 'pbr',
        'ascending': True
    },
    '戦略1（+出来高フィルタ）': {
        'filter': lambda df: (
            (df['pbr'] <= df['pbr'].quantile(0.25)) &
            (df['roe'] >= df['roe'].quantile(0.75)) &
            (df['volume_ma20'] > df['volume_ma20'].median())
        ),
        'score': 'pbr',
        'ascending': True
    },
    '戦略2（+低四半期PER）': {
        'filter': lambda df: (
            (df['pbr'] <= df['pbr'].quantile(0.25)) &
            (df['roe'] >= df['roe'].quantile(0.75)) &
            (df['quarterly_per'] <= df['quarterly_per'].quantile(0.25))
        ),
        'score': 'pbr',
        'ascending': True
    },
    '戦略3（+高成長率）': {
        'filter': lambda df: (
            (df['pbr'] <= df['pbr'].quantile(0.25)) &
            (df['roe'] >= df['roe'].quantile(0.75)) &
            (df['growth_rate'] >= df['growth_rate'].quantile(0.75))
        ),
        'score': 'pbr',
        'ascending': True
    },
    '戦略4（+PEG的スコア）': {
        'filter': lambda df: (
            (df['pbr'] <= df['pbr'].quantile(0.25)) &
            (df['roe'] >= df['roe'].quantile(0.75)) &
            (df['peg_score'] >= df['peg_score'].quantile(0.75))
        ),
        'score': 'pbr',
        'ascending': True
    }
}

print(f"戦略数: {len(strategies)}")

# ================================================================================
# 6. バックテスト実行
# ================================================================================

print("\n[6/6] バックテストを実行...")

INITIAL_CASH = 10_000_000
N_STOCKS = 20
TAX_RATE = 0.20315
UNIT = 100

all_results = {}

for strategy_name, strategy_config in strategies.items():
    print(f"\n  {strategy_name}...")

    cash = INITIAL_CASH
    portfolio = {}
    annual_realized_pnl = 0
    current_year = None
    results = []

    for i, rebalance_date in enumerate(rebalance_dates[:-1]):  # 最後の1回は除外
        # 年の切り替わり
        if current_year != rebalance_date.year:
            if current_year is not None and annual_realized_pnl > 0:
                tax = annual_realized_pnl * TAX_RATE
                cash -= tax
            annual_realized_pnl = 0
            current_year = rebalance_date.year

        # 既存ポートフォリオ売却
        sell_value = 0
        for code, position in portfolio.items():
            if code in df_price_pivot.columns:
                sell_price = df_price_pivot.loc[rebalance_date, code]
                if pd.notna(sell_price):
                    sell_amount = position['shares'] * sell_price
                    sell_value += sell_amount
                    pnl = (sell_price - position['buy_price']) * position['shares']
                    annual_realized_pnl += pnl

        cash += sell_value
        portfolio = {}

        # データ準備
        merged = prepare_data_for_date(rebalance_date)

        if merged is None or len(merged) < N_STOCKS:
            results.append({
                'date': rebalance_date,
                'cash': cash,
                'invested': 0,
                'n_stocks': 0
            })
            continue

        # フィルタ適用
        filtered = merged[strategy_config['filter'](merged)]

        if len(filtered) < N_STOCKS:
            # フィルタ後が不足する場合はベースライン条件のみ
            filtered = merged[
                (merged['pbr'] <= merged['pbr'].quantile(0.25)) &
                (merged['roe'] >= merged['roe'].quantile(0.75))
            ]

        if len(filtered) < N_STOCKS:
            # それでも不足する場合は低PBRのみ
            filtered = merged.nsmallest(N_STOCKS, 'pbr')

        # スコアでソート
        selected = filtered.sort_values(strategy_config['score'], ascending=strategy_config['ascending']).head(N_STOCKS)

        # 購入
        target_per_stock = cash / len(selected)
        total_invested = 0

        for code in selected.index:
            price = selected.loc[code, 'price']
            shares = int(target_per_stock / (price * UNIT)) * UNIT

            if shares > 0:
                invest_amount = shares * price
                total_invested += invest_amount
                portfolio[code] = {'shares': shares, 'buy_price': price}

        cash -= total_invested

        results.append({
            'date': rebalance_date,
            'cash': cash,
            'invested': total_invested,
            'n_stocks': len(portfolio)
        })

    # 最終税金
    if annual_realized_pnl > 0:
        tax = annual_realized_pnl * TAX_RATE
        cash -= tax
        results[-1]['cash'] = cash

    # 最終評価
    final_date = rebalance_dates[-1]
    final_portfolio_value = 0
    for code, position in portfolio.items():
        if code in df_price_pivot.columns:
            final_price = df_price_pivot.loc[final_date, code]
            if pd.notna(final_price):
                final_portfolio_value += position['shares'] * final_price

    results[-1]['invested'] = final_portfolio_value

    all_results[strategy_name] = pd.DataFrame(results)

    print(f"    完了")

# ================================================================================
# 7. パフォーマンス分析
# ================================================================================

print("\n" + "="*80)
print("【バックテスト結果】")
print("="*80)

performance = []

for strategy_name, result_df in all_results.items():
    result_df['total_value'] = result_df['cash'] + result_df['invested']
    result_df['return'] = result_df['total_value'].pct_change()
    result_df['cumulative_return'] = (1 + result_df['return']).cumprod() - 1

    # パフォーマンス指標
    total_return = result_df['cumulative_return'].iloc[-1]
    years = (result_df['date'].iloc[-1] - result_df['date'].iloc[0]).days / 365.25
    annual_return = (1 + total_return) ** (1 / years) - 1

    volatility = result_df['return'].std() * np.sqrt(1)  # 年次なのでそのまま

    sharpe_ratio = (annual_return - 0.03) / volatility if volatility > 0 else 0

    # MDD
    result_df['peak'] = result_df['total_value'].cummax()
    result_df['drawdown'] = (result_df['total_value'] - result_df['peak']) / result_df['peak']
    max_drawdown = result_df['drawdown'].min()

    win_rate = np.sum(result_df['return'] > 0) / len(result_df['return']) if len(result_df['return']) > 0 else 0

    performance.append({
        '戦略': strategy_name,
        '最終資産': result_df['total_value'].iloc[-1],
        '累積リターン': total_return,
        '年率リターン': annual_return,
        'ボラティリティ': volatility,
        'シャープレシオ': sharpe_ratio,
        '最大DD': max_drawdown,
        '勝率': win_rate
    })

df_performance = pd.DataFrame(performance)
df_performance_sorted = df_performance.sort_values('年率リターン', ascending=False)

print("\nパフォーマンスサマリ（年率リターン順）:")
print("-"*80)

for _, row in df_performance_sorted.iterrows():
    print(f"\n{row['戦略']}:")
    print(f"  最終資産:     {row['最終資産']:12,.0f}円")
    print(f"  年率リターン: {row['年率リターン']*100:8.2f}%")
    print(f"  シャープレシオ: {row['シャープレシオ']:6.2f}")
    print(f"  最大DD:       {row['最大DD']*100:8.2f}%")
    print(f"  勝率:         {row['勝率']*100:8.1f}%")

# 保存
output_dir = PROJECT_ROOT / 'analyses' / '20260221_1500_annual_backtest_improved'
output_dir.mkdir(exist_ok=True, parents=True)

df_performance.to_csv(output_dir / 'performance_summary.csv', index=False, encoding='utf-8-sig')

for strategy_name, result_df in all_results.items():
    safe_name = strategy_name.replace('（', '_').replace('）', '').replace('×', 'x').replace('+', '_')
    result_df.to_csv(output_dir / f'{safe_name}.csv', index=False, encoding='utf-8-sig')

with open(output_dir / 'backtest_report.txt', 'w', encoding='utf-8') as f:
    f.write("年次リバランス（10月）改善戦略バックテスト結果\n")
    f.write("="*80 + "\n\n")
    f.write(f"期間: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}\n")
    f.write(f"初期資本: {INITIAL_CASH:,}円\n")
    f.write(f"リバランス頻度: 年次（10月1日）\n")
    f.write(f"ポートフォリオ銘柄数: {N_STOCKS}\n\n")

    f.write("="*80 + "\n")
    f.write("パフォーマンスサマリ\n")
    f.write("="*80 + "\n\n")

    for _, row in df_performance_sorted.iterrows():
        f.write(f"\n{row['戦略']}:\n")
        f.write(f"  最終資産:       {row['最終資産']:,.0f}円\n")
        f.write(f"  年率リターン:   {row['年率リターン']*100:.2f}%\n")
        f.write(f"  シャープレシオ: {row['シャープレシオ']:.2f}\n")
        f.write(f"  最大DD:         {row['最大DD']*100:.2f}%\n")
        f.write(f"  勝率:           {row['勝率']*100:.1f}%\n")

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("【最強の戦略】")
print("="*80)

best = df_performance_sorted.iloc[0]
print(f"\n戦略名: {best['戦略']}")
print(f"最終資産: {best['最終資産']:,.0f}円")
print(f"年率リターン: {best['年率リターン']*100:.2f}%")
print(f"シャープレシオ: {best['シャープレシオ']:.2f}")
print(f"最大ドローダウン: {best['最大DD']*100:.2f}%")

# ベースラインとの比較
baseline = df_performance[df_performance['戦略'] == 'ベースライン（低PBR×高ROE）'].iloc[0]
improvement = best['年率リターン'] - baseline['年率リターン']
print(f"\nベースラインとの差: {improvement*100:+.2f}%pt")

print("\n完了！")
