"""
既存のカスタム成長率分析結果に時価総額データを追加
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("時価総額データを追加中...")

# 1. 既存の分析結果を読み込む
print("\n[1/5] 既存の分析結果を読み込み...")
df_growth = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_analysis/growth_rate_and_returns.csv',
    dtype={'code': str}
)
df_growth['disclosed_date'] = pd.to_datetime(df_growth['disclosed_date'])

print(f"既存レコード数: {len(df_growth):,}")

# 2. 財務データを読み込む（equity, bps）
print("\n[2/5] 財務データを読み込み...")
df_fin = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin['disclosed_date'] = pd.to_datetime(df_fin['disclosed_date'])
df_fin = df_fin[['disclosed_date', 'code', 'equity', 'bps']].dropna()

print(f"財務データ: {len(df_fin):,} 行")

# 3. 価格データを読み込む
print("\n[3/5] 価格データを読み込み...")
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])

print(f"価格データ: {len(df_price):,} 行")

# 4. 各レコードに対して時価総額を計算
print("\n[4/5] 時価総額を計算中...")

market_caps = []
estimated_shares_list = []
stock_prices = []

for idx, row in df_growth.iterrows():
    if idx % 10000 == 0:
        print(f"  進捗: {idx}/{len(df_growth)}")

    code = row['code']
    disclosed_date = row['disclosed_date']

    # 財務データを取得（開示日の最新データ）
    fin_data = df_fin[
        (df_fin['code'] == code) &
        (df_fin['disclosed_date'] <= disclosed_date)
    ].sort_values('disclosed_date').tail(1)

    if len(fin_data) == 0:
        market_caps.append(np.nan)
        estimated_shares_list.append(np.nan)
        stock_prices.append(np.nan)
        continue

    equity = fin_data.iloc[0]['equity']
    bps = fin_data.iloc[0]['bps']

    # 株価を取得（開示日以降の最初の営業日）
    price_data = df_price[
        (df_price['code'] == code) &
        (df_price['date'] >= disclosed_date)
    ].head(1)

    if len(price_data) == 0 or pd.isna(equity) or pd.isna(bps) or bps == 0:
        market_caps.append(np.nan)
        estimated_shares_list.append(np.nan)
        stock_prices.append(np.nan)
        continue

    stock_price = price_data.iloc[0]['adjusted_close']

    # 時価総額計算
    estimated_shares = equity / bps  # 発行済株式数の推定
    market_cap = stock_price * estimated_shares

    market_caps.append(market_cap)
    estimated_shares_list.append(estimated_shares)
    stock_prices.append(stock_price)

df_growth['market_cap'] = market_caps
df_growth['estimated_shares'] = estimated_shares_list
df_growth['stock_price'] = stock_prices

# 欠損値除外
df_growth = df_growth.dropna(subset=['market_cap'])

# 異常値除外
df_growth = df_growth[
    (df_growth['market_cap'] > 0) &
    (df_growth['market_cap'] < 1e15)
].copy()

print(f"\n時価総額計算完了: {len(df_growth):,} レコード")
print(f"時価総額の範囲: {df_growth['market_cap'].min()/1e8:.1f}億円 ~ {df_growth['market_cap'].max()/1e8:.1f}億円")

# 5. 時価総額別の分析
print("\n[5/5] 時価総額別の分析...")

# 時価総額の四分位
df_growth['marketcap_quartile'] = pd.qcut(
    df_growth['market_cap'],
    q=4,
    labels=['Q1 (小型株)', 'Q2', 'Q3', 'Q4 (大型株)'],
    duplicates='drop'
)

period_names = ['1M', '3M', '6M']

print("\n" + "="*80)
print("時価総額四分位別の相関係数")
print("="*80)

for mc_q in ['Q1 (小型株)', 'Q2', 'Q3', 'Q4 (大型株)']:
    subset = df_growth[df_growth['marketcap_quartile'] == mc_q]

    if len(subset) < 100:
        continue

    print(f"\n{mc_q} (N={len(subset):,}):")
    for name in period_names:
        corr = subset['custom_growth_rate'].corr(subset[f'return_{name}'])
        print(f"  {name}: {corr:+.4f}")

print("\n" + "="*80)
print("時価総額四分位別 × 成長率四分位別の平均騰落率（3ヶ月）")
print("="*80)

pivot_result = df_growth.pivot_table(
    index='marketcap_quartile',
    columns='growth_quartile',
    values='return_3M',
    aggfunc='mean'
)

print("\n平均騰落率（%）:")
print((pivot_result * 100).round(2))

# Q4（大型株）のみの詳細分析
print("\n" + "="*80)
print("Q4（大型株）のみ - 成長率四分位別の平均騰落率")
print("="*80)

large_cap = df_growth[df_growth['marketcap_quartile'] == 'Q4 (大型株)']

large_cap_analysis = large_cap.groupby('growth_quartile')[
    [f'return_{name}' for name in period_names]
].mean()

print(f"\nサンプル数: {len(large_cap):,}")
print("\n平均騰落率（%）:")
print((large_cap_analysis * 100).round(2))

# Q1（小型株）のみの詳細分析
print("\n" + "="*80)
print("Q1（小型株）のみ - 成長率四分位別の平均騰落率")
print("="*80)

small_cap = df_growth[df_growth['marketcap_quartile'] == 'Q1 (小型株)']

small_cap_analysis = small_cap.groupby('growth_quartile')[
    [f'return_{name}' for name in period_names]
].mean()

print(f"\nサンプル数: {len(small_cap):,}")
print("\n平均騰落率（%）:")
print((small_cap_analysis * 100).round(2))

# 仮説の検証
print("\n" + "="*80)
print("【仮説検証: 低時価総額ほど効くか？】")
print("="*80)

print("\n成長率効果（Q4高成長 - Q1低成長）の3ヶ月リターン差:")
for mc_q in ['Q1 (小型株)', 'Q2', 'Q3', 'Q4 (大型株)']:
    subset = df_growth[df_growth['marketcap_quartile'] == mc_q]

    if len(subset) < 100:
        continue

    high_growth = subset[subset['growth_quartile'] == 'Q4 (高成長)']['return_3M'].mean()
    low_growth = subset[subset['growth_quartile'] == 'Q1 (低成長)']['return_3M'].mean()
    diff = high_growth - low_growth

    print(f"{mc_q:20}: {diff*100:+6.2f}%")

print("\n→ 差が大きいほど成長率の効果が強い")

# 結果を保存
output_dir = PROJECT_ROOT / 'analyses' / 'custom_growth_rate_by_marketcap'
output_dir.mkdir(exist_ok=True, parents=True)

df_growth.to_csv(output_dir / 'growth_rate_by_marketcap.csv', index=False, encoding='utf-8-sig')

with open(output_dir / 'report.txt', 'w', encoding='utf-8') as f:
    f.write("カスタム四半期成長率と株価騰落率の相関検証（時価総額別）\n")
    f.write("="*80 + "\n\n")

    f.write(f"総レコード数: {len(df_growth):,}\n")
    f.write(f"時価総額の範囲: {df_growth['market_cap'].min()/1e8:.1f}億円 ~ {df_growth['market_cap'].max()/1e8:.1f}億円\n\n")

    f.write("="*80 + "\n")
    f.write("Q4（大型株）のみ - 成長率四分位別の平均騰落率（%）\n")
    f.write("="*80 + "\n")
    f.write((large_cap_analysis * 100).round(2).to_string())
    f.write("\n\n")

    f.write("="*80 + "\n")
    f.write("Q1（小型株）のみ - 成長率四分位別の平均騰落率（%）\n")
    f.write("="*80 + "\n")
    f.write((small_cap_analysis * 100).round(2).to_string())
    f.write("\n\n")

    f.write("="*80 + "\n")
    f.write("時価総額 × 成長率のクロス分析（3ヶ月、%）\n")
    f.write("="*80 + "\n")
    f.write((pivot_result * 100).round(2).to_string())

print(f"\n保存先: {output_dir}")
print("\n分析完了！")
