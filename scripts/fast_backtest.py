"""
高速版バックテスト実装

複数の戦略を比較：
1. PEG的スコア戦略
2. 益利回り戦略（低PER）
3. 期待リターン戦略
4. PEG的スコア × 出来高フィルタ
5. 益利回り × 高成長 × 出来高フィルタ
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("高速版バックテスト実装")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/5] データ読み込み...")

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
# 2. 出来高データの追加（高速化）
# ================================================================================

print("\n[2/5] 出来高データを追加（高速化版）...")

# 20日移動平均出来高を事前計算
df_price = df_price.sort_values(['code', 'date'])
df_price['volume_ma20'] = df_price.groupby('code')['volume'].transform(
    lambda x: x.rolling(window=20, min_periods=10).mean()
)

# 開示日でマージ（前後数日のずれを許容）
df_price_for_merge = df_price[['date', 'code', 'volume_ma20']].copy()
df_price_for_merge = df_price_for_merge.rename(columns={'date': 'disclosed_date'})

# 完全一致でマージを試みる
df_scores = df_scores.merge(
    df_price_for_merge,
    on=['disclosed_date', 'code'],
    how='left'
)

# 欠損している場合は前後5日以内の出来高を使う
print("  欠損値を補完中...")
for days_offset in [1, 2, 3, 4, 5, -1, -2, -3, -4, -5]:
    mask = df_scores['volume_ma20'].isna()
    if mask.sum() == 0:
        break

    df_price_shifted = df_price[['date', 'code', 'volume_ma20']].copy()
    df_price_shifted['disclosed_date'] = df_price_shifted['date'] - pd.Timedelta(days=days_offset)
    df_price_shifted = df_price_shifted.rename(columns={'volume_ma20': 'volume_ma20_shifted'})
    df_price_shifted = df_price_shifted.drop(columns=['date'])

    df_scores = df_scores.merge(
        df_price_shifted[['disclosed_date', 'code', 'volume_ma20_shifted']],
        on=['disclosed_date', 'code'],
        how='left'
    )

    df_scores.loc[mask, 'volume_ma20'] = df_scores.loc[mask, 'volume_ma20_shifted']
    df_scores = df_scores.drop(columns=['volume_ma20_shifted'])

# 欠損値除外
df_scores = df_scores.dropna(subset=['volume_ma20'])

print(f"出来高データ追加後: {len(df_scores):,} レコード")

# 出来高中央値
volume_median = df_scores['volume_ma20'].median()
df_scores['high_volume'] = df_scores['volume_ma20'] > volume_median

print(f"出来高中央値: {volume_median:,.0f}")

# PEG的スコアを計算（まだない場合）
if 'peg_score' not in df_scores.columns:
    df_scores['peg_score'] = (df_scores['custom_growth_rate'] * 100) / df_scores['quarterly_per']

# ================================================================================
# 3. 戦略定義
# ================================================================================

print("\n[3/5] 戦略を定義...")

strategies = {
    'PEG的スコア': {
        'filter': lambda df: df['custom_growth_rate'] > 0,
        'score': 'peg_score',
        'ascending': False
    },
    '益利回り': {
        'filter': lambda df: df['earnings_yield'].notna(),
        'score': 'earnings_yield',
        'ascending': False
    },
    '期待リターン': {
        'filter': lambda df: df['expected_return'].notna(),
        'score': 'expected_return',
        'ascending': False
    },
    '低PER': {
        'filter': lambda df: df['quarterly_per'] > 0,
        'score': 'quarterly_per',
        'ascending': True
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

print(f"戦略数: {len(strategies)}")

# ================================================================================
# 4. リバランス日の設定
# ================================================================================

print("\n[4/5] リバランス日を設定...")

# 四半期ごとのリバランス
all_dates = sorted(df_scores['disclosed_date'].unique())
rebalance_dates = []
last_quarter = None

for date in all_dates:
    quarter = (date.year, (date.month - 1) // 3 + 1)
    if quarter != last_quarter:
        rebalance_dates.append(date)
        last_quarter = quarter

# 最初の1年はウォームアップ期間として除外
rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp('2018-01-01')]

print(f"リバランス日数: {len(rebalance_dates)}")
print(f"期間: {rebalance_dates[0]} ~ {rebalance_dates[-1]}")

# ================================================================================
# 5. バックテスト実行（高速化版）
# ================================================================================

print("\n[5/5] バックテストを実行（高速化版）...")

HOLDING_PERIOD_DAYS = 180  # 約6ヶ月
PORTFOLIO_SIZE = 20
TRANSACTION_COST = 0.003

# 価格データを準備
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

results = {}

for strategy_name, strategy_config in strategies.items():
    print(f"\n  {strategy_name}...")

    all_returns = []
    rebalance_count = 0

    for rebalance_date in rebalance_dates[:-1]:  # 最後の1回は除外（保有期間確保のため）
        # このリバランス日のデータ
        df_rebalance = df_scores[df_scores['disclosed_date'] == rebalance_date].copy()

        # フィルタ適用
        df_filtered = df_rebalance[strategy_config['filter'](df_rebalance)]

        if len(df_filtered) == 0:
            continue

        # スコアでソート
        df_sorted = df_filtered.sort_values(
            strategy_config['score'],
            ascending=strategy_config['ascending']
        )

        # 上位N銘柄
        selected = df_sorted.head(PORTFOLIO_SIZE)

        # エントリー日を決定（開示日以降の最初の営業日）
        entry_date = df_price_pivot.index[df_price_pivot.index >= rebalance_date][0] if len(df_price_pivot.index[df_price_pivot.index >= rebalance_date]) > 0 else None

        if entry_date is None:
            continue

        # イグジット日を決定
        exit_date_target = entry_date + pd.Timedelta(days=HOLDING_PERIOD_DAYS)
        possible_exit_dates = df_price_pivot.index[df_price_pivot.index >= exit_date_target]

        if len(possible_exit_dates) == 0:
            continue

        exit_date = possible_exit_dates[0]

        # 各銘柄のリターンを計算
        stock_returns = []

        for code in selected['code']:
            if code not in df_price_pivot.columns:
                continue

            entry_price = df_price_pivot.loc[entry_date, code]
            exit_price = df_price_pivot.loc[exit_date, code]

            if pd.isna(entry_price) or pd.isna(exit_price):
                continue

            # リターン（取引コスト考慮）
            gross_return = (exit_price - entry_price) / entry_price
            net_return = gross_return - (TRANSACTION_COST * 2)

            stock_returns.append(net_return)

        if len(stock_returns) >= 5:  # 最低5銘柄は確保
            portfolio_return = np.mean(stock_returns)
            all_returns.append({
                'date': rebalance_date,
                'return': portfolio_return,
                'num_stocks': len(stock_returns)
            })
            rebalance_count += 1

    results[strategy_name] = pd.DataFrame(all_returns)
    print(f"    リバランス回数: {rebalance_count}")

# ================================================================================
# 6. パフォーマンス指標の計算
# ================================================================================

print("\n" + "="*80)
print("【バックテスト結果】")
print("="*80)

print(f"\n保有期間: 約{HOLDING_PERIOD_DAYS}日（約6ヶ月）")
print(f"ポートフォリオ銘柄数: {PORTFOLIO_SIZE}")
print(f"取引コスト: {TRANSACTION_COST*100:.1f}%（片道）")
print(f"リバランス頻度: 四半期")

performance = []

for strategy_name, result_df in results.items():
    if len(result_df) == 0:
        continue

    returns = result_df['return'].values

    # 累積リターン
    cumulative_return = np.prod(1 + returns) - 1

    # 期間（年）
    date_range = (result_df['date'].max() - result_df['date'].min()).days / 365.25
    years = max(date_range, 1)

    # 年率リターン
    annual_return = (1 + cumulative_return) ** (1 / years) - 1

    # ボラティリティ（年率）
    volatility = np.std(returns) * np.sqrt(4)  # 四半期リバランスなので年4回

    # シャープレシオ
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

if len(df_performance) == 0:
    print("\nエラー: バックテスト結果が生成されませんでした")
else:
    # 年率リターンでソート
    df_performance_sorted = df_performance.sort_values('年率リターン', ascending=False)

    print("\n" + "-"*80)
    print("パフォーマンスサマリ（年率リターン順）")
    print("-"*80)

    for _, row in df_performance_sorted.iterrows():
        print(f"\n{row['戦略']}:")
        print(f"  年率リターン: {row['年率リターン']*100:6.2f}%")
        print(f"  シャープレシオ: {row['シャープレシオ']:6.2f}")
        print(f"  最大DD: {row['最大DD']*100:6.2f}%")
        print(f"  勝率: {row['勝率']*100:5.1f}%")
        print(f"  リバランス回数: {int(row['リバランス回数'])}")

    # 保存
    output_dir = PROJECT_ROOT / 'analyses' / 'fast_backtest'
    output_dir.mkdir(exist_ok=True, parents=True)

    df_performance.to_csv(output_dir / 'performance_summary.csv', index=False, encoding='utf-8-sig')

    # 各戦略の詳細
    for strategy_name, result_df in results.items():
        safe_name = strategy_name.replace(' ', '_').replace('×', 'x')
        result_df.to_csv(output_dir / f'{safe_name}_returns.csv', index=False, encoding='utf-8-sig')

    # レポート
    with open(output_dir / 'backtest_report.txt', 'w', encoding='utf-8') as f:
        f.write("高速版バックテスト結果\n")
        f.write("="*80 + "\n\n")

        f.write(f"保有期間: 約{HOLDING_PERIOD_DAYS}日（約6ヶ月）\n")
        f.write(f"ポートフォリオ銘柄数: {PORTFOLIO_SIZE}\n")
        f.write(f"取引コスト: {TRANSACTION_COST*100:.1f}%（片道）\n")
        f.write(f"リバランス頻度: 四半期\n")
        f.write(f"期間: {rebalance_dates[0]} ~ {rebalance_dates[-1]}\n\n")

        f.write("="*80 + "\n")
        f.write("パフォーマンスサマリ\n")
        f.write("="*80 + "\n\n")

        for _, row in df_performance_sorted.iterrows():
            f.write(f"\n{row['戦略']}:\n")
            f.write(f"  年率リターン: {row['年率リターン']*100:.2f}%\n")
            f.write(f"  シャープレシオ: {row['シャープレシオ']:.2f}\n")
            f.write(f"  最大DD: {row['最大DD']*100:.2f}%\n")
            f.write(f"  勝率: {row['勝率']*100:.1f}%\n")

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

print("\n完了！")
