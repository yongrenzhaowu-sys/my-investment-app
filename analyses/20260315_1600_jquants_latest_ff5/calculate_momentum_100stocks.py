"""
既存100銘柄データでモメンタムを追加計算

既に取得済みのデータ（2016-03～2026-03-13）を使用
"""
import pandas as pd
import numpy as np
from pathlib import Path

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data/processed/jquants_latest"
OUTPUT_DIR = Path(__file__).parent

print("="*80)
print("FF5+モメンタムファクター計算（既存100銘柄データ）")
print("="*80)

# データ読み込み
print("\n[1] データ読み込み")
df_prices = pd.read_parquet(DATA_DIR / "daily_bars_2025_2026.parquet")
df_fins = pd.read_parquet(DATA_DIR / "financials_2025_2026.parquet")

print(f"  株価: {len(df_prices):,}レコード")
print(f"  財務: {len(df_fins):,}レコード")

# 日付型に変換
df_prices['Date'] = pd.to_datetime(df_prices['Date'])
df_fins['DiscDate'] = pd.to_datetime(df_fins['DiscDate'])

# Codeを4桁に統一
df_prices['Code'] = df_prices['Code'].str[:4]
df_fins['Code'] = df_fins['Code'].str[:4]

print(f"  株価期間: {df_prices['Date'].min()} ~ {df_prices['Date'].max()}")
print(f"  銘柄数: {df_prices['Code'].nunique()}")

# 月次リターン計算
print("\n[2] 月次リターン・モメンタム計算")
df_prices['YearMonth'] = df_prices['Date'].dt.to_period('M')
df_prices = df_prices.sort_values(['Code', 'Date'])

# 月末価格
month_end = df_prices.groupby(['Code', 'YearMonth']).tail(1).copy()
month_end = month_end.rename(columns={'Date': 'MonthEnd', 'AdjC': 'Price'})
month_end = month_end[['Code', 'YearMonth', 'MonthEnd', 'Price']].sort_values(['Code', 'YearMonth'])

# 月次リターン
month_end['PrevPrice'] = month_end.groupby('Code')['Price'].shift(1)
month_end['MonthlyReturn'] = (month_end['Price'] / month_end['PrevPrice']) - 1

# モメンタム: 過去6ヶ月リターン（t-7ヶ月 ~ t-1ヶ月）
month_end['Price_t7'] = month_end.groupby('Code')['Price'].shift(7)
month_end['Price_t1'] = month_end.groupby('Code')['Price'].shift(1)
month_end['Momentum_6M'] = (month_end['Price_t1'] / month_end['Price_t7']) - 1

print(f"  月次データ: {len(month_end):,}レコード")

# 財務データ処理
print("\n[3] 財務データ処理")
for col in ['Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS']:
    df_fins[col] = pd.to_numeric(df_fins[col], errors='coerce')

latest_fins = df_fins.sort_values('DiscDate').groupby('Code').last().reset_index()
latest_fins = latest_fins[['Code', 'DiscDate', 'Sales', 'OP', 'NP', 'Eq', 'TA', 'BPS']]

# マージ
month_end = month_end.merge(latest_fins, on='Code', how='left')

# ファクター計算
print("\n[4] ファクター値計算")
month_end['MarketCap'] = month_end['Price'] * (month_end['Eq'] / month_end['BPS'])
month_end['BM'] = month_end['Eq'] / month_end['MarketCap']
month_end['ROE'] = month_end['NP'] / month_end['Eq'] * 100
month_end['OP_Margin'] = month_end['OP'] / month_end['Sales'] * 100

# 投資（総資産成長率）
month_end = month_end.sort_values(['Code', 'YearMonth'])
month_end['TA_Prev'] = month_end.groupby('Code')['TA'].shift(4)
month_end['INV_Growth'] = (month_end['TA'] - month_end['TA_Prev']) / month_end['TA_Prev']

# FF5+モメンタムファクターリターン計算
print("\n[5] FF5+モメンタムファクターリターン計算")
factor_returns = []

# 2025年10月以降
target_months = month_end[month_end['MonthEnd'] >= '2025-10-01']['YearMonth'].unique()
print(f"  計算対象: {len(target_months)}ヶ月")

