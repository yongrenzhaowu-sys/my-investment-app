import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()

sample_2020 = df_price[df_price['date'] == '2020-10-01'].head(5)
print(f"元データの2020-10-01: {len(df_price[df_price['date'] == '2020-10-01'])} レコード")
print(f"\nカラム: {list(df_price.columns)}")
print(f"\n2020-10-01のサンプル:")
print(sample_2020[['date', 'code', 'adjusted_close' if 'adjusted_close' in df_price.columns else 'close']])

df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')

print(f"Pivot shape: {df_price_pivot.shape}")
print(f"2020-10-01がインデックスに含まれるか: {pd.Timestamp('2020-10-01') in df_price_pivot.index}")

if pd.Timestamp('2020-10-01') in df_price_pivot.index:
    row = df_price_pivot.loc[pd.Timestamp('2020-10-01')]
    print(f"2020-10-01の非NaN銘柄数: {row.notna().sum()}")
    print(f"2020-10-01の非NaN銘柄数（dropna後）: {len(row.dropna())}")
