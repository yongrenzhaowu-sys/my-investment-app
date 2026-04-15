"""
FF5分析結果に基づく銘柄スクリーニング

推奨戦略: 大型グロース×モメンタム
- 時価総額: 上位30%
- 過去6ヶ月リターン: 上位33%
- PBR: 1.5以上
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# データ読み込み
print("="*80)
print("銘柄スクリーニング（大型グロース×モメンタム戦略）")
print("="*80)

DATA_DIR = Path(__file__).parent.parent.parent / "data/processed/jquants_historical_6years"
OUTPUT_DIR = Path(__file__).parent / "results"

print("\n[1] データ読み込み")
df_prices = pd.read_parquet(DATA_DIR / "daily_bars_2021_2026.parquet")
df_fins = pd.read_parquet(DATA_DIR / "financials_2021_2026.parquet")

print(f"  株価: {len(df_prices):,}レコード")
print(f"  財務: {len(df_fins):,}レコード")

# 日付型に変換
df_prices['Date'] = pd.to_datetime(df_prices['Date'])
df_fins['DiscDate'] = pd.to_datetime(df_fins['DiscDate'])

# Codeを4桁に統一
df_prices['Code'] = df_prices['Code'].str[:4]
df_fins['Code'] = df_fins['Code'].str[:4]

# 数値型に変換
for col in ['Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS', 'ShOutFY', 'TrShFY', 'AvgSh']:
    df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

# BPS代替計算
df_fins['SharesOut'] = df_fins['ShOutFY'].fillna(df_fins['TrShFY']).fillna(df_fins['AvgSh'])
df_fins['BPS_Calc'] = df_fins['Eq'] / df_fins['SharesOut']
df_fins['BPS_Final'] = df_fins['BPS'].fillna(df_fins['BPS_Calc'])

# 最新の株価データ
print("\n[2] 最新の株価データ取得")
latest_date = df_prices['Date'].max()
six_months_ago = latest_date - timedelta(days=180)

print(f"  最新日: {latest_date.date()}")
print(f"  6ヶ月前: {six_months_ago.date()}")

# 最新価格
latest_prices = df_prices[df_prices['Date'] == latest_date].copy()
latest_prices = latest_prices[['Code', 'AdjC']].rename(columns={'AdjC': 'Price_Now'})

# 6ヶ月前の価格
six_month_prices = df_prices[
    (df_prices['Date'] >= six_months_ago - timedelta(days=7)) &
    (df_prices['Date'] <= six_months_ago + timedelta(days=7))
].copy()
six_month_prices = six_month_prices.sort_values(['Code', 'Date']).groupby('Code').first().reset_index()
six_month_prices = six_month_prices[['Code', 'AdjC']].rename(columns={'AdjC': 'Price_6M'})

# マージ
stock_data = latest_prices.merge(six_month_prices, on='Code', how='inner')

# 6ヶ月リターン計算
stock_data['Return_6M'] = (stock_data['Price_Now'] / stock_data['Price_6M'] - 1) * 100

print(f"  6ヶ月リターン計算完了: {len(stock_data)}銘柄")

# 最新の財務データ取得
print("\n[3] 最新の財務データ取得")
latest_fins = df_fins[df_fins['DiscDate'] <= latest_date].copy()
latest_fins = latest_fins.sort_values(['Code', 'DiscDate']).groupby('Code').last().reset_index()

print(f"  財務データ: {len(latest_fins)}銘柄")

# 株価データと財務データをマージ
stock_data = stock_data.merge(
    latest_fins[['Code', 'Eq', 'BPS_Final', 'Sales', 'OP', 'SharesOut']],
    on='Code',
    how='left'
)

# 時価総額計算（Price × 発行済株式数）
stock_data['MarketCap'] = stock_data['Price_Now'] * (stock_data['Eq'] / stock_data['BPS_Final'])

# PBR計算
stock_data['PBR'] = stock_data['Price_Now'] / stock_data['BPS_Final']

# 営業利益率
stock_data['OP_Margin'] = (stock_data['OP'] / stock_data['Sales']) * 100

print(f"  マージ後: {len(stock_data)}銘柄")

# 欠損値除外
valid_data = stock_data.dropna(subset=['MarketCap', 'Return_6M', 'PBR']).copy()
print(f"  有効データ: {len(valid_data)}銘柄")

# スクリーニング
print("\n[4] スクリーニング条件適用")

# 条件1: 時価総額上位30%
mc_threshold = valid_data['MarketCap'].quantile(0.70)
condition1 = valid_data['MarketCap'] >= mc_threshold
print(f"  条件1（時価総額上位30%）: {condition1.sum()}銘柄")

# 条件2: 過去6ヶ月リターン上位33%
return_threshold = valid_data['Return_6M'].quantile(0.67)
condition2 = valid_data['Return_6M'] >= return_threshold
print(f"  条件2（6ヶ月リターン上位33%）: {condition2.sum()}銘柄")

# 条件3: PBR 1.5以上（グロース株）
condition3 = valid_data['PBR'] >= 1.5
print(f"  条件3（PBR≧1.5）: {condition3.sum()}銘柄")

# 全条件を満たす銘柄
screened = valid_data[condition1 & condition2 & condition3].copy()
print(f"\n  全条件を満たす銘柄: {len(screened)}銘柄")

# ソート（6ヶ月リターン降順）
screened = screened.sort_values('Return_6M', ascending=False)

# 結果表示
print("\n[5] スクリーニング結果（上位30銘柄）")
print("="*80)
print(f"{'銘柄':>6} {'6M騰落率':>10} {'時価総額':>12} {'PBR':>8} {'営業利益率':>10}")
print("-"*80)

for idx, row in screened.head(30).iterrows():
    mc_str = f"{row['MarketCap']/1e8:.1f}億" if pd.notna(row['MarketCap']) else "N/A"
    op_margin_str = f"{row['OP_Margin']:.1f}%" if pd.notna(row['OP_Margin']) else "N/A"

    print(f"{row['Code']:>6} {row['Return_6M']:>9.2f}% {mc_str:>12} {row['PBR']:>7.2f} {op_margin_str:>10}")

# CSV保存
output_path = OUTPUT_DIR / "screened_stocks_momentum.csv"
screened.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"\n結果を保存: {output_path}")
print(f"合計 {len(screened)} 銘柄")

# サマリー統計
print("\n[6] サマリー統計")
print("="*80)
print(f"平均6ヶ月リターン: {screened['Return_6M'].mean():.2f}%")
print(f"平均時価総額: {screened['MarketCap'].mean()/1e8:.1f}億円")
print(f"平均PBR: {screened['PBR'].mean():.2f}")
print(f"平均営業利益率: {screened['OP_Margin'].mean():.2f}%")

print("\n完了")
