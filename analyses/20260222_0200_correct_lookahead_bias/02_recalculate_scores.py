# -*- coding: utf-8 -*-
"""
prediction_scores.csvのルックアヘッドバイアスを修正

重要な修正:
1. return_1M, return_3M, return_6M: 未来のリターン → 過去のリターンに修正
2. custom_growth_rate: 計算方法を確認し、必要なら修正
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import io

# 標準出力をUTF-8に設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("ルックアヘッドバイアスの修正: スコアデータ再計算")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/4] データ読み込み...")

# 価格データ
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()
print(f"価格データ: {len(df_price):,} 行")

# 財務データ
df_fin = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin['disclosed_date'] = pd.to_datetime(df_fin['disclosed_date'])
df_fin = df_fin[df_fin['disclosed_date'] >= '2016-01-01'].copy()

# 年次決算のみ
if 'fiscal_quarter' in df_fin.columns:
    df_fin = df_fin[df_fin['fiscal_quarter'] == 'FY'].copy()

print(f"財務データ: {len(df_fin):,} 行")

# 既存のスコアデータ（構造を参照するため）
df_old_scores = pd.read_csv(
    PROJECT_ROOT / 'analyses/growth_yield_prediction/prediction_scores.csv',
    dtype={'code': str}
)
df_old_scores['disclosed_date'] = pd.to_datetime(df_old_scores['disclosed_date'])

print(f"既存スコアデータ: {len(df_old_scores):,} 行")

# ================================================================================
# 2. 過去のリターンを正しく計算
# ================================================================================

print("\n[2/4] 過去のリターンを計算...")

# 価格データをピボット（高速化のため）
print("  価格データをピボット中...")
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

# 各財務開示日時点での過去のリターンを計算
results = []
total_rows = len(df_old_scores)

print(f"  {total_rows:,} 行を処理中...")

for idx, row in df_old_scores.iterrows():
    if idx % 1000 == 0:
        print(f"    進捗: {idx:,} / {total_rows:,} ({idx/total_rows*100:.1f}%)")

    code = row['code']
    disclosed_date = row['disclosed_date']

    # この銘柄の価格データ
    if code not in df_price_pivot.columns:
        continue

    price_series = df_price_pivot[code].dropna()

    # disclosed_date時点の価格
    prices_at_disclosed = price_series[price_series.index <= disclosed_date]
    if len(prices_at_disclosed) == 0:
        continue

    price_at_disclosed = prices_at_disclosed.iloc[-1]
    date_at_disclosed = prices_at_disclosed.index[-1]

    # 過去1ヶ月のリターン
    date_1m_before = disclosed_date - pd.Timedelta(days=30)
    prices_1m_before = price_series[price_series.index <= date_1m_before]
    if len(prices_1m_before) > 0:
        price_1m_before = prices_1m_before.iloc[-1]
        return_1m = (price_at_disclosed - price_1m_before) / price_1m_before
    else:
        return_1m = np.nan

    # 過去3ヶ月のリターン
    date_3m_before = disclosed_date - pd.Timedelta(days=90)
    prices_3m_before = price_series[price_series.index <= date_3m_before]
    if len(prices_3m_before) > 0:
        price_3m_before = prices_3m_before.iloc[-1]
        return_3m = (price_at_disclosed - price_3m_before) / price_3m_before
    else:
        return_3m = np.nan

    # 過去6ヶ月のリターン
    date_6m_before = disclosed_date - pd.Timedelta(days=180)
    prices_6m_before = price_series[price_series.index <= date_6m_before]
    if len(prices_6m_before) > 0:
        price_6m_before = prices_6m_before.iloc[-1]
        return_6m = (price_at_disclosed - price_6m_before) / price_6m_before
    else:
        return_6m = np.nan

    # 元のデータをコピーし、リターンのみ更新
    new_row = row.copy()
    new_row['return_1M'] = return_1m
    new_row['return_3M'] = return_3m
    new_row['return_6M'] = return_6m

    results.append(new_row)

df_corrected = pd.DataFrame(results)

print(f"\n  完了: {len(df_corrected):,} 行を生成")

# ================================================================================
# 3. custom_growth_rateの確認
# ================================================================================

print("\n[3/4] custom_growth_rateの確認...")

# custom_growth_rateがどのように計算されているか推測
# おそらく: (current_profit - previous_year_profit) / previous_year_profit

sample = df_corrected[['code', 'disclosed_date', 'current_profit', 'previous_year_profit', 'custom_growth_rate']].head(10)
print("\nサンプルデータ:")
print(sample)

# 計算してみる
if len(df_corrected) > 0:
    df_corrected['calculated_growth'] = (df_corrected['current_profit'] - df_corrected['previous_year_profit']) / df_corrected['previous_year_profit'].replace(0, np.nan)

    # 比較
    comparison = df_corrected[['custom_growth_rate', 'calculated_growth']].head(10)
    print("\n元のcustom_growth_rateと計算結果の比較:")
    print(comparison)

    # 相関係数
    corr = df_corrected[['custom_growth_rate', 'calculated_growth']].corr().iloc[0, 1]
    print(f"\n相関係数: {corr:.4f}")

    if corr > 0.99:
        print("=> custom_growth_rateは利益成長率として計算されている（問題なし）")
    else:
        print("=> custom_growth_rateの計算方法が不明（要確認）")

# ================================================================================
# 4. 保存
# ================================================================================

print("\n[4/4] 保存...")

output_dir = PROJECT_ROOT / 'analyses' / '20260222_0200_correct_lookahead_bias'
output_dir.mkdir(exist_ok=True, parents=True)

# 修正後のデータを保存
df_corrected.to_csv(output_dir / 'prediction_scores_corrected.csv', index=False, encoding='utf-8-sig')

print(f"\n保存完了: {output_dir / 'prediction_scores_corrected.csv'}")
print(f"行数: {len(df_corrected):,}")

# 統計サマリー
print("\n" + "="*80)
print("修正後のreturn_6M統計:")
print("="*80)
print(df_corrected['return_6M'].describe())

print("\n元のreturn_6M統計（参考）:")
print(df_old_scores['return_6M'].describe())

# 比較
print("\n" + "="*80)
print("修正前後の比較:")
print("="*80)

old_mean = df_old_scores['return_6M'].mean()
new_mean = df_corrected['return_6M'].mean()
old_median = df_old_scores['return_6M'].median()
new_median = df_corrected['return_6M'].median()

print(f"平均:")
print(f"  修正前: {old_mean*100:.2f}%")
print(f"  修正後: {new_mean*100:.2f}%")
print(f"  差: {(new_mean - old_mean)*100:.2f}%pt")

print(f"\n中央値:")
print(f"  修正前: {old_median*100:.2f}%")
print(f"  修正後: {new_median*100:.2f}%")
print(f"  差: {(new_median - old_median)*100:.2f}%pt")

print("\n完了!")
