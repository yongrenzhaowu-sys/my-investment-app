"""
決算発表後の株価反応タイミング分析

目的: 低時価総額株式のカスタム成長率と、決算発表日からの期間別株価相関を検証
期間: 1週間、1ヶ月、2ヶ月
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import warnings
import json
warnings.filterwarnings('ignore')

# プロジェクトルート
PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("決算発表後の株価反応タイミング分析")
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
# 6. 株価騰落率の計算（1週間、1ヶ月、2ヶ月）
# ================================================================================

print("\n[6/7] 株価騰落率を計算中...")

# 営業日換算: 1週間=5日、1ヶ月=21日、2ヶ月=42日
holding_periods = [5, 21, 42]
period_names = ['1W', '1M', '2M']

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
# 7. 時価総額別・期間別の分析
# ================================================================================

print("\n[7/7] 時価総額別・期間別の分析中...")

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

# ================================================================================
# 分析結果の出力
# ================================================================================

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

# ================================================================================
# 8. 結果の保存
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

print("\n→ 詳細はナレッジファイルに記録します")
