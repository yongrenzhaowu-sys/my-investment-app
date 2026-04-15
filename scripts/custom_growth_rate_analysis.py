"""
カスタム四半期成長率と株価騰落率の相関検証

成長率の定義:
GrowthRate = (CurrentOrdinaryProfit - PreviousYearSamePeriodProfit) /
             (|Current| + |Previous1| + |Previous2| + |Previous3|)

分母: 直近4四半期の経常利益の絶対値の合計
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
print("カスタム四半期成長率と株価騰落率の相関検証")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/6] データ読み込み中...")

# 財務データ（四半期決算）
df_fin = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/financials/statements_all.parquet')
df_fin['disclosed_date'] = pd.to_datetime(df_fin['disclosed_date'])

# 経常利益が必要なので、列が存在するか確認
if 'ordinary_profit' not in df_fin.columns:
    raise ValueError("ordinary_profit列が見つかりません")

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

print("\n[2/6] カスタム成長率を計算中...")

# 四半期情報を整理
df_fin = df_fin[['disclosed_date', 'code', 'fiscal_quarter', 'ordinary_profit']].copy()

# 欠損値除外
df_fin = df_fin.dropna(subset=['ordinary_profit'])

# fiscal_quarterが存在するか確認
if 'fiscal_quarter' not in df_fin.columns:
    print("警告: fiscal_quarter列が存在しません。決算日から推定します。")
    # 簡易的に全データを四半期として扱う
    df_fin['fiscal_quarter'] = 'Q'

print(f"欠損値除外後: {len(df_fin):,} 行")

# 各銘柄・四半期ごとにソート
df_fin = df_fin.sort_values(['code', 'disclosed_date'])

# 成長率計算のための準備
results = []

for code, group in df_fin.groupby('code'):
    group = group.reset_index(drop=True)

    for i in range(len(group)):
        current_row = group.iloc[i]
        current_date = current_row['disclosed_date']
        current_profit = current_row['ordinary_profit']
        current_quarter = current_row['fiscal_quarter']

        # 前年同期を探す（約4四半期前 = 約365日前）
        # 同じfiscal_quarterで、約1年前のデータを探す
        previous_year_data = group[
            (group['fiscal_quarter'] == current_quarter) &
            (group['disclosed_date'] < current_date) &
            (group['disclosed_date'] >= current_date - pd.Timedelta(days=400)) &
            (group['disclosed_date'] <= current_date - pd.Timedelta(days=300))
        ]

        if len(previous_year_data) == 0:
            # 前年同期が見つからない場合、約1年前のデータを使う
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
            'custom_growth_rate': growth_rate
        })

df_growth = pd.DataFrame(results)

print(f"成長率計算完了: {len(df_growth):,} レコード")
print(f"対象銘柄数: {df_growth['code'].nunique()} 銘柄")

# 異常値除外（成長率が-5～+5の範囲）
df_growth = df_growth[
    (df_growth['custom_growth_rate'] >= -5) &
    (df_growth['custom_growth_rate'] <= 5)
].copy()

print(f"異常値除外後: {len(df_growth):,} レコード")

# ================================================================================
# 3. 価格データの準備（ピボット化）
# ================================================================================

print("\n[3/6] 価格データをピボット化中...")

df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')
print(f"ピボットテーブル: {df_price_pivot.shape[0]} 日 × {df_price_pivot.shape[1]} 銘柄")

# ================================================================================
# 4. 株価騰落率の計算
# ================================================================================

print("\n[4/6] 株価騰落率を計算中...")

holding_periods = [21, 63, 126]  # 1ヶ月、3ヶ月、6ヶ月（営業日）
period_names = ['1M', '3M', '6M']

for period, name in zip(holding_periods, period_names):
    returns = []

    for idx, row in df_growth.iterrows():
        code = row['code']
        disclosed_date = row['disclosed_date']

        # 銘柄が価格データに存在するか確認
        if code not in df_price_pivot.columns:
            returns.append(np.nan)
            continue

        # 開示日以降の価格を取得
        future_dates = df_price_pivot.index[df_price_pivot.index >= disclosed_date]

        if len(future_dates) == 0:
            returns.append(np.nan)
            continue

        # 開示日の翌営業日の価格
        start_date = future_dates[0] if len(future_dates) > 0 else None
        if start_date is None:
            returns.append(np.nan)
            continue

        start_price = df_price_pivot.loc[start_date, code]

        if pd.isna(start_price):
            returns.append(np.nan)
            continue

        # period営業日後の価格
        future_dates_from_start = df_price_pivot.index[df_price_pivot.index >= start_date]

        if len(future_dates_from_start) < period + 1:
            returns.append(np.nan)
            continue

        end_date = future_dates_from_start[min(period, len(future_dates_from_start) - 1)]
        end_price = df_price_pivot.loc[end_date, code]

        if pd.isna(end_price):
            returns.append(np.nan)
            continue

        # 騰落率
        return_pct = (end_price - start_price) / start_price
        returns.append(return_pct)

    df_growth[f'return_{name}'] = returns

print(f"騰落率計算完了")

# 欠損値除外
df_growth = df_growth.dropna(subset=[f'return_{name}' for name in period_names])

print(f"欠損値除外後: {len(df_growth):,} レコード")

# ================================================================================
# 5. 相関分析
# ================================================================================

print("\n[5/6] 相関分析中...")

print("\n" + "="*80)
print("カスタム成長率と株価騰落率の相関係数")
print("="*80)

for name in period_names:
    corr = df_growth['custom_growth_rate'].corr(df_growth[f'return_{name}'])
    print(f"{name:>4}: {corr:+.4f}")

# 四分位分析
print("\n" + "="*80)
print("成長率四分位別の平均騰落率")
print("="*80)

df_growth['growth_quartile'] = pd.qcut(
    df_growth['custom_growth_rate'],
    q=4,
    labels=['Q1 (低成長)', 'Q2', 'Q3', 'Q4 (高成長)'],
    duplicates='drop'
)

quartile_analysis = df_growth.groupby('growth_quartile')[
    [f'return_{name}' for name in period_names]
].mean()

print("\n平均騰落率（%）:")
print((quartile_analysis * 100).round(2))

# ================================================================================
# 6. 結果の保存
# ================================================================================

print("\n[6/6] 結果を保存中...")

output_dir = PROJECT_ROOT / 'analyses' / 'custom_growth_rate_analysis'
output_dir.mkdir(exist_ok=True, parents=True)

# 詳細データ
df_growth.to_csv(output_dir / 'growth_rate_and_returns.csv', index=False, encoding='utf-8-sig')

# サマリ
summary = {
    'total_records': len(df_growth),
    'unique_stocks': df_growth['code'].nunique(),
    'date_range': f"{df_growth['disclosed_date'].min().date()} ~ {df_growth['disclosed_date'].max().date()}",
    'correlation': {
        name: df_growth['custom_growth_rate'].corr(df_growth[f'return_{name}'])
        for name in period_names
    },
    'quartile_analysis': quartile_analysis.to_dict()
}

import json
with open(output_dir / 'summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

# テキストレポート
with open(output_dir / 'report.txt', 'w', encoding='utf-8') as f:
    f.write("カスタム四半期成長率と株価騰落率の相関検証\n")
    f.write("="*80 + "\n\n")

    f.write(f"分析期間: {summary['date_range']}\n")
    f.write(f"総レコード数: {summary['total_records']:,}\n")
    f.write(f"対象銘柄数: {summary['unique_stocks']:,}\n\n")

    f.write("カスタム成長率の定義:\n")
    f.write("GrowthRate = (Current - PreviousYearSame) / (|Q0| + |Q1| + |Q2| + |Q3|)\n")
    f.write("  ※分母は直近4四半期の経常利益の絶対値の合計\n\n")

    f.write("="*80 + "\n")
    f.write("相関係数\n")
    f.write("="*80 + "\n")
    for name in period_names:
        corr = summary['correlation'][name]
        f.write(f"{name}: {corr:+.4f}\n")

    f.write("\n" + "="*80 + "\n")
    f.write("成長率四分位別の平均騰落率（%）\n")
    f.write("="*80 + "\n")
    f.write((quartile_analysis * 100).round(2).to_string())

print(f"\n保存先: {output_dir}")
print(f"  - growth_rate_and_returns.csv (詳細データ)")
print(f"  - summary.json (サマリ)")
print(f"  - report.txt (レポート)")

print("\n" + "="*80)
print("分析完了！")
print("="*80)

# 基本統計量
print("\n【基本統計量】")
print("\nカスタム成長率:")
print(df_growth['custom_growth_rate'].describe())

print("\n株価騰落率（1ヶ月）:")
print(df_growth['return_1M'].describe())

print("\n株価騰落率（3ヶ月）:")
print(df_growth['return_3M'].describe())

print("\n株価騰落率（6ヶ月）:")
print(df_growth['return_6M'].describe())
