"""
FF5分析結果に基づく銘柄スクリーニング（調整済み株価版）

推奨戦略: 大型グロース（モメンタムは緩和）
- 調整済み株価を使用
- 時価総額: 上位30%
- 過去6ヶ月リターン: 中央値以上
- PBR: 2.0以上
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# データ読み込み
print("="*80)
print("銘柄スクリーニング（調整済み株価版：大型グロース戦略）")
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

# 【重要】調整済み株価を正しく計算
print("\n[2] 調整済み株価を計算")
df_prices['AdjC_Correct'] = df_prices['C'] * df_prices['AdjFactor']
df_prices['Price'] = df_prices['AdjC_Correct']

print(f"  調整係数が1.0でないレコード: {(df_prices['AdjFactor'] != 1.0).sum():,}レコード")

# 重複データの除外
print("\n[3] 重複データの除外")
df_prices = df_prices.sort_values(['Code', 'Date', 'Vo'], ascending=[True, True, False])
df_prices = df_prices.drop_duplicates(subset=['Code', 'Date'], keep='first')
print(f"  除外後: {len(df_prices):,}レコード")

# 数値型に変換
for col in ['Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS', 'ShOutFY', 'TrShFY', 'AvgSh']:
    df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

# BPS代替計算
df_fins['SharesOut'] = df_fins['ShOutFY'].fillna(df_fins['TrShFY']).fillna(df_fins['AvgSh'])
df_fins['BPS_Calc'] = df_fins['Eq'] / df_fins['SharesOut']
df_fins['BPS_Final'] = df_fins['BPS'].fillna(df_fins['BPS_Calc'])

# 最新の株価データ
print("\n[4] 最新の株価データ取得")
latest_date = df_prices['Date'].max()
six_months_ago = latest_date - timedelta(days=180)

print(f"  最新日: {latest_date.date()}")
print(f"  6ヶ月前: {six_months_ago.date()}")

# 最新価格
latest_prices = df_prices[df_prices['Date'] == latest_date].copy()
latest_prices = latest_prices[['Code', 'Price']].rename(columns={'Price': 'Price_Now'})

# 6ヶ月前の価格
six_month_prices = df_prices[
    (df_prices['Date'] >= six_months_ago - timedelta(days=7)) &
    (df_prices['Date'] <= six_months_ago + timedelta(days=7))
].copy()
six_month_prices = six_month_prices.sort_values(['Code', 'Date']).groupby('Code').first().reset_index()
six_month_prices = six_month_prices[['Code', 'Price']].rename(columns={'Price': 'Price_6M'})

# マージ
stock_data = latest_prices.merge(six_month_prices, on='Code', how='inner')

# 6ヶ月リターン計算
stock_data['Return_6M'] = (stock_data['Price_Now'] / stock_data['Price_6M'] - 1) * 100

print(f"  6ヶ月リターン計算完了: {len(stock_data)}銘柄")

# 最新の財務データ取得
print("\n[5] 最新の財務データ取得")
latest_fins = df_fins[df_fins['DiscDate'] <= latest_date].copy()
latest_fins = latest_fins.sort_values(['Code', 'DiscDate']).groupby('Code').last().reset_index()

print(f"  財務データ: {len(latest_fins)}銘柄")

# 株価データと財務データをマージ
stock_data = stock_data.merge(
    latest_fins[['Code', 'Eq', 'BPS_Final', 'Sales', 'OP', 'SharesOut']],
    on='Code',
    how='left'
)

# 時価総額計算
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
print("\n[6] スクリーニング条件適用")

# 条件1: 時価総額上位30%
mc_threshold = valid_data['MarketCap'].quantile(0.70)
condition1 = valid_data['MarketCap'] >= mc_threshold
print(f"  条件1（時価総額上位30%）: {condition1.sum()}銘柄")
print(f"    閾値: {mc_threshold/1e8:.1f}億円以上")

# 条件2: 過去6ヶ月リターン中央値以上（モメンタム緩和）
return_threshold = valid_data['Return_6M'].median()
condition2 = valid_data['Return_6M'] >= return_threshold
print(f"  条件2（6ヶ月リターン中央値以上）: {condition2.sum()}銘柄")
print(f"    閾値: {return_threshold:.2f}%以上")

# 条件3: PBR 2.0以上（グロース株）
condition3 = valid_data['PBR'] >= 2.0
print(f"  条件3（PBR≧2.0）: {condition3.sum()}銘柄")

# 全条件を満たす銘柄
screened = valid_data[condition1 & condition2 & condition3].copy()
print(f"\n  全条件を満たす銘柄: {len(screened)}銘柄")

if len(screened) == 0:
    print("\n⚠️ 条件を満たす銘柄がありません。条件を緩和します。")
    # 条件緩和: PBRを1.5に下げる
    condition3_relaxed = valid_data['PBR'] >= 1.5
    screened = valid_data[condition1 & condition2 & condition3_relaxed].copy()
    print(f"  条件緩和後（PBR≧1.5）: {len(screened)}銘柄")

# ソート（時価総額降順）
screened = screened.sort_values('MarketCap', ascending=False)

# 結果表示
print("\n[7] スクリーニング結果（上位30銘柄）")
print("="*80)
print(f"{'銘柄':>6} {'時価総額':>12} {'6M騰落率':>10} {'PBR':>8} {'営業利益率':>10}")
print("-"*80)

for idx, row in screened.head(30).iterrows():
    mc_str = f"{row['MarketCap']/1e8:.0f}億" if pd.notna(row['MarketCap']) else "N/A"
    op_margin_str = f"{row['OP_Margin']:.1f}%" if pd.notna(row['OP_Margin']) else "N/A"

    print(f"{row['Code']:>6} {mc_str:>12} {row['Return_6M']:>9.2f}% {row['PBR']:>7.2f} {op_margin_str:>10}")

# CSV保存
output_path = OUTPUT_DIR / "screened_stocks_corrected.csv"
screened.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"\n結果を保存: {output_path}")
print(f"合計 {len(screened)} 銘柄")

# サマリー統計
print("\n[8] サマリー統計")
print("="*80)
print(f"平均6ヶ月リターン: {screened['Return_6M'].mean():.2f}%")
print(f"中央値6ヶ月リターン: {screened['Return_6M'].median():.2f}%")
print(f"平均時価総額: {screened['MarketCap'].mean()/1e8:.0f}億円")
print(f"中央値時価総額: {screened['MarketCap'].median()/1e8:.0f}億円")
print(f"平均PBR: {screened['PBR'].mean():.2f}")
print(f"中央値PBR: {screened['PBR'].median():.2f}")
print(f"平均営業利益率: {screened['OP_Margin'].mean():.2f}%")

# リターン分布
print("\n[9] リターン分布")
print(f"  最小: {screened['Return_6M'].min():.2f}%")
print(f"  25%: {screened['Return_6M'].quantile(0.25):.2f}%")
print(f"  50%: {screened['Return_6M'].quantile(0.50):.2f}%")
print(f"  75%: {screened['Return_6M'].quantile(0.75):.2f}%")
print(f"  最大: {screened['Return_6M'].max():.2f}%")

print("\n完了")
