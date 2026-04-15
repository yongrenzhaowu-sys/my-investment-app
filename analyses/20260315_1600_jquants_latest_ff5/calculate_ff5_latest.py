"""
最新データでFF5ファクターを簡易計算

既存データ（2016-2025/09）+ 新規データ（2025/10-2026/03）を結合して分析
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data/processed/jquants_latest"
OUTPUT_DIR = Path(__file__).parent

print("="*80)
print("FF5ファクター簡易計算（最新データ）")
print("="*80)

# 新規データ読み込み
print("\n[1] 新規データ読み込み")
df_prices = pd.read_parquet(DATA_DIR / "daily_bars_2025_2026.parquet")
df_fins = pd.read_parquet(DATA_DIR / "financials_2025_2026.parquet")

print(f"  株価: {len(df_prices):,}レコード")
print(f"  財務: {len(df_fins):,}レコード")

# 日付型に変換
df_prices['Date'] = pd.to_datetime(df_prices['Date'])
df_fins['DiscDate'] = pd.to_datetime(df_fins['DiscDate'])

# 2025年10月以降のみ抽出
df_prices_latest = df_prices[df_prices['Date'] >= '2025-10-01'].copy()
print(f"  最新株価（2025-10以降）: {len(df_prices_latest):,}レコード")

# 月次リターン計算
print("\n[2] 月次リターン計算")
df_prices_latest['YearMonth'] = df_prices_latest['Date'].dt.to_period('M')
df_prices_latest = df_prices_latest.sort_values(['Code', 'Date'])

# 月末価格
month_end = df_prices_latest.groupby(['Code', 'YearMonth']).tail(1).copy()
month_end = month_end.rename(columns={'Date': 'MonthEnd', 'AdjC': 'Price'})
month_end = month_end[['Code', 'YearMonth', 'MonthEnd', 'Price']].sort_values(['Code', 'YearMonth'])

# 月次リターン
month_end['PrevPrice'] = month_end.groupby('Code')['Price'].shift(1)
month_end['MonthlyReturn'] = (month_end['Price'] / month_end['PrevPrice']) - 1
month_end = month_end.dropna(subset=['MonthlyReturn'])

print(f"  月次リターン: {len(month_end):,}レコード")
print(f"  期間: {month_end['YearMonth'].min()} ~ {month_end['YearMonth'].max()}")

# 財務データの最新値取得
print("\n[3] 財務データ処理")
# 数値変換
df_fins['Sales'] = pd.to_numeric(df_fins['Sales'], errors='coerce')
df_fins['OP'] = pd.to_numeric(df_fins['OP'], errors='coerce')
df_fins['NP'] = pd.to_numeric(df_fins['NP'], errors='coerce')
df_fins['Eq'] = pd.to_numeric(df_fins['Eq'], errors='coerce')
df_fins['TA'] = pd.to_numeric(df_fins['TA'], errors='coerce')
df_fins['BPS'] = pd.to_numeric(df_fins['BPS'], errors='coerce')

# 各銘柄の最新財務データ
latest_fins = df_fins.sort_values('DiscDate').groupby('Code').last().reset_index()
latest_fins = latest_fins[['Code', 'DiscDate', 'Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS']]

print(f"  最新財務データ: {len(latest_fins)}銘柄")

# 月次データとマージ
print("\n[4] データマージ")
month_end = month_end.merge(latest_fins, on='Code', how='left')

# 時価総額計算（簡易版: Price * 推定発行済株式数）
# BPS（1株純資産）から逆算
month_end['MarketCap'] = month_end['Price'] * (month_end['Eq'] / month_end['BPS'])

# BM比率（Book-to-Market）
month_end['BM'] = month_end['Eq'] / month_end['MarketCap']

# ROE（自己資本利益率）
month_end['ROE'] = month_end['NP'] / month_end['Eq'] * 100

# 営業利益率
month_end['OP_Margin'] = month_end['OP'] / month_end['Sales'] * 100

print(f"  マージ後: {len(month_end):,}レコード")

# 簡易ファクター計算（各月ごと）
print("\n[5] 簡易ファクター計算")
factor_returns = []

for ym, group in month_end.groupby('YearMonth'):
    # 欠損値除外
    valid = group.dropna(subset=['MonthlyReturn', 'MarketCap', 'BM', 'ROE'])

    if len(valid) < 10:  # 最低10銘柄必要
        continue

    # MKT（市場リターン、等ウェイト）
    mkt = valid['MonthlyReturn'].mean()

    # SMB（Small Minus Big）
    median_mc = valid['MarketCap'].median()
    small = valid[valid['MarketCap'] <= median_mc]['MonthlyReturn'].mean()
    big = valid[valid['MarketCap'] > median_mc]['MonthlyReturn'].mean()
    smb = small - big

    # HML（High Minus Low BM）
    q33_bm = valid['BM'].quantile(0.33)
    q66_bm = valid['BM'].quantile(0.67)
    high_bm = valid[valid['BM'] >= q66_bm]['MonthlyReturn'].mean()
    low_bm = valid[valid['BM'] <= q33_bm]['MonthlyReturn'].mean()
    hml = high_bm - low_bm

    # RMW（Robust Minus Weak、ROEで代用）
    q33_roe = valid['ROE'].quantile(0.33)
    q66_roe = valid['ROE'].quantile(0.67)
    robust = valid[valid['ROE'] >= q66_roe]['MonthlyReturn'].mean()
    weak = valid[valid['ROE'] <= q33_roe]['MonthlyReturn'].mean()
    rmw = robust - weak

    # CMA（Conservative Minus Aggressive、簡易版スキップ）
    cma = np.nan

    # WML（モメンタム、簡易版スキップ）
    wml = np.nan

    factor_returns.append({
        'YearMonth': ym,
        'MonthEnd': valid['MonthEnd'].iloc[0],
        'MKT': mkt,
        'SMB': smb,
        'HML': hml,
        'RMW': rmw,
        'CMA': cma,
        'WML': wml,
        'n_stocks': len(valid)
    })

df_factors = pd.DataFrame(factor_returns)
df_factors = df_factors.sort_values('YearMonth')

print(f"  計算完了: {len(df_factors)}ヶ月")
print("\n最新ファクターリターン:")
print(df_factors[['MonthEnd', 'MKT', 'SMB', 'HML', 'RMW', 'n_stocks']].tail(10).to_string(index=False))

# 保存
output_path = OUTPUT_DIR / "ff5_factors_latest_simplified.csv"
df_factors.to_csv(output_path, index=False)
print(f"\n[SUCCESS] 保存完了: {output_path}")

# 統計サマリー
print("\n[6] 最新期間の統計（2025-10以降）")
recent = df_factors[df_factors['MonthEnd'] >= '2025-10-01']
if len(recent) > 0:
    for factor in ['MKT', 'SMB', 'HML', 'RMW']:
        mean = recent[factor].mean() * 12  # 年率換算
        print(f"  {factor}: 年率 {mean:+.2%}")
else:
    print("  データなし")

print("\n完了")
