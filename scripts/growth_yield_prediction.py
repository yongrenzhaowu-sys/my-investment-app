"""
カスタム成長率 × 益利回りによる株価予測の検証

理論的アプローチ:
1. 期待リターン = 益利回り + カスタム成長率（加算）
2. 割安度スコア = 益利回り × カスタム成長率（乗算）
3. PEG的スコア = カスタム成長率 / PER
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("カスタム成長率 × 益利回りによる株価予測の検証")
print("="*80)

# 1. データ読み込み
print("\n[1/4] データ読み込み...")
df = pd.read_csv(
    PROJECT_ROOT / 'analyses/quarterly_metrics_validation/quarterly_metrics_data.csv',
    dtype={'code': str}
)
df['disclosed_date'] = pd.to_datetime(df['disclosed_date'])

print(f"レコード数: {len(df):,}")

# 正のPERのみに絞る
df = df[df['quarterly_per'] > 0].copy()
print(f"正のPERのみ: {len(df):,}")

# 2. 各種スコアを計算
print("\n[2/4] 予測スコアを計算中...")

# 益利回り = 1/PER × 100 = (四半期経常利益/時価総額) × 100
df['earnings_yield'] = (1 / df['quarterly_per']) * 100

# 方法1: 期待リターン = 益利回り + カスタム成長率×100
df['expected_return'] = df['earnings_yield'] + df['custom_growth_rate'] * 100

# 方法2: 割安度スコア = 益利回り × カスタム成長率
df['value_score'] = df['earnings_yield'] * df['custom_growth_rate']

# 方法3: PEG的スコア = カスタム成長率 / PER（成長率を%に変換）
# 成長率が負の場合は除外
df_positive_growth = df[df['custom_growth_rate'] > 0].copy()
df_positive_growth['peg_score'] = (df_positive_growth['custom_growth_rate'] * 100) / df_positive_growth['quarterly_per']

print(f"正の成長率のみ: {len(df_positive_growth):,}")

# 異常値除外
# 益利回り: -50% ~ 50%
# 期待リターン: -100% ~ 100%
# 割安度スコア: -10 ~ 10
df = df[
    (df['earnings_yield'] >= -50) &
    (df['earnings_yield'] <= 50) &
    (df['expected_return'] >= -100) &
    (df['expected_return'] <= 100) &
    (df['value_score'] >= -10) &
    (df['value_score'] <= 10)
].copy()

print(f"異常値除外後: {len(df):,}")

# 3. 相関分析
print("\n" + "="*80)
print("【結果1】各予測スコアと株価騰落率の相関係数")
print("="*80)

scores = {
    'earnings_yield': '益利回り',
    'custom_growth_rate': 'カスタム成長率（参考）',
    'expected_return': '期待リターン（益利回り + 成長率×100）',
    'value_score': '割安度スコア（益利回り × 成長率）'
}

periods = ['return_1M', 'return_3M', 'return_6M']
period_names = ['1ヶ月', '3ヶ月', '6ヶ月']

print(f"\nサンプル数: {len(df):,}")
print("-" * 60)

for score_col, score_name in scores.items():
    print(f"\n{score_name}:")
    for period, name in zip(periods, period_names):
        corr = df[score_col].corr(df[period])
        print(f"  {name}: {corr:+.4f}")

# 正の成長率のみでPEGスコアを検証
print("\n\nPEG的スコア（正の成長率のみ、N={:,}）:".format(len(df_positive_growth)))
print("-" * 60)
for period, name in zip(periods, period_names):
    corr = df_positive_growth['peg_score'].corr(df_positive_growth[period])
    print(f"  {name}: {corr:+.4f}")

# 4. 四分位分析
print("\n" + "="*80)
print("【結果2】期待リターン四分位別の平均騰落率")
print("="*80)

df['expected_return_quartile'] = pd.qcut(
    df['expected_return'],
    q=4,
    labels=['Q1 (低)', 'Q2', 'Q3', 'Q4 (高)'],
    duplicates='drop'
)

expected_return_analysis = df.groupby('expected_return_quartile')[periods].mean()

print(f"\nサンプル数: {len(df):,}")
print("\n平均騰落率（%）:")
print((expected_return_analysis * 100).round(2))

# Q1 vs Q4の差
print("\n効果（Q4高 - Q1低）:")
for period, name in zip(periods, period_names):
    q1 = df[df['expected_return_quartile'] == 'Q1 (低)'][period].mean()
    q4 = df[df['expected_return_quartile'] == 'Q4 (高)'][period].mean()
    diff = q4 - q1
    print(f"  {name}: {diff*100:+6.2f}%")

print("\n" + "="*80)
print("【結果3】割安度スコア四分位別の平均騰落率")
print("="*80)

df['value_score_quartile'] = pd.qcut(
    df['value_score'],
    q=4,
    labels=['Q1 (低)', 'Q2', 'Q3', 'Q4 (高)'],
    duplicates='drop'
)

value_score_analysis = df.groupby('value_score_quartile')[periods].mean()

print(f"\nサンプル数: {len(df):,}")
print("\n平均騰落率（%）:")
print((value_score_analysis * 100).round(2))

# Q1 vs Q4の差
print("\n効果（Q4高 - Q1低）:")
for period, name in zip(periods, period_names):
    q1 = df[df['value_score_quartile'] == 'Q1 (低)'][period].mean()
    q4 = df[df['value_score_quartile'] == 'Q4 (高)'][period].mean()
    diff = q4 - q1
    print(f"  {name}: {diff*100:+6.2f}%")

# 5. クロス分析: 益利回り × カスタム成長率
print("\n" + "="*80)
print("【結果4】益利回り × カスタム成長率のクロス分析（3ヶ月、%）")
print("="*80)

# 益利回り四分位
df['earnings_yield_quartile'] = pd.qcut(
    df['earnings_yield'],
    q=4,
    labels=['Q1 (低利回り)', 'Q2', 'Q3', 'Q4 (高利回り)'],
    duplicates='drop'
)

# 成長率四分位（既に存在）
if 'growth_quartile' not in df.columns:
    df['growth_quartile'] = pd.qcut(
        df['custom_growth_rate'],
        q=4,
        labels=['Q1 (低成長)', 'Q2', 'Q3', 'Q4 (高成長)'],
        duplicates='drop'
    )

pivot = df.pivot_table(
    index='earnings_yield_quartile',
    columns='growth_quartile',
    values='return_3M',
    aggfunc='mean'
)

print("\n")
print((pivot * 100).round(2))

# 最強の組み合わせ
print("\n" + "="*80)
print("【結果5】最強の組み合わせ（高益利回り × 高成長率）")
print("="*80)

best_combo = df[
    (df['earnings_yield_quartile'] == 'Q4 (高利回り)') &
    (df['growth_quartile'] == 'Q4 (高成長)')
]

print(f"\nサンプル数: {len(best_combo):,}")
print("\n平均騰落率（%）:")
for period, name in zip(periods, period_names):
    ret = best_combo[period].mean()
    print(f"  {name}: {ret*100:+6.2f}%")

# 6. 理論株価の推定
print("\n" + "="*80)
print("【結果6】理論株価との乖離による予測")
print("="*80)

# 理論株価 = 現在の利益 × 理論PER
# 理論PER = 1 / (割引率 - 成長率)
# 簡易版: 理論PER = 1 / (リスクフリーレート - 成長率)
# リスクフリーレートを3%と仮定
risk_free_rate = 0.03

# 成長率が高すぎる場合は除外（割引率より大きいと理論株価が無限大）
df_theory = df[df['custom_growth_rate'] < risk_free_rate].copy()

# 理論PER
df_theory['theoretical_per'] = 1 / (risk_free_rate - df_theory['custom_growth_rate'])

# 理論株価 = 四半期経常利益 × 理論PER（年換算なので×4）
df_theory['theoretical_price'] = (df_theory['current_profit'] * 4) * df_theory['theoretical_per']

# 現在の株価（推定）= 時価総額 / 発行済株式数
df_theory['current_price'] = df_theory['adjusted_close']

# 乖離率 = (理論株価 - 現在株価) / 現在株価
df_theory['price_gap'] = (df_theory['theoretical_price'] / df_theory['estimated_shares'] - df_theory['current_price']) / df_theory['current_price']

# 異常値除外（乖離率が-90%～+200%）
df_theory = df_theory[
    (df_theory['price_gap'] >= -0.9) &
    (df_theory['price_gap'] <= 2.0)
].copy()

print(f"理論株価計算可能: {len(df_theory):,}")

# 乖離率と実際のリターンの相関
print("\n理論株価との乖離率と実際のリターンの相関:")
for period, name in zip(periods, period_names):
    corr = df_theory['price_gap'].corr(df_theory[period])
    print(f"  {name}: {corr:+.4f}")

# 乖離率四分位別の分析
df_theory['gap_quartile'] = pd.qcut(
    df_theory['price_gap'],
    q=4,
    labels=['Q1 (割高)', 'Q2', 'Q3', 'Q4 (割安)'],
    duplicates='drop'
)

gap_analysis = df_theory.groupby('gap_quartile')[periods].mean()

print("\n乖離率四分位別の平均騰落率（%）:")
print((gap_analysis * 100).round(2))

# 保存
print("\n[4/4] 結果を保存中...")

output_dir = PROJECT_ROOT / 'analyses' / 'growth_yield_prediction'
output_dir.mkdir(exist_ok=True, parents=True)

df.to_csv(output_dir / 'prediction_scores.csv', index=False, encoding='utf-8-sig')

with open(output_dir / 'report.txt', 'w', encoding='utf-8') as f:
    f.write("カスタム成長率 × 益利回りによる株価予測の検証\n")
    f.write("="*80 + "\n\n")

    f.write("【各予測スコアと株価騰落率の相関係数】\n")
    for score_col, score_name in scores.items():
        f.write(f"\n{score_name}:\n")
        for period, name in zip(periods, period_names):
            corr = df[score_col].corr(df[period])
            f.write(f"  {name}: {corr:+.4f}\n")

    f.write("\n【期待リターン四分位別の平均騰落率（%）】\n")
    f.write(expected_return_analysis.to_string())
    f.write("\n\n")

    f.write("【割安度スコア四分位別の平均騰落率（%）】\n")
    f.write(value_score_analysis.to_string())
    f.write("\n\n")

    f.write("【最強の組み合わせ（高益利回り × 高成長率）】\n")
    f.write(f"サンプル数: {len(best_combo):,}\n")
    for period, name in zip(periods, period_names):
        ret = best_combo[period].mean()
        f.write(f"  {name}: {ret*100:+6.2f}%\n")

print(f"\n保存先: {output_dir}")
print("\n完了！")

# サマリ
print("\n" + "="*80)
print("【サマリ】予測力の比較（3ヶ月）")
print("="*80)

summary = {
    '益利回り': df['earnings_yield'].corr(df['return_3M']),
    'カスタム成長率': df['custom_growth_rate'].corr(df['return_3M']),
    '期待リターン（加算）': df['expected_return'].corr(df['return_3M']),
    '割安度スコア（乗算）': df['value_score'].corr(df['return_3M']),
    'PEG的スコア': df_positive_growth['peg_score'].corr(df_positive_growth['return_3M']),
    '理論株価乖離率': df_theory['price_gap'].corr(df_theory['return_3M'])
}

print("\n相関係数（絶対値が大きいほど予測力が高い）:")
for name, corr in sorted(summary.items(), key=lambda x: abs(x[1]), reverse=True):
    print(f"{name:30}: {corr:+.4f}")

print("\n" + "="*80)
print("【推奨される予測方法】")
print("="*80)

# 最も相関が高いものを特定
best_method = max(summary.items(), key=lambda x: abs(x[1]))
print(f"\n最強の予測方法: {best_method[0]}")
print(f"相関係数: {best_method[1]:+.4f}")

# Q4 vs Q1の効果を比較
print("\n各方法のQ4 vs Q1効果（3ヶ月）:")

methods = {
    '期待リターン': ('expected_return_quartile', df),
    '割安度スコア': ('value_score_quartile', df),
}

for method_name, (quartile_col, data) in methods.items():
    q1 = data[data[quartile_col] == 'Q1 (低)']['return_3M'].mean()
    q4 = data[data[quartile_col] == 'Q4 (高)']['return_3M'].mean()
    diff = q4 - q1
    print(f"  {method_name:20}: {diff*100:+6.2f}%")
