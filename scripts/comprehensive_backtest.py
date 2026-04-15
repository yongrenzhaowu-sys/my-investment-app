"""
包括的バックテスト実装

複数の戦略を比較：
1. PEG的スコア戦略
2. 益利回り戦略（低PER）
3. 期待リターン戦略
4. PEG的スコア × 出来高フィルタ
5. 益利回り × 高成長率 × 出来高フィルタ
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("包括的バックテスト実装")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/6] データ読み込み...")

# 予測スコアデータ
df_scores = pd.read_csv(
    PROJECT_ROOT / 'analyses/growth_yield_prediction/prediction_scores.csv',
    dtype={'code': str}
)
df_scores['disclosed_date'] = pd.to_datetime(df_scores['disclosed_date'])

print(f"スコアデータ: {len(df_scores):,} レコード")

# 価格データ
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[['date', 'code', 'adjusted_close', 'volume']].copy()

print(f"価格データ: {len(df_price):,} レコード")

# ================================================================================
# 2. 出来高データの追加
# ================================================================================

print("\n[2/6] 出来高データを追加...")

# 各開示日に対して、過去20営業日の平均出来高を計算
df_price_sorted = df_price.sort_values(['code', 'date'])

# 20日移動平均出来高
df_price_sorted['volume_ma20'] = df_price_sorted.groupby('code')['volume'].transform(
    lambda x: x.rolling(window=20, min_periods=10).mean()
)

# 開示日に対応する出来高を取得
volume_data = []

for idx, row in df_scores.iterrows():
    if idx % 10000 == 0:
        print(f"  進捗: {idx}/{len(df_scores)}")

    code = row['code']
    disclosed_date = row['disclosed_date']

    # 開示日以降の最初の価格データを取得
    price_match = df_price_sorted[
        (df_price_sorted['code'] == code) &
        (df_price_sorted['date'] >= disclosed_date)
    ].head(1)

    if len(price_match) > 0:
        volume_data.append({
            'idx': idx,
            'volume_ma20': price_match.iloc[0]['volume_ma20']
        })
    else:
        volume_data.append({
            'idx': idx,
            'volume_ma20': np.nan
        })

df_volume = pd.DataFrame(volume_data).set_index('idx')
df_scores = df_scores.join(df_volume)

# 欠損値除外
df_scores = df_scores.dropna(subset=['volume_ma20'])

print(f"出来高データ追加後: {len(df_scores):,} レコード")

# 出来高中央値
volume_median = df_scores['volume_ma20'].median()
df_scores['high_volume'] = df_scores['volume_ma20'] > volume_median

print(f"出来高中央値: {volume_median:,.0f}")

# ================================================================================
# 3. 戦略定義
# ================================================================================

print("\n[3/6] 戦略を定義...")

strategies = {
    'PEG的スコア': {
        'filter': lambda df: df['custom_growth_rate'] > 0,  # 正の成長率のみ
        'score': 'peg_score',
        'ascending': False  # 高いほど良い
    },
    '益利回り': {
        'filter': lambda df: df['earnings_yield'].notna(),
        'score': 'earnings_yield',
        'ascending': False  # 高いほど良い
    },
    '期待リターン': {
        'filter': lambda df: df['expected_return'].notna(),
        'score': 'expected_return',
        'ascending': False  # 高いほど良い
    },
    '低PER': {
        'filter': lambda df: df['quarterly_per'] > 0,
        'score': 'quarterly_per',
        'ascending': True  # 低いほど良い
    },
    'PEG × 出来高': {
        'filter': lambda df: (df['custom_growth_rate'] > 0) & df['high_volume'],
        'score': 'peg_score',
        'ascending': False
    },
    '益利回り × 高成長 × 出来高': {
        'filter': lambda df: (
            df['earnings_yield'].notna() &
            (df['custom_growth_rate'] > df['custom_growth_rate'].quantile(0.75)) &
            df['high_volume']
        ),
        'score': 'earnings_yield',
        'ascending': False
    }
}

# PEG的スコアを計算（まだない場合）
if 'peg_score' not in df_scores.columns:
    df_scores['peg_score'] = (df_scores['custom_growth_rate'] * 100) / df_scores['quarterly_per']

print(f"戦略数: {len(strategies)}")

# ================================================================================
# 4. バックテスト実行
# ================================================================================

print("\n[4/6] バックテストを実行...")

# パラメータ
HOLDING_PERIOD = 126  # 6ヶ月（営業日）
PORTFOLIO_SIZE = 20  # ポートフォリオ銘柄数
TRANSACTION_COST = 0.003  # 取引コスト（片道0.3%）

# リバランス日を設定（四半期ごと）
all_dates = sorted(df_scores['disclosed_date'].unique())
rebalance_dates = []
last_quarter = None

for date in all_dates:
    quarter = (date.year, (date.month - 1) // 3 + 1)
    if quarter != last_quarter:
        rebalance_dates.append(date)
        last_quarter = quarter

print(f"リバランス日数: {len(rebalance_dates)}")
print(f"期間: {rebalance_dates[0]} ~ {rebalance_dates[-1]}")

# 価格データをピボット化
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

# 各戦略のバックテスト
results = {}

for strategy_name, strategy_config in strategies.items():
    print(f"\n  {strategy_name}を実行中...")

    portfolio_returns = []
    positions = []

    for i, rebalance_date in enumerate(rebalance_dates[:-1]):
        # 次のリバランス日
        next_rebalance_date = rebalance_dates[i + 1] if i + 1 < len(rebalance_dates) else None

        # このリバランス日のデータ
        df_rebalance = df_scores[df_scores['disclosed_date'] == rebalance_date].copy()

        # 戦略のフィルタを適用
        df_filtered = df_rebalance[strategy_config['filter'](df_rebalance)]

        if len(df_filtered) == 0:
            continue

        # スコアでソート
        df_sorted = df_filtered.sort_values(
            strategy_config['score'],
            ascending=strategy_config['ascending']
        )

        # 上位N銘柄を選択
        selected = df_sorted.head(PORTFOLIO_SIZE)

        if len(selected) == 0:
            continue

        # 各銘柄のリターンを計算
        stock_returns = []

        for _, stock in selected.iterrows():
            code = stock['code']

            if code not in df_price_pivot.columns:
                continue

            # エントリー日（開示日以降の最初の営業日）
            entry_dates = df_price_pivot.index[df_price_pivot.index >= rebalance_date]
            if len(entry_dates) == 0:
                continue

            entry_date = entry_dates[0]
            entry_price = df_price_pivot.loc[entry_date, code]

            if pd.isna(entry_price):
                continue

            # 保有期間後の日付
            exit_dates = df_price_pivot.index[df_price_pivot.index >= entry_date]
            if len(exit_dates) <= HOLDING_PERIOD:
                continue

            exit_date = exit_dates[min(HOLDING_PERIOD, len(exit_dates) - 1)]
            exit_price = df_price_pivot.loc[exit_date, code]

            if pd.isna(exit_price):
                continue

            # リターン計算（取引コスト考慮）
            gross_return = (exit_price - entry_price) / entry_price
            net_return = gross_return - (TRANSACTION_COST * 2)  # 往復コスト

            stock_returns.append(net_return)

        if len(stock_returns) > 0:
            # ポートフォリオのリターン（等金額加重）
            portfolio_return = np.mean(stock_returns)
            portfolio_returns.append({
                'date': rebalance_date,
                'return': portfolio_return,
                'num_stocks': len(stock_returns)
            })

    results[strategy_name] = pd.DataFrame(portfolio_returns)

    if len(portfolio_returns) > 0:
        print(f"    リバランス回数: {len(portfolio_returns)}")
        print(f"    平均銘柄数: {np.mean([p['num_stocks'] for p in portfolio_returns]):.1f}")

# ================================================================================
# 5. パフォーマンス指標の計算
# ================================================================================

print("\n[5/6] パフォーマンス指標を計算...")

performance = []

for strategy_name, result_df in results.items():
    if len(result_df) == 0:
        continue

    returns = result_df['return'].values

    # 累積リターン
    cumulative_return = np.prod(1 + returns) - 1

    # 年率リターン
    years = len(returns) * (HOLDING_PERIOD / 252)
    annual_return = (1 + cumulative_return) ** (1 / years) - 1 if years > 0 else 0

    # ボラティリティ（年率）
    volatility = np.std(returns) * np.sqrt(252 / HOLDING_PERIOD)

    # シャープレシオ（リスクフリーレート3%と仮定）
    risk_free_rate = 0.03
    sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0

    # 最大ドローダウン
    cumulative_returns = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdowns = (cumulative_returns - running_max) / running_max
    max_drawdown = np.min(drawdowns)

    # 勝率
    win_rate = np.sum(returns > 0) / len(returns)

    performance.append({
        '戦略': strategy_name,
        'リバランス回数': len(returns),
        '累積リターン': cumulative_return,
        '年率リターン': annual_return,
        'ボラティリティ': volatility,
        'シャープレシオ': sharpe_ratio,
        '最大DD': max_drawdown,
        '勝率': win_rate,
        '平均リターン': np.mean(returns),
        '中央値リターン': np.median(returns)
    })

df_performance = pd.DataFrame(performance)

# ================================================================================
# 6. 結果の表示と保存
# ================================================================================

print("\n" + "="*80)
print("【バックテスト結果】")
print("="*80)

print(f"\n保有期間: {HOLDING_PERIOD}営業日（約6ヶ月）")
print(f"ポートフォリオ銘柄数: {PORTFOLIO_SIZE}")
print(f"取引コスト: {TRANSACTION_COST*100:.1f}%（片道）")

print("\n" + "-"*80)
print("パフォーマンスサマリ")
print("-"*80)

# 年率リターンでソート
df_performance_sorted = df_performance.sort_values('年率リターン', ascending=False)

print("\n年率リターン:")
for _, row in df_performance_sorted.iterrows():
    print(f"  {row['戦略']:30}: {row['年率リターン']*100:6.2f}%")

print("\nシャープレシオ:")
df_sharpe_sorted = df_performance.sort_values('シャープレシオ', ascending=False)
for _, row in df_sharpe_sorted.iterrows():
    print(f"  {row['戦略']:30}: {row['シャープレシオ']:6.2f}")

print("\n最大ドローダウン:")
for _, row in df_performance_sorted.iterrows():
    print(f"  {row['戦略']:30}: {row['最大DD']*100:6.2f}%")

print("\n詳細:")
print(df_performance_sorted.to_string(index=False))

# 保存
output_dir = PROJECT_ROOT / 'analyses' / 'comprehensive_backtest'
output_dir.mkdir(exist_ok=True, parents=True)

df_performance.to_csv(output_dir / 'performance_summary.csv', index=False, encoding='utf-8-sig')

# 各戦略の詳細結果を保存
for strategy_name, result_df in results.items():
    safe_name = strategy_name.replace(' ', '_').replace('×', 'x')
    result_df.to_csv(output_dir / f'{safe_name}_returns.csv', index=False, encoding='utf-8-sig')

# レポート
with open(output_dir / 'backtest_report.txt', 'w', encoding='utf-8') as f:
    f.write("包括的バックテスト結果\n")
    f.write("="*80 + "\n\n")

    f.write(f"保有期間: {HOLDING_PERIOD}営業日（約6ヶ月）\n")
    f.write(f"ポートフォリオ銘柄数: {PORTFOLIO_SIZE}\n")
    f.write(f"取引コスト: {TRANSACTION_COST*100:.1f}%（片道）\n")
    f.write(f"リバランス頻度: 四半期\n\n")

    f.write("="*80 + "\n")
    f.write("パフォーマンスサマリ\n")
    f.write("="*80 + "\n\n")

    f.write(df_performance_sorted.to_string(index=False))
    f.write("\n\n")

    f.write("="*80 + "\n")
    f.write("最強の戦略\n")
    f.write("="*80 + "\n\n")

    best = df_performance_sorted.iloc[0]
    f.write(f"戦略: {best['戦略']}\n")
    f.write(f"年率リターン: {best['年率リターン']*100:.2f}%\n")
    f.write(f"シャープレシオ: {best['シャープレシオ']:.2f}\n")
    f.write(f"最大ドローダウン: {best['最大DD']*100:.2f}%\n")
    f.write(f"勝率: {best['勝率']*100:.1f}%\n")

print(f"\n保存先: {output_dir}")
print("\n" + "="*80)
print("【最強の戦略】")
print("="*80)

best = df_performance_sorted.iloc[0]
print(f"\n戦略名: {best['戦略']}")
print(f"年率リターン: {best['年率リターン']*100:.2f}%")
print(f"シャープレシオ: {best['シャープレシオ']:.2f}")
print(f"最大ドローダウン: {best['最大DD']*100:.2f}%")
print(f"勝率: {best['勝率']*100:.1f}%")
print(f"リバランス回数: {int(best['リバランス回数'])}")

print("\n完了！")
