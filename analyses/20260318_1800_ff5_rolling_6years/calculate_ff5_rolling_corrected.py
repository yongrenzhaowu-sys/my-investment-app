"""
5年間のFF5ファクターローリング分析（調整済み株価版）

重要な修正:
1. 調整済み株価を正しく計算（AdjC_Correct = C × AdjFactor）
2. 重複データの除外
3. グループ単位で高速処理

データ期間: 2021-03～2026-03
対象銘柄: 全銘柄
ウィンドウサイズ: 12ヶ月
スライド幅: 1ヶ月
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data/processed/jquants_historical_6years"
OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("="*80)
print("FF5ファクターローリング分析（調整済み株価版、2021-03～2026-03）")
print("="*80)

# データ読み込み
print("\n[1] データ読み込み")
df_prices = pd.read_parquet(DATA_DIR / "daily_bars_2021_2026.parquet")
df_fins = pd.read_parquet(DATA_DIR / "financials_2021_2026.parquet")

print(f"  株価: {len(df_prices):,}レコード")
print(f"  財務: {len(df_fins):,}レコード")

# 日付型に変換
df_prices['Date'] = pd.to_datetime(df_prices['Date'])
df_fins['DiscDate'] = pd.to_datetime(df_fins['DiscDate'])
df_fins['CurPerEn'] = pd.to_datetime(df_fins['CurPerEn'])

# Codeを4桁に統一
df_prices['Code'] = df_prices['Code'].str[:4]
df_fins['Code'] = df_fins['Code'].str[:4]

# 【重要】調整済み株価を正しく計算
print("\n[2] 調整済み株価を正しく計算")
print(f"  修正前のAdjC = C: {(df_prices['AdjC'] == df_prices['C']).sum():,}レコード")

df_prices['AdjC_Correct'] = df_prices['C'] * df_prices['AdjFactor']
df_prices['Price'] = df_prices['AdjC_Correct']

print(f"  修正後: Price = C × AdjFactor")
print(f"  調整係数が1.0でないレコード: {(df_prices['AdjFactor'] != 1.0).sum():,}レコード")

# 重複データの除外（同じCode×Dateで複数レコードがある場合）
print("\n[3] 重複データの除外")
before_count = len(df_prices)

# 同じCode×Dateの中で、最も取引量が多いレコードを採用
df_prices = df_prices.sort_values(['Code', 'Date', 'Vo'], ascending=[True, True, False])
df_prices = df_prices.drop_duplicates(subset=['Code', 'Date'], keep='first')

after_count = len(df_prices)
print(f"  除外前: {before_count:,}レコード")
print(f"  除外後: {after_count:,}レコード")
print(f"  除外数: {before_count - after_count:,}レコード")

print(f"  株価銘柄数: {df_prices['Code'].nunique()}")
print(f"  財務銘柄数: {df_fins['Code'].nunique()}")

# 月次リターン計算
print("\n[4] 月次リターン計算")
df_prices['YearMonth'] = df_prices['Date'].dt.to_period('M')
df_prices = df_prices.sort_values(['Code', 'Date'])

# 月末価格
month_end = df_prices.groupby(['Code', 'YearMonth']).tail(1).copy()
month_end = month_end.rename(columns={'Date': 'MonthEnd'})
month_end = month_end[['Code', 'YearMonth', 'MonthEnd', 'Price']].sort_values(['Code', 'YearMonth'])

# 月次リターン
month_end['PrevPrice'] = month_end.groupby('Code')['Price'].shift(1)
month_end['MonthlyReturn'] = (month_end['Price'] / month_end['PrevPrice']) - 1

# モメンタム計算
print("\n[5] モメンタム計算")
month_end['Price_t7'] = month_end.groupby('Code')['Price'].shift(7)
month_end['Price_t1'] = month_end.groupby('Code')['Price'].shift(1)
month_end['Momentum_6M'] = (month_end['Price_t1'] / month_end['Price_t7']) - 1

print(f"  月次データ: {len(month_end):,}レコード")
print(f"  対象銘柄: 全銘柄（{month_end['Code'].nunique()}銘柄）")

# 財務データ処理（BPS代替計算）
print("\n[6] 財務データ処理（BPS代替計算）")
for col in ['Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS', 'ShOutFY', 'TrShFY', 'AvgSh']:
    df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

# BPS代替計算
df_fins['SharesOut'] = df_fins['ShOutFY'].fillna(df_fins['TrShFY']).fillna(df_fins['AvgSh'])
df_fins['BPS_Calc'] = df_fins['Eq'] / df_fins['SharesOut']
df_fins['BPS_Final'] = df_fins['BPS'].fillna(df_fins['BPS_Calc'])

print(f"  BPS有効数: {df_fins['BPS_Final'].notna().sum()}")

# INV_Growth計算
print("\n[7] INV_Growth計算")
df_fins = df_fins.sort_values(['Code', 'DiscDate'])
df_fins['TA_Prev'] = df_fins.groupby('Code')['TA'].shift(1)
df_fins['CurPerEn_Prev'] = df_fins.groupby('Code')['CurPerEn'].shift(1)
df_fins['Days'] = (df_fins['CurPerEn'] - df_fins['CurPerEn_Prev']).dt.days
df_fins['INV_Growth_Raw'] = (df_fins['TA'] - df_fins['TA_Prev']) / df_fins['TA_Prev']
df_fins['INV_Growth'] = df_fins['INV_Growth_Raw'] * (365 / df_fins['Days'])
df_fins.loc[(df_fins['INV_Growth'] < -1) | (df_fins['INV_Growth'] > 1), 'INV_Growth'] = np.nan

print(f"  INV_Growth有効数: {df_fins['INV_Growth'].notna().sum()}")

# データマージ（グループ単位で処理）
print("\n[8] データマージ（グループ単位処理）")

# 月末日付から3ヶ月前の日付を計算
month_end['ThreeMonthsBefore'] = month_end['MonthEnd'] - pd.Timedelta(days=90)

# 銘柄ごとにグループ化してマージ
merged_list = []
codes = month_end['Code'].unique()
total_codes = len(codes)

print(f"  対象銘柄数: {total_codes}")

for i, code in enumerate(codes):
    # 銘柄ごとのデータを抽出
    month_data = month_end[month_end['Code'] == code].copy()
    fin_data = df_fins[df_fins['Code'] == code].copy()

    if len(fin_data) == 0:
        continue

    # 日付でソート
    month_data = month_data.sort_values('ThreeMonthsBefore')
    fin_data = fin_data.sort_values('DiscDate')

    # merge_asof（銘柄単位なのでbyパラメータ不要）
    merged_code = pd.merge_asof(
        month_data,
        fin_data[['DiscDate', 'Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS_Final', 'INV_Growth']],
        left_on='ThreeMonthsBefore',
        right_on='DiscDate',
        direction='backward'
    )

    merged_list.append(merged_code)

    # 進捗表示（500銘柄ごと）
    if (i + 1) % 500 == 0:
        print(f"  進捗: {i+1}/{total_codes}銘柄処理完了")

# 結合
merged = pd.concat(merged_list, ignore_index=True)

# 列名を整理
merged = merged.rename(columns={'BPS_Final': 'BPS'})
if 'DiscDate' in merged.columns:
    merged = merged.drop(columns=['DiscDate'])
if 'ThreeMonthsBefore' in merged.columns:
    merged = merged.drop(columns=['ThreeMonthsBefore'])

print(f"  マージ後: {len(merged):,}レコード")
print(f"  財務データ付き: {merged['BPS'].notna().sum():,}レコード")

# ファクター計算
print("\n[9] ファクター値計算")

# 時価総額
merged['MarketCap'] = merged['Price'] * (merged['Eq'] / merged['BPS'])

# BM比率
merged['BM'] = merged['Eq'] / merged['MarketCap']

# ROE
merged['ROE'] = merged['NP'] / merged['Eq'] * 100

# 営業利益率
merged['OP_Margin'] = merged['OP'] / merged['Sales'] * 100

print(f"  ファクター計算完了")
print(f"  MarketCap有効: {merged['MarketCap'].notna().sum()}レコード")

# ローリングウィンドウ分析（1ヶ月スライド）
print("\n[10] ローリングウィンドウ分析（12ヶ月ウィンドウ、1ヶ月スライド）")

all_months = sorted(merged['YearMonth'].unique())
print(f"  全期間: {all_months[0]} ~ {all_months[-1]} ({len(all_months)}ヶ月)")

# 12ヶ月ウィンドウ、1ヶ月スライド
windows = []
for i in range(len(all_months) - 11):  # 12ヶ月ウィンドウなので-11
    window_start = all_months[i]
    window_end = all_months[i + 11]
    windows.append({
        'window_id': i + 1,
        'start': window_start,
        'end': window_end,
        'months': all_months[i:i+12]
    })

print(f"  ウィンドウ数: {len(windows)}")

# 各ウィンドウでFF5+WMLファクター計算
rolling_results = []

for w in windows:
    window_data = merged[merged['YearMonth'].isin(w['months'])].copy()
    valid = window_data.dropna(subset=['MonthlyReturn', 'MarketCap', 'BM', 'ROE', 'Momentum_6M'])

    if len(valid) < 50:
        print(f"  ウィンドウ{w['window_id']} ({w['start']}～{w['end']}): スキップ（データ不足）")
        continue

    # MKT（市場リターン）
    mkt = valid['MonthlyReturn'].mean() * 12

    # SMB
    median_mc = valid['MarketCap'].median()
    small = valid[valid['MarketCap'] <= median_mc]['MonthlyReturn'].mean() * 12
    big = valid[valid['MarketCap'] > median_mc]['MonthlyReturn'].mean() * 12
    smb = small - big

    # HML
    q33_bm = valid['BM'].quantile(0.33)
    q67_bm = valid['BM'].quantile(0.67)
    high_bm = valid[valid['BM'] >= q67_bm]['MonthlyReturn'].mean() * 12
    low_bm = valid[valid['BM'] <= q33_bm]['MonthlyReturn'].mean() * 12
    hml = high_bm - low_bm

    # RMW
    q33_roe = valid['ROE'].quantile(0.33)
    q67_roe = valid['ROE'].quantile(0.67)
    robust = valid[valid['ROE'] >= q67_roe]['MonthlyReturn'].mean() * 12
    weak = valid[valid['ROE'] <= q33_roe]['MonthlyReturn'].mean() * 12
    rmw = robust - weak

    # CMA
    valid_inv = valid.dropna(subset=['INV_Growth'])
    if len(valid_inv) >= 50:
        q33_inv = valid_inv['INV_Growth'].quantile(0.33)
        q67_inv = valid_inv['INV_Growth'].quantile(0.67)
        conservative = valid_inv[valid_inv['INV_Growth'] <= q33_inv]['MonthlyReturn'].mean() * 12
        aggressive = valid_inv[valid_inv['INV_Growth'] >= q67_inv]['MonthlyReturn'].mean() * 12
        cma = conservative - aggressive
    else:
        cma = np.nan

    # WML
    q33_mom = valid['Momentum_6M'].quantile(0.33)
    q67_mom = valid['Momentum_6M'].quantile(0.67)
    winners = valid[valid['Momentum_6M'] >= q67_mom]['MonthlyReturn'].mean() * 12
    losers = valid[valid['Momentum_6M'] <= q33_mom]['MonthlyReturn'].mean() * 12
    wml = winners - losers

    rolling_results.append({
        'window_id': w['window_id'],
        'window_start': str(w['start']),
        'window_end': str(w['end']),
        'MKT': mkt,
        'SMB': smb,
        'HML': hml,
        'RMW': rmw,
        'CMA': cma,
        'WML': wml,
        'n_stocks': len(valid),
        'n_inv_valid': len(valid_inv)
    })

    if w['window_id'] % 5 == 0:
        print(f"  ウィンドウ{w['window_id']}/{len(windows)} ({w['start']}～{w['end']}): 完了（{len(valid)}銘柄）")

df_rolling = pd.DataFrame(rolling_results)
print(f"\n  計算完了: {len(df_rolling)}ウィンドウ")

# 保存
print("\n[11] 結果保存")
output_path = OUTPUT_DIR / "ff5_rolling_factors_corrected.csv"
df_rolling.to_csv(output_path, index=False)
print(f"  保存完了: {output_path}")

# サマリー
print("\n[12] サマリー（全期間平均）")
print("="*80)
for factor in ['MKT', 'SMB', 'HML', 'RMW', 'CMA', 'WML']:
    data = df_rolling[factor].dropna()
    if len(data) > 0:
        mean_return = data.mean()
        std_return = data.std()
        sharpe = mean_return / std_return if std_return > 0 else 0

        print(f"{factor}:")
        print(f"  平均年率リターン: {mean_return:+.2%}")
        print(f"  標準偏差: {std_return:.2%}")
        print(f"  シャープレシオ: {sharpe:.2f}")
        print()

print("完了")
