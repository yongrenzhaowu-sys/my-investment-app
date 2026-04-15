"""
月次リターンから最大ドローダウンを手動計算
"""

import pandas as pd
import numpy as np

# 月次リターン（出力から取得）
monthly_returns = [
    ('2024-01', 0.0066),
    ('2024-02', 0.0420),
    ('2024-03', 0.0111),
    ('2024-04', 0.0017),
    ('2024-05', 0.0135),
    ('2024-06', 0.0135),
    ('2024-07', -0.0059),
    ('2024-08', -0.0089),
    ('2024-09', -0.0165),
    ('2024-10', -0.0327),
    ('2024-11', 0.0561),
    ('2024-12', -0.0194),
    ('2025-01', -0.0238),
    ('2025-02', -0.0139),
    ('2025-03', -0.0272),
    ('2025-04', 0.0376),
    ('2025-05', 0.0228),
    ('2025-06', 0.0826),
    ('2025-07', 0.0650),
    ('2025-08', 0.0317),
    ('2025-09', 0.0461),
    ('2025-10', 0.0167),
    ('2025-11', 0.0176),
]

df = pd.DataFrame(monthly_returns, columns=['Month', 'MonthlyReturn'])

# 累積リターン
df['CumulativeReturn'] = (1 + df['MonthlyReturn']).cumprod()

# ランニング最大値
df['RunningMax'] = df['CumulativeReturn'].cummax()

# ドローダウン
df['Drawdown'] = (df['CumulativeReturn'] - df['RunningMax']) / df['RunningMax']

# 最大ドローダウン
max_dd = df['Drawdown'].min()
max_dd_idx = df['Drawdown'].idxmin()
max_dd_month = df.iloc[max_dd_idx]['Month']

print("=" * 80)
print("月次ドローダウン計算結果")
print("=" * 80)

print(f"\n最大ドローダウン: {max_dd:.2%}")
print(f"発生月: {max_dd_month}")

# 累積リターン
final_cumulative = df['CumulativeReturn'].iloc[-1] - 1
print(f"\n累積リターン: {final_cumulative:.2%}")

# 年率換算
months = len(df)
cagr = (1 + final_cumulative) ** (12 / months) - 1
print(f"年率リターン（CAGR）: {cagr:.2%}")

# ドローダウン詳細（最悪5ヶ月）
print(f"\nドローダウン最悪5ヶ月:")
print(df.sort_values('Drawdown').head(5)[['Month', 'MonthlyReturn', 'CumulativeReturn', 'Drawdown']].to_string(index=False))

# 全期間の推移
print(f"\n\n月次推移:")
print(df[['Month', 'MonthlyReturn', 'CumulativeReturn', 'Drawdown']].to_string(index=False))

# CSVに保存
output_path = "backtest_monthly_drawdown_manual.csv"
df.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"\n結果保存: {output_path}")
