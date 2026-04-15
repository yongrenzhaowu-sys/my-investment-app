"""
カスタム四半期成長率と株価騰落率の相関検証（時価総額別）

仮説: 低時価総額ほどカスタム成長率の効果が高い
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import warnings
warnings.filterwarnings('ignore')

# プロジェクトルート
PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("カスタム四半期成長率と株価騰落率の相関検証（時価総額別）")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/7] データ読み込み中...")

# 財務データ（四半期決算）
df_fin = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin['disclosed_date'] = pd.to_datetime(df_fin['disclosed_date'])

# 価格データ
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])

print(f"財務データ: {len(df_fin):,} 行")
print(f"価格データ: {len(df_price):,} 行")

# 期間フィルタ（2017年以降）
df_fin = df_fin[df_fin['disclosed_date'] >= '2017-01-01'].copy()
df_price = df_price[df_price['date'] >= '2017-01-01'].copy()

print(f"期間フィルタ後 - 財務: {len(df_fin):,} 行, 価格: {len(df_price):,} 行")

# ================================================================================
# 2. カスタム成長率の計算
# ================================================================================

print("\n[2/7] カスタム成長率を計算中...")

# 必要な列を抽出
df_fin = df_fin[['disclosed_date', 'code', 'fiscal_quarter', 'ordinary_profit', 'equity', 'bps']].copy()

# 欠損値除外
df_fin = df_fin.dropna(subset=['ordinary_profit'])

print(f"欠損値除外後: {len(df_fin):,} 行")

# 各銘柄・四半期ごとにソート
df_fin = df_fin.sort_values(['code', 'disclosed_date'])

# 成長率計算
results = []

for code, group in df_fin.groupby('code'):
    group = group.reset_index(drop=True)

    for i in range(len(group)):
        current_row = group.iloc[i]
        current_date = current_row['disclosed_date']
        current_profit = current_row['ordinary_profit']
        current_quarter = current_row['fiscal_quarter']

        # 時価総額計算用の財務データ
        equity = current_row['equity']
        bps = current_row['bps']

        # 前年同期を探す
        previous_year_data = group[
            (group['fiscal_quarter'] == current_quarter) &
            (group['disclosed_date'] < current_date) &
            (group['disclosed_date'] >= current_date - pd.Timedelta(days=400)) &
            (group['disclosed_date'] <= current_date - pd.Timedelta(days=300))
        ]

        if len(previous_year_data) == 0:
            previous_year_data = group[
                (group['disclosed_date'] < current_date) &
                (group['disclosed_date'] >= current_date - pd.Timedelta(days=400))
            ]

        if len(previous_year_data) == 0:
            continue

        previous_year_profit = previous_year_data.iloc[-1]['ordinary_profit']

        # 直近4四半期のデータを取得
        recent_4q = group[group['disclosed_date'] <= current_date].tail(4)

        if len(recent_4q) < 4:
            continue

        # 分母: 直近4四半期の経常利益の絶対値の合計
        denominator = recent_4q['ordinary_profit'].abs().sum()

        if denominator == 0:
            continue

        # カスタム成長率の計算
        numerator = current_profit - previous_year_profit
        growth_rate = numerator / denominator

        results.append({
            'code': code,
            'disclosed_date': current_date,
            'fiscal_quarter': current_quarter,
            'current_profit': current_profit,
            'previous_year_profit': previous_year_profit,
            'recent_4q_abs_sum': denominator,
            'custom_growth_rate': growth_rate,
            'equity': equity,
            'bps': bps
        })

df_growth = pd.DataFrame(results)

print(f"成長率計算完了: {len(df_growth):,} レコード")

# 異常値除外（成長率が-5～+5の範囲）
df_growth = df_growth[
    (df_growth['custom_growth_rate'] >= -5) &
    (df_growth['custom_growth_rate'] <= 5)
].copy()

print(f"異常値除外後: {len(df_growth):,} レコード")

# ================================================================================
# 3. 価格データの準備とマージ
# ================================================================================

print("\n[3/7] 開示日の株価を取得中...")

# 開示日の株価を取得（時価総額計算用）
stock_prices = []

for idx, row in df_growth.iterrows():
    code = row['code']
    disclosed_date = row['disclosed_date']

    # 開示日以降の価格を取得
    price_data = df_price[
        (df_price['code'] == code) &
        (df_price['date'] >= disclosed_date)
    ].head(1)

    if len(price_data) > 0:
        stock_price = price_data.iloc[0]['adjusted_close']
        stock_prices.append(stock_price)
    else:
        stock_prices.append(np.nan)

df_growth['stock_price'] = stock_prices

# 欠損値除外
df_growth = df_growth.dropna(subset=['stock_price', 'equity', 'bps'])

print(f"株価データマージ後: {len(df_growth):,} レコード")

# ================================================================================
# 4. 時価総額の計算
# ================================================================================

print("\n[4/7] 時価総額を計算中...")

# 発行済株式数の推定: equity / bps
df_growth['estimated_shares'] = df_growth['equity'] / df_growth['bps']

# 時価総額の推定: stock_price × estimated_shares
df_growth['market_cap'] = df_growth['stock_price'] * df_growth['estimated_shares']

# 異常値除外（時価総額が負または極端に大きい）
df_growth = df_growth[
    (df_growth['market_cap'] > 0) &
    (df_growth['market_cap'] < 1e15)  # 1000兆円以下
].copy()

print(f"時価総額計算完了: {len(df_growth):,} レコード")
print(f"時価総額の範囲: {df_growth['market_cap'].min()/1e8:.1f}億円 ~ {df_growth['market_cap'].max()/1e8:.1f}億円")

# ================================================================================
# 5. 価格データの準備（ピボット化）
# ================================================================================

print("\n[5/7] 価格データをピボット化中...")

df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')
print(f"ピボットテーブル: {df_price_pivot.shape[0]} 日 × {df_price_pivot.shape[1]} 銘柄")

# ================================================================================
# 6. 株価騰落率の計算
# ================================================================================

print("\n[6/7] 株価騰落率を計算中...")

holding_periods = [21, 63, 126]  # 1ヶ月、3ヶ月、6ヶ月（営業日）
period_names = ['1M', '3M', '6M']

for period, name in zip(holding_periods, period_names):
    returns = []

    for idx, row in df_growth.iterrows():
        code = row['code']
        disclosed_date = row['disclosed_date']

        if code not in df_price_pivot.columns:
            returns.append(np.nan)
            continue

        future_dates = df_price_pivot.index[df_price_pivot.index >= disclosed_date]

        if len(future_dates) == 0:
            returns.append(np.nan)
            continue

        start_date = future_dates[0]
        start_price = df_price_pivot.loc[start_date, code]

        if pd.isna(start_price):
            returns.append(np.nan)
            continue

        future_dates_from_start = df_price_pivot.index[df_price_pivot.index >= start_date]

        if len(future_dates_from_start) < period + 1:
            returns.append(np.nan)
            continue

        end_date = future_dates_from_start[min(period, len(future_dates_from_start) - 1)]
        end_price = df_price_pivot.loc[end_date, code]

        if pd.isna(end_price):
            returns.append(np.nan)
            continue

        return_pct = (end_price - start_price) / start_price
        returns.append(return_pct)

    df_growth[f'return_{name}'] = returns

print(f"騰落率計算完了")

# 欠損値除外
df_growth = df_growth.dropna(subset=[f'return_{name}' for name in period_names])

print(f"欠損値除外後: {len(df_growth):,} レコード")

# ================================================================================
# 7. 時価総額別の分析
# ================================================================================

print("\n[7/7] 時価総額別の分析中...")

# 時価総額の四分位
df_growth['marketcap_quartile'] = pd.qcut(
    df_growth['market_cap'],
    q=4,
    labels=['Q1 (小型株)', 'Q2', 'Q3', 'Q4 (大型株)'],
    duplicates='drop'
)

# カスタム成長率の四分位
df_growth['growth_quartile'] = pd.qcut(
    df_growth['custom_growth_rate'],
    q=4,
    labels=['Q1 (低成長)', 'Q2', 'Q3', 'Q4 (高成長)'],
    duplicates='drop'
)

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

# 小型株（Q1）のみの詳細分析
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

# ================================================================================
# 8. 結果の保存
# ================================================================================

print("\n[保存中...]")

output_dir = PROJECT_ROOT / 'analyses' / 'custom_growth_rate_by_marketcap'
output_dir.mkdir(exist_ok=True, parents=True)

# 詳細データ
df_growth.to_csv(output_dir / 'growth_rate_by_marketcap.csv', index=False, encoding='utf-8-sig')

# サマリ
summary = {
    'total_records': len(df_growth),
    'unique_stocks': df_growth['code'].nunique(),
    'date_range': f"{df_growth['disclosed_date'].min().date()} ~ {df_growth['disclosed_date'].max().date()}",
    'large_cap_analysis': large_cap_analysis.to_dict(),
    'small_cap_analysis': small_cap_analysis.to_dict(),
    'pivot_3m': pivot_result.to_dict()
}

import json
with open(output_dir / 'summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

# テキストレポート
with open(output_dir / 'report.txt', 'w', encoding='utf-8') as f:
    f.write("カスタム四半期成長率と株価騰落率の相関検証（時価総額別）\n")
    f.write("="*80 + "\n\n")

    f.write(f"分析期間: {summary['date_range']}\n")
    f.write(f"総レコード数: {summary['total_records']:,}\n")
    f.write(f"対象銘柄数: {summary['unique_stocks']:,}\n\n")

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

print("\n" + "="*80)
print("分析完了！")
print("="*80)

# 仮説の検証
print("\n【仮説検証: 低時価総額ほど効くか？】")

# 各時価総額四分位での成長率効果（Q4 vs Q1のリターン差）
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
