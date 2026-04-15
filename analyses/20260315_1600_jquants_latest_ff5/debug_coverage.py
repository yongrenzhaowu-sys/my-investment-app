"""
銘柄カバレッジが低い原因を調査

なぜ約1,000銘柄しかカバーできないのか詳細分析
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data/processed/jquants_latest_full"

print("="*80)
print("銘柄カバレッジ調査")
print("="*80)

# データ読み込み
df_prices = pd.read_parquet(DATA_DIR / "daily_bars_full.parquet")
df_fins = pd.read_parquet(DATA_DIR / "financials_full.parquet")

# 日付型に変換
df_prices['Date'] = pd.to_datetime(df_prices['Date'])
df_fins['DiscDate'] = pd.to_datetime(df_fins['DiscDate'])
df_fins['CurPerEn'] = pd.to_datetime(df_fins['CurPerEn'])

# Codeを4桁に統一
df_prices['Code'] = df_prices['Code'].str[:4]
df_fins['Code'] = df_fins['Code'].str[:4]

print(f"\n[1] 元データの銘柄数")
print(f"  株価データ: {df_prices['Code'].nunique()}銘柄")
print(f"  財務データ: {df_fins['Code'].nunique()}銘柄")

# 月次リターン計算
df_prices['YearMonth'] = df_prices['Date'].dt.to_period('M')
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

# 2025-10のデータで調査
target_date = pd.Timestamp('2025-10-31')
ym = pd.Period('2025-10')

print(f"\n[2] 2025-10の月次データ")
group = month_end[month_end['YearMonth'] == ym].copy()
print(f"  月次データ銘柄数: {len(group)}銘柄")
print(f"  MonthlyReturn有効: {group['MonthlyReturn'].notna().sum()}銘柄")
print(f"  Momentum_6M有効: {group['Momentum_6M'].notna().sum()}銘柄")

# 財務データマージ
print(f"\n[3] 財務データマージ（3ヶ月前まで）")
three_months_before = target_date - timedelta(days=90)
print(f"  基準日: {target_date}")
print(f"  3ヶ月前: {three_months_before}")

# 各銘柄の利用可能な財務データ
merged_count = 0
merged_codes = []

for code in group['Code'].unique():
    available_fins = df_fins[(df_fins['Code'] == code) & (df_fins['DiscDate'] <= three_months_before)]
    if len(available_fins) > 0:
        merged_count += 1
        merged_codes.append(code)

print(f"  財務データ利用可能な銘柄数: {merged_count}銘柄")

# マージ処理
merged_data = []
for idx, row in group.iterrows():
    code = row['Code']
    available_fins = df_fins[(df_fins['Code'] == code) & (df_fins['DiscDate'] <= three_months_before)]

    if len(available_fins) > 0:
        latest = available_fins.sort_values('DiscDate').iloc[-1]
        merged_data.append({
            'Code': row['Code'],
            'MonthlyReturn': row['MonthlyReturn'],
            'Momentum_6M': row['Momentum_6M'],
            'Price': row['Price'],
            'Sales': latest['Sales'],
            'OP': latest['OP'],
            'NP': latest['NP'],
            'Eq': latest['Eq'],
            'TA': latest['TA'],
            'BPS': latest['BPS']
        })

df_merged = pd.DataFrame(merged_data)
print(f"  マージ後レコード数: {len(df_merged)}銘柄")

# ファクター計算
df_merged['MarketCap'] = df_merged['Price'] * (df_merged['Eq'] / df_merged['BPS'])
df_merged['BM'] = df_merged['Eq'] / df_merged['MarketCap']
df_merged['ROE'] = df_merged['NP'] / df_merged['Eq'] * 100

print(f"\n[4] ファクター計算後の有効数")
print(f"  MarketCap有効: {df_merged['MarketCap'].notna().sum()}銘柄")
print(f"  BM有効: {df_merged['BM'].notna().sum()}銘柄")
print(f"  ROE有効: {df_merged['ROE'].notna().sum()}銘柄")

# 欠損値除外
print(f"\n[5] 欠損値除外（valid計算）")
print(f"  対象: {len(df_merged)}銘柄")

# ステップごとに除外数を確認
step1 = df_merged['MonthlyReturn'].notna()
print(f"  MonthlyReturn有効: {step1.sum()}銘柄（-{(~step1).sum()}銘柄）")

step2 = step1 & df_merged['MarketCap'].notna()
print(f"  + MarketCap有効: {step2.sum()}銘柄（-{(step1 & ~step2).sum()}銘柄）")

step3 = step2 & df_merged['BM'].notna()
print(f"  + BM有効: {step3.sum()}銘柄（-{(step2 & ~step3).sum()}銘柄）")

step4 = step3 & df_merged['ROE'].notna()
print(f"  + ROE有効: {step4.sum()}銘柄（-{(step3 & ~step4).sum()}銘柄）")

step5 = step4 & df_merged['Momentum_6M'].notna()
print(f"  + Momentum_6M有効: {step5.sum()}銘柄（-{(step4 & ~step5).sum()}銘柄）")

valid = df_merged[step5]
print(f"\n  最終的なvalid銘柄数: {len(valid)}銘柄")

# 各財務指標の欠損の原因
print(f"\n[6] 財務データ欠損の詳細分析")

# Eq（自己資本）の欠損
eq_missing = df_merged['Eq'].isna().sum()
print(f"  Eq（自己資本）欠損: {eq_missing}銘柄")

# BPS（1株あたり純資産）の欠損
bps_missing = df_merged['BPS'].isna().sum()
print(f"  BPS（1株あたり純資産）欠損: {bps_missing}銘柄")

# NP（純利益）の欠損
np_missing = df_merged['NP'].isna().sum()
print(f"  NP（純利益）欠損: {np_missing}銘柄")

# MarketCap計算失敗の原因
mc_fail = df_merged['MarketCap'].isna()
mc_fail_eq = mc_fail & df_merged['Eq'].isna()
mc_fail_bps = mc_fail & df_merged['BPS'].isna()
mc_fail_both = mc_fail & df_merged['Eq'].isna() & df_merged['BPS'].isna()
mc_fail_calc = mc_fail & df_merged['Eq'].notna() & df_merged['BPS'].notna()

print(f"\n  MarketCap計算失敗の内訳:")
print(f"    Eq欠損: {mc_fail_eq.sum()}銘柄")
print(f"    BPS欠損: {mc_fail_bps.sum()}銘柄")
print(f"    両方欠損: {mc_fail_both.sum()}銘柄")
print(f"    計算エラー（BPS=0など）: {mc_fail_calc.sum()}銘柄")

# サンプル表示（欠損が多い銘柄）
print(f"\n[7] サンプル: 財務データ欠損の例")
missing_sample = df_merged[df_merged['Eq'].isna() | df_merged['BPS'].isna() | df_merged['NP'].isna()].head(5)
if len(missing_sample) > 0:
    print(missing_sample[['Code', 'Sales', 'Eq', 'BPS', 'NP']].to_string(index=False))

print("\n" + "="*80)
