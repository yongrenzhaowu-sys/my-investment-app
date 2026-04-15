# -*- coding: utf-8 -*-
"""
月足最安値R2仮説の統計検証

仮説: 過去3ヶ月の月足最安値でR2 >= 0.98なら次月上昇

検証内容:
1. 各月末時点で過去3ヶ月の最安値を取得
2. 線形回帰を実施してR2を計算
3. R2 >= 0.98の銘柄の次月リターンを分析
4. 統計的有意性を検定
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
print("月足最安値R2仮説の統計検証")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/5] データ読み込み...")

df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2016-01-01'].copy()

print(f"価格データ: {len(df_price):,} 行")
print(f"期間: {df_price['date'].min().date()} ~ {df_price['date'].max().date()}")
print(f"銘柄数: {df_price['code'].nunique():,}")

# ================================================================================
# 2. 月次最安値の集計
# ================================================================================

print("\n[2/5] 月次最安値を集計...")

# 年月カラムを追加
df_price['year_month'] = df_price['date'].dt.to_period('M')

# 各銘柄×月の最安値を集計
df_monthly_low = df_price.groupby(['code', 'year_month']).agg({
    'low': 'min',
    'adjusted_close': 'last'  # 月末終値（次月リターン計算用）
}).reset_index()

df_monthly_low = df_monthly_low.sort_values(['code', 'year_month'])

print(f"月次データ: {len(df_monthly_low):,} 行")
print(f"月数: {df_monthly_low['year_month'].nunique()} ヶ月")

# ================================================================================
# 3. R2計算
# ================================================================================

print("\n[3/5] 過去3ヶ月の最安値でR2を計算...")

results = []

# 銘柄ごとに処理
for code, group in df_monthly_low.groupby('code'):
    group = group.sort_values('year_month').reset_index(drop=True)

    # 過去3ヶ月のデータが必要なので、4ヶ月目から開始
    for i in range(3, len(group)):
        # 過去3ヶ月の最安値
        past_3_months = group.iloc[i-3:i]

        if len(past_3_months) < 3:
            continue

        # 最安値の配列
        low_values = past_3_months['low'].values

        # 線形回帰（x = 0, 1, 2）
        x = np.array([0, 1, 2])
        y = low_values

        # 線形回帰の係数を計算
        coefficients = np.polyfit(x, y, deg=1)
        slope, intercept = coefficients[0], coefficients[1]

        # 予測値
        y_pred = slope * x + intercept

        # R2（決定係数）を計算
        ss_res = np.sum((y - y_pred) ** 2)  # 残差平方和
        ss_tot = np.sum((y - np.mean(y)) ** 2)  # 全平方和

        if ss_tot > 0:
            r_squared = 1 - (ss_res / ss_tot)
        else:
            r_squared = 0

        # 現在の月末終値
        current_close = group.iloc[i-1]['adjusted_close']

        # 次月のリターンを計算（次のデータがあれば）
        if i < len(group):
            next_month_close = group.iloc[i]['adjusted_close']
            next_month_return = (next_month_close - current_close) / current_close
        else:
            next_month_return = np.nan

        # 結果を記録
        results.append({
            'code': code,
            'year_month': group.iloc[i-1]['year_month'],
            'r_squared': r_squared,
            'slope': slope,
            'low_0': low_values[0],
            'low_1': low_values[1],
            'low_2': low_values[2],
            'current_close': current_close,
            'next_month_return': next_month_return
        })

df_results = pd.DataFrame(results)

print(f"R2計算完了: {len(df_results):,} サンプル")

# ================================================================================
# 4. R2 >= 0.98の銘柄を抽出
# ================================================================================

print("\n[4/5] R2 >= 0.98の銘柄を抽出...")

# 次月リターンが計算できるサンプルのみ使用
df_valid = df_results[df_results['next_month_return'].notna()].copy()

print(f"有効サンプル数: {len(df_valid):,}")

# R2の閾値で分類
thresholds = [0.98, 0.95, 0.90, 0.80]

for threshold in thresholds:
    df_high_r2 = df_valid[df_valid['r_squared'] >= threshold]
    df_low_r2 = df_valid[df_valid['r_squared'] < threshold]

    print(f"\n--- R2 >= {threshold} の分析 ---")
    print(f"該当サンプル数: {len(df_high_r2):,} ({len(df_high_r2)/len(df_valid)*100:.2f}%)")

    if len(df_high_r2) > 0:
        # 次月リターンの統計
        mean_return_high = df_high_r2['next_month_return'].mean()
        median_return_high = df_high_r2['next_month_return'].median()
        std_return_high = df_high_r2['next_month_return'].std()
        win_rate_high = (df_high_r2['next_month_return'] > 0).mean()

        print(f"平均次月リターン: {mean_return_high*100:.2f}%")
        print(f"中央値: {median_return_high*100:.2f}%")
        print(f"標準偏差: {std_return_high*100:.2f}%")
        print(f"勝率: {win_rate_high*100:.1f}%")

        # 比較群（R2 < threshold）
        if len(df_low_r2) > 0:
            mean_return_low = df_low_r2['next_month_return'].mean()
            win_rate_low = (df_low_r2['next_month_return'] > 0).mean()

            print(f"\n比較群 (R2 < {threshold}):")
            print(f"平均次月リターン: {mean_return_low*100:.2f}%")
            print(f"勝率: {win_rate_low*100:.1f}%")

            # t検定（手動実装）
            n1 = len(df_high_r2)
            n2 = len(df_low_r2)

            if n1 > 1 and n2 > 1:
                var1 = df_high_r2['next_month_return'].var()
                var2 = df_low_r2['next_month_return'].var()

                # プールされた標準偏差
                pooled_std = np.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))

                # t統計量
                t_stat = (mean_return_high - mean_return_low) / (pooled_std * np.sqrt(1/n1 + 1/n2))

                print(f"\nt検定結果:")
                print(f"t統計量: {t_stat:.3f}")
                print(f"サンプル数: n1={n1}, n2={n2}")

                if abs(t_stat) > 1.96:
                    print("=> t統計量が1.96超（おおよそp<0.05に相当）")
                else:
                    print("=> t統計量が1.96以下（有意差なし）")
    else:
        print("該当サンプルなし")

# ================================================================================
# 5. 詳細分析
# ================================================================================

print("\n" + "="*80)
print("[5/5] 詳細分析")
print("="*80)

# R2 >= 0.98の詳細
df_r98 = df_valid[df_valid['r_squared'] >= 0.98]

if len(df_r98) > 0:
    print(f"\nR2 >= 0.98の詳細統計:")
    print(f"サンプル数: {len(df_r98):,}")
    print(f"\n次月リターンの分布:")
    print(df_r98['next_month_return'].describe())

    # 月別の発生頻度
    print(f"\n月別の発生頻度:")
    monthly_counts = df_r98.groupby('year_month').size().sort_values(ascending=False)
    print(monthly_counts.head(10))

    # slope（傾き）の分布
    print(f"\nslope（傾き）の統計:")
    print(df_r98['slope'].describe())

    # 極端なリターンの確認
    print(f"\n次月リターン上位10件:")
    top_10 = df_r98.nlargest(10, 'next_month_return')[['code', 'year_month', 'r_squared', 'next_month_return']]
    for idx, row in top_10.iterrows():
        print(f"  {row['code']} ({row['year_month']}): R2={row['r_squared']:.4f}, リターン={row['next_month_return']*100:.2f}%")

    print(f"\n次月リターン下位10件:")
    bottom_10 = df_r98.nsmallest(10, 'next_month_return')[['code', 'year_month', 'r_squared', 'next_month_return']]
    for idx, row in bottom_10.iterrows():
        print(f"  {row['code']} ({row['year_month']}): R2={row['r_squared']:.4f}, リターン={row['next_month_return']*100:.2f}%")
else:
    print("\nR2 >= 0.98の該当サンプルなし")

# ================================================================================
# 結果保存
# ================================================================================

output_dir = PROJECT_ROOT / 'analyses' / '20260221_2300_monthly_low_r2_validation'
df_results.to_csv(output_dir / 'r2_analysis_results.csv', index=False, encoding='utf-8-sig')

print(f"\n結果を保存: {output_dir / 'r2_analysis_results.csv'}")

# ================================================================================
# 結論
# ================================================================================

print("\n" + "="*80)
print("結論")
print("="*80)

if len(df_r98) > 0:
    mean_r98 = df_r98['next_month_return'].mean()
    win_rate_r98 = (df_r98['next_month_return'] > 0).mean()

    print(f"\n仮説: 「R2 >= 0.98なら次月上昇」")
    print(f"検証結果:")
    print(f"  - 該当サンプル数: {len(df_r98):,} ({len(df_r98)/len(df_valid)*100:.2f}%)")
    print(f"  - 平均次月リターン: {mean_r98*100:.2f}%")
    print(f"  - 勝率: {win_rate_r98*100:.1f}%")

    if mean_r98 > 0 and win_rate_r98 > 0.5:
        print(f"\n=> 仮説は「部分的に正しい」可能性あり")
        print(f"   （ただし、統計的有意性とサンプル数を考慮）")
    else:
        print(f"\n=> 仮説は「誤り」または「限定的」")
else:
    print(f"\n仮説: 「R2 >= 0.98なら次月上昇」")
    print(f"検証結果: R2 >= 0.98の該当サンプルなし")
    print(f"\n=> 仮説は検証不可（条件が厳しすぎる）")

print("\n完了!")
