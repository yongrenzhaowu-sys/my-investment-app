"""
超高速版：カスタム成長率 × 時価総額分析
完全ベクトル化アプローチ
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("超高速版：カスタム成長率 × 時価総額分析")
print("="*80)

# 1. 既存の分析結果を読み込む
print("\n[1/4] 既存の分析結果を読み込み...")
df = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_analysis/growth_rate_and_returns.csv',
    dtype={'code': str}
)
df['disclosed_date'] = pd.to_datetime(df['disclosed_date'])

print(f"レコード数: {len(df):,}")

# 2. 財務データを読み込んで準備（ユニーク化）
print("\n[2/4] 財務データをマージ...")
df_fin = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin = df_fin[['disclosed_date', 'code', 'equity', 'bps']].copy()
df_fin['disclosed_date'] = pd.to_datetime(df_fin['disclosed_date'])
df_fin = df_fin.dropna(subset=['equity', 'bps'])
df_fin = df_fin[df_fin['bps'] > 0]

# 同じcode-dateの重複を除去（最新を採用）
df_fin = df_fin.sort_values(['code', 'disclosed_date']).drop_duplicates(
    subset=['code', 'disclosed_date'], keep='last'
)

# マルチインデックスを作成
df_fin_indexed = df_fin.set_index(['code', 'disclosed_date']).sort_index()

print(f"財務データ: {len(df_fin):,} ユニークレコード")

# dfにもマルチインデックスを適用して、財務データを後方結合
df_copy = df.copy()
df_copy = df_copy.set_index(['code', 'disclosed_date']).sort_index()

print("  財務データを後方結合中...")

# 各銘柄ごとに最新の財務データを取得（ベクトル化）
equity_list = []
bps_list = []

for idx in df_copy.index:
    code, date = idx
    # この銘柄のこの日付以前の財務データを探す
    try:
        fin_data = df_fin_indexed.loc[code]
        if isinstance(fin_data, pd.Series):
            # 単一レコード
            equity_list.append(fin_data['equity'])
            bps_list.append(fin_data['bps'])
        else:
            # 複数レコード
            valid = fin_data[fin_data.index <= date]
            if len(valid) > 0:
                latest = valid.iloc[-1]
                equity_list.append(latest['equity'])
                bps_list.append(latest['bps'])
            else:
                equity_list.append(np.nan)
                bps_list.append(np.nan)
    except KeyError:
        equity_list.append(np.nan)
        bps_list.append(np.nan)

df_copy['equity'] = equity_list
df_copy['bps'] = bps_list

# インデックスをリセット
df = df_copy.reset_index()
df = df.dropna(subset=['equity', 'bps'])

print(f"財務データマージ後: {len(df):,} レコード")

# 3. 価格データをマージ
print("\n[3/4] 価格データをマージ...")
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price = df_price[['date', 'code', 'adjusted_close']].copy()
df_price['date'] = pd.to_datetime(df_price['date'])

# 同じcode-dateの重複を除去
df_price = df_price.sort_values(['code', 'date']).drop_duplicates(
    subset=['code', 'date'], keep='last'
)

df_price_indexed = df_price.set_index(['code', 'date']).sort_index()

print(f"価格データ: {len(df_price):,} ユニークレコード")

# 各銘柄ごとに開示日以降の最初の価格を取得
print("  価格データを前方結合中...")

price_list = []

for _, row in df.iterrows():
    code = row['code']
    date = row['disclosed_date']

    try:
        price_data = df_price_indexed.loc[code]
        if isinstance(price_data, pd.Series):
            # 単一レコード
            price_list.append(price_data['adjusted_close'])
        else:
            # 複数レコード
            valid = price_data[price_data.index >= date]
            if len(valid) > 0:
                first = valid.iloc[0]
                price_list.append(first['adjusted_close'])
            else:
                price_list.append(np.nan)
    except KeyError:
        price_list.append(np.nan)

df['adjusted_close'] = price_list
df = df.dropna(subset=['adjusted_close'])

print(f"価格データマージ後: {len(df):,} レコード")

# 4. 時価総額を計算
print("\n[4/4] 時価総額を計算...")

# 発行済株式数の推定
df['estimated_shares'] = df['equity'] / df['bps']

# 時価総額
df['market_cap'] = df['adjusted_close'] * df['estimated_shares']

# 欠損値・異常値除外
df = df.dropna(subset=['market_cap'])
df = df[(df['market_cap'] > 0) & (df['market_cap'] < 1e15)]

print(f"最終レコード数: {len(df):,}")
print(f"時価総額範囲: {df['market_cap'].min()/1e8:.1f}億円 ~ {df['market_cap'].max()/1e8:.1f}億円")

# 5. 時価総額四分位
df['marketcap_quartile'] = pd.qcut(
    df['market_cap'],
    q=4,
    labels=['Q1 (小型株)', 'Q2', 'Q3', 'Q4 (大型株)']
)

# 6. 分析
print("\n" + "="*80)
print("【結果】時価総額四分位別の相関係数（3ヶ月）")
print("="*80)

for mc_q in ['Q1 (小型株)', 'Q2', 'Q3', 'Q4 (大型株)']:
    subset = df[df['marketcap_quartile'] == mc_q]
    corr = subset['custom_growth_rate'].corr(subset['return_3M'])
    print(f"{mc_q:20} (N={len(subset):5,}):  {corr:+.4f}")

print("\n" + "="*80)
print("【結果】Q4（大型株）のみ - 成長率四分位別の平均騰落率")
print("="*80)

large_cap = df[df['marketcap_quartile'] == 'Q4 (大型株)']

large_cap_analysis = large_cap.groupby('growth_quartile')[
    ['return_1M', 'return_3M', 'return_6M']
].mean()

print(f"\nサンプル数: {len(large_cap):,}")
print("\n平均騰落率（%）:")
print((large_cap_analysis * 100).round(2))

print("\n" + "="*80)
print("【結果】Q1（小型株）のみ - 成長率四分位別の平均騰落率")
print("="*80)

small_cap = df[df['marketcap_quartile'] == 'Q1 (小型株)']

small_cap_analysis = small_cap.groupby('growth_quartile')[
    ['return_1M', 'return_3M', 'return_6M']
].mean()

print(f"\nサンプル数: {len(small_cap):,}")
print("\n平均騰落率（%）:")
print((small_cap_analysis * 100).round(2))

print("\n" + "="*80)
print("【仮説検証】低時価総額ほど効くか？")
print("="*80)

print("\n成長率効果（Q4高成長 - Q1低成長）の3ヶ月リターン差:")
for mc_q in ['Q1 (小型株)', 'Q2', 'Q3', 'Q4 (大型株)']:
    subset = df[df['marketcap_quartile'] == mc_q]

    high = subset[subset['growth_quartile'] == 'Q4 (高成長)']['return_3M'].mean()
    low = subset[subset['growth_quartile'] == 'Q1 (低成長)']['return_3M'].mean()
    diff = high - low

    print(f"{mc_q:20}: {diff*100:+6.2f}%")

print("\n→ 差が大きいほど成長率の効果が強い")

# クロス分析
print("\n" + "="*80)
print("【詳細】時価総額 × 成長率のクロス分析（3ヶ月、%）")
print("="*80)

pivot = df.pivot_table(
    index='marketcap_quartile',
    columns='growth_quartile',
    values='return_3M',
    aggfunc='mean'
)

print("\n")
print((pivot * 100).round(2))

# 保存
output_dir = PROJECT_ROOT / 'analyses' / 'custom_growth_rate_by_marketcap'
output_dir.mkdir(exist_ok=True, parents=True)

df.to_csv(output_dir / 'growth_rate_by_marketcap.csv', index=False, encoding='utf-8-sig')

with open(output_dir / 'report.txt', 'w', encoding='utf-8') as f:
    f.write("カスタム成長率 × 時価総額分析\n")
    f.write("="*80 + "\n\n")

    f.write(f"総レコード数: {len(df):,}\n")
    f.write(f"時価総額範囲: {df['market_cap'].min()/1e8:.1f}億円 ~ {df['market_cap'].max()/1e8:.1f}億円\n\n")

    f.write("Q4（大型株）- 成長率四分位別の平均騰落率（%）\n")
    f.write((large_cap_analysis * 100).round(2).to_string())
    f.write("\n\n")

    f.write("Q1（小型株）- 成長率四分位別の平均騰落率（%）\n")
    f.write((small_cap_analysis * 100).round(2).to_string())
    f.write("\n\n")

    f.write("時価総額 × 成長率のクロス分析（3ヶ月、%）\n")
    f.write((pivot * 100).round(2).to_string())

print(f"\n保存先: {output_dir}")
print("\n完了！")
