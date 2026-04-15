"""
決算発表後の株価反応タイミング分析（高速版）

既存のカスタム成長率データを再利用し、株価騰落率のみ再計算
期間: 1週間、1ヶ月、2ヶ月
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
import json
warnings.filterwarnings('ignore')

# プロジェクトルート
PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("決算発表後の株価反応タイミング分析（高速版）")
print("="*80)

# ================================================================================
# 1. 既存データの読み込み
# ================================================================================

print("\n[1/4] 既存の成長率データを読み込み中...")

# 既存の分析結果を読み込む
df_growth = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_by_marketcap/growth_rate_by_marketcap.csv',
    parse_dates=['disclosed_date']
)

print(f"既存データ: {len(df_growth):,} レコード")
print(f"期間: {df_growth['disclosed_date'].min()} ~ {df_growth['disclosed_date'].max()}")

# 必要な列だけを抽出
df_growth = df_growth[['code', 'disclosed_date', 'custom_growth_rate', 'market_cap',
                        'marketcap_quartile', 'growth_quartile']].copy()

# ================================================================================
# 2. 価格データの読み込みとピボット化
# ================================================================================

print("\n[2/4] 価格データを読み込み中...")

df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2017-01-01'].copy()

print(f"価格データ: {len(df_price):,} 行")

print("価格データをピボット化中...")
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')
print(f"ピボットテーブル: {df_price_pivot.shape[0]} 日 × {df_price_pivot.shape[1]} 銘柄")

# ================================================================================
# 3. 株価騰落率の計算（1週間、1ヶ月、2ヶ月）
# ================================================================================

print("\n[3/4] 株価騰落率を計算中（1週間、1ヶ月、2ヶ月）...")

# 営業日換算: 1週間=5日、1ヶ月=21日、2ヶ月=42日
holding_periods = [5, 21, 42]
period_names = ['1W', '1M', '2M']

for period, name in zip(holding_periods, period_names):
    print(f"  {name} ({period}営業日) を計算中...")
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
    print(f"    完了: {pd.notna(df_growth[f'return_{name}']).sum():,} / {len(df_growth):,} レコード")

# 欠損値除外
df_growth = df_growth.dropna(subset=[f'return_{name}' for name in period_names])

print(f"\n欠損値除外後: {len(df_growth):,} レコード")

# ================================================================================
# 4. 分析結果の出力
# ================================================================================

print("\n[4/4] 分析結果を出力中...")

print("\n" + "="*80)
print("全体の相関係数（期間別）")
print("="*80)

print("\n全銘柄:")
for name in period_names:
    corr = df_growth['custom_growth_rate'].corr(df_growth[f'return_{name}'])
    print(f"  {name}: {corr:+.4f}")

print("\n" + "="*80)
print("時価総額四分位別の相関係数（期間別）")
print("="*80)

correlation_by_marketcap = {}

for mc_q in ['Q1 (小型株)', 'Q2', 'Q3', 'Q4 (大型株)']:
    subset = df_growth[df_growth['marketcap_quartile'] == mc_q]

    if len(subset) < 100:
        continue

    print(f"\n{mc_q} (N={len(subset):,}):")
    correlation_by_marketcap[mc_q] = {}

    for name in period_names:
        corr = subset['custom_growth_rate'].corr(subset[f'return_{name}'])
        correlation_by_marketcap[mc_q][name] = float(corr)
        print(f"  {name}: {corr:+.4f}")

print("\n" + "="*80)
print("小型株（Q1）のみ - 成長率四分位別の平均騰落率")
print("="*80)

small_cap = df_growth[df_growth['marketcap_quartile'] == 'Q1 (小型株)']

small_cap_analysis = small_cap.groupby('growth_quartile')[
    [f'return_{name}' for name in period_names]
].mean()

print(f"\nサンプル数: {len(small_cap):,}")
print("\n平均騰落率（%）:")
print((small_cap_analysis * 100).round(2))

# 成長率効果（Q4 vs Q1）
print("\n" + "="*80)
print("成長率効果（Q4高成長 - Q1低成長）のリターン差")
print("="*80)

growth_effect = {}

for name in period_names:
    high_growth = small_cap[small_cap['growth_quartile'] == 'Q4 (高成長)'][f'return_{name}'].mean()
    low_growth = small_cap[small_cap['growth_quartile'] == 'Q1 (低成長)'][f'return_{name}'].mean()
    diff = high_growth - low_growth
    growth_effect[name] = float(diff)
    print(f"{name}: {diff*100:+6.2f}%")

print("\n" + "="*80)
print("全時価総額四分位での成長率効果（期間別）")
print("="*80)

growth_effect_by_marketcap = {}

for mc_q in ['Q1 (小型株)', 'Q2', 'Q3', 'Q4 (大型株)']:
    subset = df_growth[df_growth['marketcap_quartile'] == mc_q]

    if len(subset) < 100:
        continue

    print(f"\n{mc_q}:")
    growth_effect_by_marketcap[mc_q] = {}

    for name in period_names:
        high_growth = subset[subset['growth_quartile'] == 'Q4 (高成長)'][f'return_{name}'].mean()
        low_growth = subset[subset['growth_quartile'] == 'Q1 (低成長)'][f'return_{name}'].mean()
        diff = high_growth - low_growth
        growth_effect_by_marketcap[mc_q][name] = float(diff)
        print(f"  {name}: {diff*100:+6.2f}%")

# 中型株（Q2, Q3）の分析
print("\n" + "="*80)
print("中型株（Q2）のみ - 成長率四分位別の平均騰落率")
print("="*80)

mid_cap_q2 = df_growth[df_growth['marketcap_quartile'] == 'Q2']
mid_cap_q2_analysis = mid_cap_q2.groupby('growth_quartile')[
    [f'return_{name}' for name in period_names]
].mean()

print(f"\nサンプル数: {len(mid_cap_q2):,}")
print("\n平均騰落率（%）:")
print((mid_cap_q2_analysis * 100).round(2))

# 大型株（Q4）の分析
print("\n" + "="*80)
print("大型株（Q4）のみ - 成長率四分位別の平均騰落率")
print("="*80)

large_cap = df_growth[df_growth['marketcap_quartile'] == 'Q4 (大型株)']
large_cap_analysis = large_cap.groupby('growth_quartile')[
    [f'return_{name}' for name in period_names]
].mean()

print(f"\nサンプル数: {len(large_cap):,}")
print("\n平均騰落率（%）:")
print((large_cap_analysis * 100).round(2))

# ================================================================================
# 5. 結果の保存
# ================================================================================

print("\n[保存中...]")

output_dir = PROJECT_ROOT / 'analyses' / '20260225_1400_earnings_timing_analysis' / 'results'
output_dir.mkdir(exist_ok=True, parents=True)

# 詳細データ
df_growth.to_csv(output_dir / 'detailed_data.csv', index=False, encoding='utf-8-sig')

# サマリ
summary = {
    'total_records': int(len(df_growth)),
    'unique_stocks': int(df_growth['code'].nunique()),
    'date_range': f"{df_growth['disclosed_date'].min().date()} ~ {df_growth['disclosed_date'].max().date()}",
    'marketcap_range': {
        'min_billion_yen': float(df_growth['market_cap'].min() / 1e9),
        'max_billion_yen': float(df_growth['market_cap'].max() / 1e9)
    },
    'correlation_by_marketcap': correlation_by_marketcap,
    'small_cap_analysis': {
        'sample_size': int(len(small_cap)),
        'mean_returns_by_growth': small_cap_analysis.to_dict()
    },
    'mid_cap_q2_analysis': {
        'sample_size': int(len(mid_cap_q2)),
        'mean_returns_by_growth': mid_cap_q2_analysis.to_dict()
    },
    'large_cap_analysis': {
        'sample_size': int(len(large_cap)),
        'mean_returns_by_growth': large_cap_analysis.to_dict()
    },
    'growth_effect_small_cap': growth_effect,
    'growth_effect_by_marketcap': growth_effect_by_marketcap
}

with open(output_dir / 'summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

# テキストレポート
with open(output_dir / 'report.txt', 'w', encoding='utf-8') as f:
    f.write("決算発表後の株価反応タイミング分析\n")
    f.write("="*80 + "\n\n")

    f.write(f"分析期間: {summary['date_range']}\n")
    f.write(f"総レコード数: {summary['total_records']:,}\n")
    f.write(f"対象銘柄数: {summary['unique_stocks']:,}\n\n")

    f.write("="*80 + "\n")
    f.write("時価総額四分位別の相関係数（期間別）\n")
    f.write("="*80 + "\n")
    for mc_q, corrs in correlation_by_marketcap.items():
        f.write(f"\n{mc_q}:\n")
        for period, corr in corrs.items():
            f.write(f"  {period}: {corr:+.4f}\n")

    f.write("\n" + "="*80 + "\n")
    f.write("小型株（Q1）- 成長率四分位別の平均騰落率（%）\n")
    f.write("="*80 + "\n")
    f.write((small_cap_analysis * 100).round(2).to_string())
    f.write("\n\n")

    f.write("="*80 + "\n")
    f.write("中型株（Q2）- 成長率四分位別の平均騰落率（%）\n")
    f.write("="*80 + "\n")
    f.write((mid_cap_q2_analysis * 100).round(2).to_string())
    f.write("\n\n")

    f.write("="*80 + "\n")
    f.write("大型株（Q4）- 成長率四分位別の平均騰落率（%）\n")
    f.write("="*80 + "\n")
    f.write((large_cap_analysis * 100).round(2).to_string())
    f.write("\n\n")

    f.write("="*80 + "\n")
    f.write("成長率効果（Q4高成長 - Q1低成長）のリターン差\n")
    f.write("="*80 + "\n\n")

    f.write("小型株（Q1）:\n")
    for period, effect in growth_effect.items():
        f.write(f"  {period}: {effect*100:+6.2f}%\n")

    f.write("\n全時価総額四分位:\n")
    for mc_q, effects in growth_effect_by_marketcap.items():
        f.write(f"\n{mc_q}:\n")
        for period, effect in effects.items():
            f.write(f"  {period}: {effect*100:+6.2f}%\n")

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("分析完了！")
print("="*80)

# ================================================================================
# 主要な発見のハイライト
# ================================================================================

print("\n【主要な発見】")
print("\n1. 小型株（Q1）の相関係数（期間別）:")
for name in period_names:
    corr = correlation_by_marketcap.get('Q1 (小型株)', {}).get(name, 0)
    print(f"   {name}: {corr:+.4f}")

print("\n2. 小型株（Q1）の成長率効果（Q4 - Q1、期間別）:")
for period, effect in growth_effect.items():
    print(f"   {period}: {effect*100:+6.2f}%")

print("\n3. 最も効果的な期間:")
best_period = max(growth_effect, key=growth_effect.get)
best_effect = growth_effect[best_period]
print(f"   {best_period}: {best_effect*100:+6.2f}%")

print("\n4. 時価総額による違い（1ヶ月の成長率効果）:")
for mc_q in ['Q1 (小型株)', 'Q2', 'Q3', 'Q4 (大型株)']:
    if mc_q in growth_effect_by_marketcap:
        effect = growth_effect_by_marketcap[mc_q].get('1M', 0)
        print(f"   {mc_q}: {effect*100:+6.2f}%")