for ym in target_months:
    group = month_end[month_end['YearMonth'] == ym].copy()
    valid = group.dropna(subset=['MonthlyReturn', 'MarketCap', 'BM', 'ROE', 'Momentum_6M'])

    if len(valid) < 10:
        print(f"  {ym}: スキップ（データ不足）")
        continue

    # MKT
    mkt = valid['MonthlyReturn'].mean()

    # SMB
    median_mc = valid['MarketCap'].median()
    small = valid[valid['MarketCap'] <= median_mc]['MonthlyReturn'].mean()
    big = valid[valid['MarketCap'] > median_mc]['MonthlyReturn'].mean()
    smb = small - big

    # HML
    q33_bm = valid['BM'].quantile(0.33)
    q67_bm = valid['BM'].quantile(0.67)
    high_bm = valid[valid['BM'] >= q67_bm]['MonthlyReturn'].mean()
    low_bm = valid[valid['BM'] <= q33_bm]['MonthlyReturn'].mean()
    hml = high_bm - low_bm

    # RMW
    q33_roe = valid['ROE'].quantile(0.33)
    q67_roe = valid['ROE'].quantile(0.67)
    robust = valid[valid['ROE'] >= q67_roe]['MonthlyReturn'].mean()
    weak = valid[valid['ROE'] <= q33_roe]['MonthlyReturn'].mean()
    rmw = robust - weak

    # CMA
    valid_inv = valid.dropna(subset=['INV_Growth'])
    if len(valid_inv) >= 10:
        q33_inv = valid_inv['INV_Growth'].quantile(0.33)
        q67_inv = valid_inv['INV_Growth'].quantile(0.67)
        conservative = valid_inv[valid_inv['INV_Growth'] <= q33_inv]['MonthlyReturn'].mean()
        aggressive = valid_inv[valid_inv['INV_Growth'] >= q67_inv]['MonthlyReturn'].mean()
        cma = conservative - aggressive
    else:
        cma = np.nan

    # WML (モメンタム)
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

df_factors = pd.DataFrame(factor_returns)
df_factors = df_factors.sort_values('YearMonth')

# 結果表示
print("\n[6] 結果サマリー")
print("\nファクターリターン（月次）:")
print(df_factors[['MonthEnd', 'MKT', 'SMB', 'HML', 'RMW', 'CMA', 'WML', 'n_stocks']].to_string(index=False))

# 保存
output_path = OUTPUT_DIR / "ff5_momentum_100stocks.csv"
df_factors.to_csv(output_path, index=False)
print(f"\n[SUCCESS] 保存: {output_path}")

# 統計サマリー
print("\n[7] 統計サマリー（年率換算）")
print("="*80)
for factor in ['MKT', 'SMB', 'HML', 'RMW', 'CMA', 'WML']:
    data = df_factors[factor].dropna()
    if len(data) > 0:
        mean_annual = data.mean() * 12
        std_annual = data.std() * np.sqrt(12)
        sharpe = (data.mean() / data.std()) * np.sqrt(12) if data.std() > 0 else 0
        print(f"{factor}:")
        print(f"  年率リターン: {mean_annual:+.2%}")
        print(f"  年率ボラティリティ: {std_annual:.2%}")
        print(f"  シャープレシオ: {sharpe:+.2f}")
        print()

# ランキング
print("\n[8] 最終ランキング（シャープレシオ順）")
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

# 推奨戦略
print("\n[9] 推奨戦略（モメンタム追加版）")
print("="*80)
top3 = df_ranking.head(3)
print("\nTop 3ファクター:")
for i, row in enumerate(top3.itertuples(), 1):
    print(f"{i}. {row.Factor}: シャープ{row.SharpeRatio:+.2f}, 年率{row.AnnualReturn:+.2%}")

print("\n推奨スクリーニング条件:")
print("  ✅ 時価総額 > 1000億円（大型株優先）")
if 'RMW' in top3['Factor'].values:
    print("  ✅ ROE > 市場中央値（収益性）")
    print("  ✅ 営業利益率 > 市場中央値（収益性）")
if 'WML' in top3['Factor'].values:
    print("  ✅ 過去6ヶ月リターン > 市場中央値（モメンタム）")
if 'HML' in top3['Factor'].values:
    print("  ✅ PBR < 市場中央値（バリュー）")
else:
    print("  ❌ PBRによるバリュー選択は無効")

print("\n完了")
