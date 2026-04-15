"""
四半期PERと四半期割安率の検証

指標定義：
1. 四半期PER = 時価総額 / 四半期経常利益
2. 四半期割安率 = (今期経常利益 - 前年同期経常利益) / 時価総額
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("四半期PERと四半期割安率の検証")
print("="*80)

# 1. 既存の時価総額付きデータを読み込む
print("\n[1/3] データ読み込み...")
df = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_by_marketcap/growth_rate_by_marketcap.csv',
    dtype={'code': str}
)
df['disclosed_date'] = pd.to_datetime(df['disclosed_date'])

print(f"レコード数: {len(df):,}")

# 2. 指標を計算
print("\n[2/3] 指標を計算中...")

# 四半期PER = 時価総額 / 四半期経常利益
# ※ 経常利益が負の場合は除外（PERが定義できない）
df['quarterly_per'] = df['market_cap'] / df['current_profit']

# 四半期割安率 = (今期経常利益 - 前年同期経常利益) / 時価総額
df['quarterly_discount_rate'] = (df['current_profit'] - df['previous_year_profit']) / df['market_cap']

# 異常値除外
# 四半期PER: -1000 ~ 1000の範囲（負のPERも一旦含める）
df = df[
    (df['quarterly_per'] >= -1000) &
    (df['quarterly_per'] <= 1000)
].copy()

# 四半期割安率: -1 ~ 1の範囲（-100% ~ +100%）
df = df[
    (df['quarterly_discount_rate'] >= -1) &
    (df['quarterly_discount_rate'] <= 1)
].copy()

print(f"異常値除外後: {len(df):,} レコード")

# 正のPERのみに絞る版も作成
df_positive_per = df[df['quarterly_per'] > 0].copy()
print(f"正のPERのみ: {len(df_positive_per):,} レコード")

# 3. 相関分析
print("\n" + "="*80)
print("【結果1】各指標と株価騰落率の相関係数")
print("="*80)

metrics = {
    'quarterly_per': '四半期PER',
    'quarterly_discount_rate': '四半期割安率',
    'custom_growth_rate': 'カスタム成長率（参考）'
}

periods = ['return_1M', 'return_3M', 'return_6M']
period_names = ['1ヶ月', '3ヶ月', '6ヶ月']

print("\n全データ（N={:,}）:".format(len(df)))
print("-" * 60)
for metric_col, metric_name in metrics.items():
    print(f"\n{metric_name}:")
    for period, name in zip(periods, period_names):
        corr = df[metric_col].corr(df[period])
        print(f"  {name}: {corr:+.4f}")

print("\n\n正のPERのみ（N={:,}）:".format(len(df_positive_per)))
print("-" * 60)
print("\n四半期PER:")
for period, name in zip(periods, period_names):
    corr = df_positive_per['quarterly_per'].corr(df_positive_per[period])
    print(f"  {name}: {corr:+.4f}")

# 四分位分析
print("\n" + "="*80)
print("【結果2】四半期PER四分位別の平均騰落率")
print("="*80)

# 正のPERのみで四分位
df_positive_per['per_quartile'] = pd.qcut(
    df_positive_per['quarterly_per'],
    q=4,
    labels=['Q1 (低PER)', 'Q2', 'Q3', 'Q4 (高PER)'],
    duplicates='drop'
)

per_analysis = df_positive_per.groupby('per_quartile')[periods].mean()

print(f"\nサンプル数: {len(df_positive_per):,}")
print("\n平均騰落率（%）:")
print((per_analysis * 100).round(2))

# Q1 vs Q4の差
print("\n効果（Q1低PER - Q4高PER）:")
for period, name in zip(periods, period_names):
    q1 = df_positive_per[df_positive_per['per_quartile'] == 'Q1 (低PER)'][period].mean()
    q4 = df_positive_per[df_positive_per['per_quartile'] == 'Q4 (高PER)'][period].mean()
    diff = q1 - q4
    print(f"  {name}: {diff*100:+6.2f}%")

print("\n" + "="*80)
print("【結果3】四半期割安率四分位別の平均騰落率")
print("="*80)

df['discount_quartile'] = pd.qcut(
    df['quarterly_discount_rate'],
    q=4,
    labels=['Q1 (割高)', 'Q2', 'Q3', 'Q4 (割安)'],
    duplicates='drop'
)

discount_analysis = df.groupby('discount_quartile')[periods].mean()

print(f"\nサンプル数: {len(df):,}")
print("\n平均騰落率（%）:")
print((discount_analysis * 100).round(2))

# Q1 vs Q4の差
print("\n効果（Q4割安 - Q1割高）:")
for period, name in zip(periods, period_names):
    q1 = df[df['discount_quartile'] == 'Q1 (割高)'][period].mean()
    q4 = df[df['discount_quartile'] == 'Q4 (割安)'][period].mean()
    diff = q4 - q1
    print(f"  {name}: {diff*100:+6.2f}%")

# 四半期PERと四半期割安率の関係
print("\n" + "="*80)
print("【結果4】四半期PER × 四半期割安率のクロス分析（3ヶ月、%）")
print("="*80)

# 正のPERのみで分析
df_positive_per['discount_quartile'] = pd.qcut(
    df_positive_per['quarterly_discount_rate'],
    q=4,
    labels=['Q1 (割高)', 'Q2', 'Q3', 'Q4 (割安)'],
    duplicates='drop'
)

pivot = df_positive_per.pivot_table(
    index='per_quartile',
    columns='discount_quartile',
    values='return_3M',
    aggfunc='mean'
)

print("\n")
print((pivot * 100).round(2))

# 最強の組み合わせ
print("\n" + "="*80)
print("【結果5】最強の組み合わせ（低PER × 割安）")
print("="*80)

best_combo = df_positive_per[
    (df_positive_per['per_quartile'] == 'Q1 (低PER)') &
    (df_positive_per['discount_quartile'] == 'Q4 (割安)')
]

print(f"\nサンプル数: {len(best_combo):,}")
print("\n平均騰落率（%）:")
for period, name in zip(periods, period_names):
    ret = best_combo[period].mean()
    print(f"  {name}: {ret*100:+6.2f}%")

# 比較：カスタム成長率との関係
print("\n" + "="*80)
print("【結果6】四半期割安率 vs カスタム成長率")
print("="*80)

corr_discount_growth = df['quarterly_discount_rate'].corr(df['custom_growth_rate'])
print(f"\n相関係数: {corr_discount_growth:+.4f}")
print("→ 正の相関が強ければ、類似の指標")

# 保存
print("\n[3/3] 結果を保存中...")

output_dir = PROJECT_ROOT / 'analyses' / 'quarterly_metrics_validation'
output_dir.mkdir(exist_ok=True, parents=True)

df.to_csv(output_dir / 'quarterly_metrics_data.csv', index=False, encoding='utf-8-sig')

with open(output_dir / 'report.txt', 'w', encoding='utf-8') as f:
    f.write("四半期PERと四半期割安率の検証\n")
    f.write("="*80 + "\n\n")

    f.write("【定義】\n")
    f.write("1. 四半期PER = 時価総額 / 四半期経常利益\n")
    f.write("2. 四半期割安率 = (今期経常利益 - 前年同期経常利益) / 時価総額\n\n")

    f.write("【相関係数】\n")
    f.write("四半期PER（正のみ）:\n")
    for period, name in zip(periods, period_names):
        corr = df_positive_per['quarterly_per'].corr(df_positive_per[period])
        f.write(f"  {name}: {corr:+.4f}\n")

    f.write("\n四半期割安率:\n")
    for period, name in zip(periods, period_names):
        corr = df['quarterly_discount_rate'].corr(df[period])
        f.write(f"  {name}: {corr:+.4f}\n")

    f.write("\n【四半期PER四分位別の平均騰落率（%）】\n")
    f.write(per_analysis.to_string())
    f.write("\n\n")

    f.write("【四半期割安率四分位別の平均騰落率（%）】\n")
    f.write(discount_analysis.to_string())
    f.write("\n\n")

    f.write("【最強の組み合わせ（低PER × 割安）】\n")
    f.write(f"サンプル数: {len(best_combo):,}\n")
    for period, name in zip(periods, period_names):
        ret = best_combo[period].mean()
        f.write(f"  {name}: {ret*100:+6.2f}%\n")

print(f"\n保存先: {output_dir}")
print("\n完了！")

# サマリ統計
print("\n" + "="*80)
print("【サマリ】相関の強さ比較（3ヶ月）")
print("="*80)

summary = {
    '四半期PER（正のみ）': df_positive_per['quarterly_per'].corr(df_positive_per['return_3M']),
    '四半期割安率': df['quarterly_discount_rate'].corr(df['return_3M']),
    'カスタム成長率': df['custom_growth_rate'].corr(df['return_3M'])
}

for name, corr in sorted(summary.items(), key=lambda x: abs(x[1]), reverse=True):
    print(f"{name:20}: {corr:+.4f}")

print("\n→ 絶対値が大きいほど予測力が高い")
