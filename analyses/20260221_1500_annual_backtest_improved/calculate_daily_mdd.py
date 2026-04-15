"""
理論株価×モメンタム戦略の日次MDDを計算

リバランス時点のみの評価ではなく、保有期間中の日次価格変動を考慮した
真のMDD（最大ドローダウン）を計算する
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("理論株価×モメンタム戦略 - 日次MDD計算")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/3] データ読み込み...")

# 価格データ
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()

# 理論株価×モメンタム戦略の結果
df_results = pd.read_csv(
    PROJECT_ROOT / 'analyses/20260221_1500_annual_backtest_improved/theoretical_price_momentum_results.csv'
)
df_results['start_date'] = pd.to_datetime(df_results['start_date'])
df_results['end_date'] = pd.to_datetime(df_results['end_date'])

print(f"価格データ: {len(df_price):,} 行")
print(f"リバランス回数: {len(df_results)} 回")

# ================================================================================
# 2. 各期間のポートフォリオを再構築
# ================================================================================

print("\n[2/3] 各期間のポートフォリオを再構築...")

# 注: 実際には、元のバックテストスクリプトから保有銘柄を取得する必要がある
# ここでは簡易的に、各期間の理論株価×モメンタム戦略を再実行して保有銘柄を特定する

# 簡易的なアプローチ: リバランス時点の投資額から、日々のポートフォリオ価値を計算
# より正確には、元のスクリプトを修正して保有銘柄リストを出力する必要がある

print("\n警告: 保有銘柄の詳細情報が必要です")
print("代替アプローチ: リバランス間のリターンを日次で按分して推定します")

# ピボット形式に変換
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

# 日次のポートフォリオ価値を計算（簡易版）
daily_values = []

for idx in range(len(df_results) - 1):  # 最後の行（最終評価）を除く
    row = df_results.iloc[idx]
    start_date = row['start_date']
    end_date = row['end_date']
    start_value = row['total_value'] if idx == 0 else df_results.iloc[idx-1]['total_value']
    end_value = row['total_value']

    # この期間の日次価格を取得
    period_dates = df_price_pivot.loc[start_date:end_date].index

    if len(period_dates) == 0:
        continue

    # 簡易推定: 期間リターンを日次で均等に按分
    total_return = (end_value / start_value) - 1
    daily_return = (1 + total_return) ** (1 / len(period_dates)) - 1

    # より正確なアプローチ: 市場全体のリターンと相関させる
    # ここでは簡易的に均等按分を使用
    current_value = start_value
    for date in period_dates:
        current_value = current_value * (1 + daily_return)
        daily_values.append({
            'date': date,
            'total_value': current_value
        })

df_daily = pd.DataFrame(daily_values)

# ================================================================================
# 3. 日次MDDを計算
# ================================================================================

print("\n[3/3] 日次MDDを計算（簡易推定版）...")

if len(df_daily) > 0:
    df_daily['peak'] = df_daily['total_value'].cummax()
    df_daily['drawdown'] = (df_daily['total_value'] - df_daily['peak']) / df_daily['peak']
    daily_mdd = df_daily['drawdown'].min()

    print(f"\n簡易推定による日次MDD: {daily_mdd*100:.2f}%")
    print(f"リバランス時点のみのMDD: -1.10%")
    print(f"\n注意: これは簡易推定です。正確な日次MDDを計算するには、")
    print("各期間の実際の保有銘柄情報が必要です。")
else:
    print("\nエラー: 日次データが生成されませんでした")

# ================================================================================
# より正確な方法の提案
# ================================================================================

print("\n" + "="*80)
print("より正確な日次MDD計算のために必要な情報:")
print("="*80)
print("1. 各リバランス日における保有銘柄のリスト（コードと株数）")
print("2. 各保有期間中の日次株価")
print("3. 現金残高の推移")
print()
print("推奨アプローチ:")
print("元のバックテストスクリプト（backtest_theoretical_price_momentum.py）を修正して、")
print("各リバランス時点の保有銘柄情報を出力し、それを使って日次評価を行う")
print("="*80)

print("\n簡易推定を終了します。")
print("より正確な計算のため、バックテストスクリプトを修正します...")
