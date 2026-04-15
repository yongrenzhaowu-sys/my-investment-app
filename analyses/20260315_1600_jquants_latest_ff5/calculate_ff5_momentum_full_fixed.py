"""
全銘柄データでFF5+モメンタムファクターを完全計算（CMA修正版）

修正点:
- 各時点で利用可能な財務データを使用（最新財務データを使い回さない）
- INV_Growth計算を財務データの時系列から行う
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data/processed/jquants_latest_full"
OUTPUT_DIR = Path(__file__).parent

print("="*80)
print("FF5+モメンタムファクター完全計算（全銘柄、CMA修正版）")
print("="*80)

# データ読み込み
print("\n[1] データ読み込み")
df_prices = pd.read_parquet(DATA_DIR / "daily_bars_full.parquet")
df_fins = pd.read_parquet(DATA_DIR / "financials_full.parquet")

print(f"  株価: {len(df_prices):,}レコード")
print(f"  財務: {len(df_fins):,}レコード")

# 日付型に変換
df_prices['Date'] = pd.to_datetime(df_prices['Date'])
df_fins['DiscDate'] = pd.to_datetime(df_fins['DiscDate'])
df_fins['CurPerEn'] = pd.to_datetime(df_fins['CurPerEn'])

# Codeを4桁に統一
df_prices['Code'] = df_prices['Code'].str[:4]
df_fins['Code'] = df_fins['Code'].str[:4]

print(f"  株価銘柄数: {df_prices['Code'].nunique()}")
print(f"  財務銘柄数: {df_fins['Code'].nunique()}")
print(f"  株価期間: {df_prices['Date'].min()} ~ {df_prices['Date'].max()}")
print(f"  財務期間: {df_fins['DiscDate'].min()} ~ {df_fins['DiscDate'].max()}")

# 月次リターン計算
print("\n[2] 月次リターン計算")
df_prices['YearMonth'] = df_prices['Date'].dt.to_period('M')
df_prices = df_prices.sort_values(['Code', 'Date'])

# 月末価格
month_end = df_prices.groupby(['Code', 'YearMonth']).tail(1).copy()
month_end = month_end.rename(columns={'Date': 'MonthEnd', 'AdjC': 'Price'})
month_end = month_end[['Code', 'YearMonth', 'MonthEnd', 'Price']].sort_values(['Code', 'YearMonth'])

# 月次リターン
month_end['PrevPrice'] = month_end.groupby('Code')['Price'].shift(1)
month_end['MonthlyReturn'] = (month_end['Price'] / month_end['PrevPrice']) - 1

# モメンタム計算（過去6ヶ月リターン、t-7 ~ t-1）
print("\n[3] モメンタム計算（過去6ヶ月リターン）")
month_end['Price_t7'] = month_end.groupby('Code')['Price'].shift(7)
month_end['Price_t1'] = month_end.groupby('Code')['Price'].shift(1)
month_end['Momentum_6M'] = (month_end['Price_t1'] / month_end['Price_t7']) - 1

print(f"  月次データ: {len(month_end):,}レコード")
print(f"  期間: {month_end['YearMonth'].min()} ~ {month_end['YearMonth'].max()}")

# 財務データ処理（修正版：時系列データを保持）
print("\n[4] 財務データ処理（時系列保持）")
for col in ['Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS']:
    df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

# 財務データに決算期を追加
df_fins['FiscalQuarter'] = df_fins['CurPerEn'].dt.to_period('Q')

# 総資産成長率を計算（前年同期比）
print("\n[5] INV_Growth計算（前年同期比）")
df_fins = df_fins.sort_values(['Code', 'CurPerEn'])

# 前年同期のTA
df_fins['TA_YoY'] = df_fins.groupby('Code')['TA'].shift(4)  # 4四半期前
df_fins['INV_Growth'] = (df_fins['TA'] - df_fins['TA_YoY']) / df_fins['TA_YoY']

print(f"  INV_Growth有効数: {df_fins['INV_Growth'].notna().sum()} / {len(df_fins)}")

# 財務データと月次データをマージ（各時点で最新の財務データを使用）
print("\n[6] データマージ（各時点で最新の財務データ）")

# 各月末時点で利用可能な最新財務データを取得
merged_data = []

for idx, row in month_end.iterrows():
    code = row['Code']
    month_end_date = row['MonthEnd']

    # この時点で利用可能な財務データ（開示日が月末以前）
    available_fins = df_fins[(df_fins['Code'] == code) & (df_fins['DiscDate'] <= month_end_date)]

    if len(available_fins) > 0:
        # 最新の財務データを取得
        latest = available_fins.sort_values('DiscDate').iloc[-1]

        merged_data.append({
            'Code': row['Code'],
            'YearMonth': row['YearMonth'],
            'MonthEnd': row['MonthEnd'],
            'Price': row['Price'],
            'MonthlyReturn': row['MonthlyReturn'],
            'Momentum_6M': row['Momentum_6M'],
            'Sales': latest['Sales'],
            'OP': latest['OP'],
            'NP': latest['NP'],
            'Eq': latest['Eq'],
            'TA': latest['TA'],
            'BPS': latest['BPS'],
            'INV_Growth': latest['INV_Growth']
        })

df_merged = pd.DataFrame(merged_data)
print(f"  マージ後: {len(df_merged):,}レコード")

# ファクター計算
print("\n[7] ファクター値計算")

# 時価総額
df_merged['MarketCap'] = df_merged['Price'] * (df_merged['Eq'] / df_merged['BPS'])

# BM比率
df_merged['BM'] = df_merged['Eq'] / df_merged['MarketCap']

# ROE
df_merged['ROE'] = df_merged['NP'] / df_merged['Eq'] * 100

# 営業利益率
df_merged['OP_Margin'] = df_merged['OP'] / df_merged['Sales'] * 100

print(f"  ファクター計算完了")

# FF5+モメンタムファクターリターン計算
print("\n[8] FF5+モメンタムファクターリターン計算")
factor_returns = []

# 2025年10月以降のみ計算
target_months = df_merged[df_merged['MonthEnd'] >= '2025-10-01']['YearMonth'].unique()
print(f"  計算対象: {len(target_months)}ヶ月")

for ym in target_months:
    group = df_merged[df_merged['YearMonth'] == ym].copy()

    # 欠損値除外
    valid = group.dropna(subset=['MonthlyReturn', 'MarketCap', 'BM', 'ROE', 'Momentum_6M'])

    if len(valid) < 50:
        print(f"  {ym}: スキップ（データ不足: {len(valid)}銘柄）")
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
    q67_bm = valid['BM'].quantile(0.67)
    high_bm = valid[valid['BM'] >= q67_bm]['MonthlyReturn'].mean()
    low_bm = valid[valid['BM'] <= q33_bm]['MonthlyReturn'].mean()
    hml = high_bm - low_bm

    # RMW（Robust Minus Weak）
    q33_roe = valid['ROE'].quantile(0.33)
    q67_roe = valid['ROE'].quantile(0.67)
    robust = valid[valid['ROE'] >= q67_roe]['MonthlyReturn'].mean()
    weak = valid[valid['ROE'] <= q33_roe]['MonthlyReturn'].mean()
    rmw = robust - weak

    # CMA（Conservative Minus Aggressive）修正版
    valid_inv = valid.dropna(subset=['INV_Growth'])
    if len(valid_inv) >= 50:
        q33_inv = valid_inv['INV_Growth'].quantile(0.33)
        q67_inv = valid_inv['INV_Growth'].quantile(0.67)
        conservative = valid_inv[valid_inv['INV_Growth'] <= q33_inv]['MonthlyReturn'].mean()
        aggressive = valid_inv[valid_inv['INV_Growth'] >= q67_inv]['MonthlyReturn'].mean()
        cma = conservative - aggressive
    else:
        cma = np.nan

    # WML（Winners Minus Losers、モメンタム）
    q33_mom = valid['Momentum_6M'].quantile(0.33)
    q67_mom = valid['Momentum_6M'].quantile(0.67)
    winners = valid[valid['Momentum_6M'] >= q67_mom]['MonthlyReturn'].mean()
    losers = valid[valid['Momentum_6M'] <= q33_mom]['MonthlyReturn'].mean()
    wml = winners - losers

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

    print(f"  {ym}: 完了（{len(valid)}銘柄、INV有効: {len(valid_inv)}銘柄）")

df_factors = pd.DataFrame(factor_returns)
df_factors = df_factors.sort_values('YearMonth')

print(f"\n  計算完了: {len(df_factors)}ヶ月")

# 結果表示
print("\n[9] 結果サマリー")
print("\n最新ファクターリターン（月次）:")
print(df_factors[['MonthEnd', 'MKT', 'SMB', 'HML', 'RMW', 'CMA', 'WML', 'n_stocks']].to_string(index=False))

# 保存
output_path = OUTPUT_DIR / "ff5_momentum_factors_full.csv"
df_factors.to_csv(output_path, index=False)
print(f"\n[SUCCESS] 保存完了: {output_path}")

# 統計サマリー
print("\n[10] 統計サマリー（年率換算）")
print("="*80)
for factor in ['MKT', 'SMB', 'HML', 'RMW', 'CMA', 'WML']:
    data = df_factors[factor].dropna()
    if len(data) > 0:
        mean_monthly = data.mean()
        std_monthly = data.std()
        mean_annual = mean_monthly * 12
        std_annual = std_monthly * np.sqrt(12)
        sharpe = (mean_monthly / std_monthly) * np.sqrt(12) if std_monthly > 0 else 0

        print(f"{factor}:")
        print(f"  年率リターン: {mean_annual:+.2%}")
        print(f"  年率ボラティリティ: {std_annual:.2%}")
        print(f"  シャープレシオ: {sharpe:.2f}")
        print()

# 最終ランキング
print("\n[11] 最終ランキング（シャープレシオ順）")
print("="*80)
ranking = []
for factor in ['MKT', 'SMB', 'HML', 'RMW', 'CMA', 'WML']:
    data = df_factors[factor].dropna()
    if len(data) > 0:
        mean_annual = data.mean() * 12
        sharpe = (data.mean() / data.std()) * np.sqrt(12) if data.std() > 0 else 0
        ranking.append({
            'Factor': factor,
            'AnnualReturn': mean_annual,
            'SharpeRatio': sharpe
        })

df_ranking = pd.DataFrame(ranking).sort_values('SharpeRatio', ascending=False)
print(df_ranking.to_string(index=False))

# CSV保存
ranking_path = OUTPUT_DIR / "ff5_momentum_ranking_full.csv"
df_ranking.to_csv(ranking_path, index=False)
print(f"\n[SUCCESS] ランキング保存: {ranking_path}")

print("\n完了")
