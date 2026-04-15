"""
CMAファクター計算のデバッグ

なぜCMAが0%になっているのか調査する
"""
import pandas as pd
import numpy as np
from pathlib import Path

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data/processed/jquants_latest_full"

# データ読み込み
df_prices = pd.read_parquet(DATA_DIR / "daily_bars_full.parquet")
df_fins = pd.read_parquet(DATA_DIR / "financials_full.parquet")

# 日付型に変換
df_prices['Date'] = pd.to_datetime(df_prices['Date'])
df_fins['DiscDate'] = pd.to_datetime(df_fins['DiscDate'])

# Codeを4桁に統一
df_prices['Code'] = df_prices['Code'].str[:4]
df_fins['Code'] = df_fins['Code'].str[:4]

# 月次リターン計算
df_prices['YearMonth'] = df_prices['Date'].dt.to_period('M')
df_prices = df_prices.sort_values(['Code', 'Date'])

# 月末価格
month_end = df_prices.groupby(['Code', 'YearMonth']).tail(1).copy()
month_end = month_end.rename(columns={'Date': 'MonthEnd', 'AdjC': 'Price'})
month_end = month_end[['Code', 'YearMonth', 'MonthEnd', 'Price']].sort_values(['Code', 'YearMonth'])

# 月次リターン
month_end['PrevPrice'] = month_end.groupby('Code')['Price'].shift(1)
month_end['MonthlyReturn'] = (month_end['Price'] / month_end['PrevPrice']) - 1

# モメンタム
month_end['Price_t7'] = month_end.groupby('Code')['Price'].shift(7)
month_end['Price_t1'] = month_end.groupby('Code')['Price'].shift(1)
month_end['Momentum_6M'] = (month_end['Price_t1'] / month_end['Price_t7']) - 1

# 財務データ処理
for col in ['Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS']:
    df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

# 各銘柄の最新財務データ
latest_fins = df_fins.sort_values('DiscDate').groupby('Code').last().reset_index()
latest_fins = latest_fins[['Code', 'DiscDate', 'Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS']]

# マージ
month_end = month_end.merge(latest_fins, on='Code', how='left')

# ファクター計算
month_end['MarketCap'] = month_end['Price'] * (month_end['Eq'] / month_end['BPS'])
month_end['BM'] = month_end['Eq'] / month_end['MarketCap']
month_end['ROE'] = month_end['NP'] / month_end['Eq'] * 100
month_end['OP_Margin'] = month_end['OP'] / month_end['Sales'] * 100

# INV_Growth計算
month_end = month_end.sort_values(['Code', 'YearMonth'])
month_end['TA_Prev'] = month_end.groupby('Code')['TA'].shift(4)
month_end['INV_Growth'] = (month_end['TA'] - month_end['TA_Prev']) / month_end['TA_Prev']

print("="*80)
print("CMAファクター計算デバッグ")
print("="*80)

# 2025-10のデータで検証
ym = pd.Period('2025-10')
group = month_end[month_end['YearMonth'] == ym].copy()

print(f"\n[1] 2025-10の全銘柄: {len(group)}銘柄")

# valid（ベースとなるデータセット）
valid = group.dropna(subset=['MonthlyReturn', 'MarketCap', 'BM', 'ROE', 'Momentum_6M'])
print(f"[2] valid（MonthlyReturn, MarketCap, BM, ROE, Momentum_6M全て有効）: {len(valid)}銘柄")

# valid_inv（INV_Growthも有効）
valid_inv = valid.dropna(subset=['INV_Growth'])
print(f"[3] valid_inv（INV_Growthも有効）: {len(valid_inv)}銘柄")

if len(valid_inv) >= 50:
    print(f"[4] CMA計算可能（{len(valid_inv)}銘柄 >= 50銘柄）")

    # INV_Growth分布
    print(f"\n=== INV_Growth分布 ===")
    print(f"  平均: {valid_inv['INV_Growth'].mean():.4f}")
    print(f"  中央値: {valid_inv['INV_Growth'].median():.4f}")
    print(f"  最小値: {valid_inv['INV_Growth'].min():.4f}")
    print(f"  最大値: {valid_inv['INV_Growth'].max():.4f}")

    # 四分位点
    q33_inv = valid_inv['INV_Growth'].quantile(0.33)
    q67_inv = valid_inv['INV_Growth'].quantile(0.67)

    print(f"\n=== 四分位点 ===")
    print(f"  33%点: {q33_inv:.4f}")
    print(f"  67%点: {q67_inv:.4f}")

    # ポートフォリオ分割
    conservative = valid_inv[valid_inv['INV_Growth'] <= q33_inv]
    aggressive = valid_inv[valid_inv['INV_Growth'] >= q67_inv]

    print(f"\n=== ポートフォリオ ===")
    print(f"  Conservative（成長率低い）: {len(conservative)}銘柄")
    print(f"  Aggressive（成長率高い）: {len(aggressive)}銘柄")

    # リターン
    cons_return = conservative['MonthlyReturn'].mean()
    agg_return = aggressive['MonthlyReturn'].mean()
    cma = cons_return - agg_return

    print(f"\n=== リターン ===")
    print(f"  Conservative平均リターン: {cons_return:.4f}")
    print(f"  Aggressive平均リターン: {agg_return:.4f}")
    print(f"  CMA: {cma:.4f}")

else:
    print(f"[4] CMA計算不可（{len(valid_inv)}銘柄 < 50銘柄）")

print("\n" + "="*80)
