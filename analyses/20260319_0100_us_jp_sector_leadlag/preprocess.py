"""
前処理・リターン計算

1. Close-to-Closeリターン（相関行列推定用）
2. Open-to-Closeリターン（戦略評価用、日本のみ）
3. 共通営業日の抽出（米国t日と日本t+1日が両方存在）
"""
import pandas as pd
import numpy as np
from pathlib import Path

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data/raw/us_jp_leadlag"
OUTPUT_DIR = PROJECT_ROOT / "data/processed/us_jp_leadlag"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("="*80)
print("前処理・リターン計算")
print("="*80)

# データ読み込み
print("\n[1] データ読み込み")
us_df = pd.read_parquet(INPUT_DIR / "us_sectors.parquet")
jp_df = pd.read_parquet(INPUT_DIR / "jp_sectors.parquet")

print(f"  米国: {len(us_df):,}レコード")
print(f"  日本: {len(jp_df):,}レコード")

# 日付型に変換
us_df['Date'] = pd.to_datetime(us_df['Date'])
jp_df['Date'] = pd.to_datetime(jp_df['Date'])

# yfinance auto_adjust=True使用（すでに調整済み価格）
print("\n[2] データ確認")
print("  注意: yfinance auto_adjust=True使用（すでに調整済み価格）")
print(f"  米国: {us_df.columns.tolist()}")
print(f"  日本: {jp_df.columns.tolist()}")

# Close-to-Closeリターン計算（相関行列推定用）
print("\n[3] Close-to-Closeリターン計算")

# 米国
us_cc = us_df.pivot(index='Date', columns='Ticker', values='Close').sort_index()
us_returns_cc = us_cc.pct_change()
print(f"  米国: {us_returns_cc.shape[0]}日 × {us_returns_cc.shape[1]}銘柄")

# 日本
jp_cc = jp_df.pivot(index='Date', columns='Ticker', values='Close').sort_index()
jp_returns_cc = jp_cc.pct_change()
print(f"  日本: {jp_returns_cc.shape[0]}日 × {jp_returns_cc.shape[1]}銘柄")

# Open-to-Closeリターン計算（日本のみ、戦略評価用）
print("\n[4] Open-to-Closeリターン計算（日本）")
jp_open = jp_df.pivot(index='Date', columns='Ticker', values='Open').sort_index()
jp_close = jp_df.pivot(index='Date', columns='Ticker', values='Close').sort_index()
jp_returns_oc = (jp_close / jp_open) - 1
print(f"  日本OC: {jp_returns_oc.shape[0]}日 × {jp_returns_oc.shape[1]}銘柄")

# 共通営業日の抽出
# 米国t日と日本t+1日が両方存在する日のみ
print("\n[5] 共通営業日の抽出")
print("  条件: 米国t日と日本t+1日が両方存在")

# 米国の日付
us_dates = us_returns_cc.index

# 日本の日付（1日前にシフト、米国t日に対応）
jp_dates_shifted = jp_returns_cc.index - pd.Timedelta(days=1)

# 共通の日付を見つける（近似マッチング）
common_dates = []
for us_date in us_dates:
    # 米国t日の翌営業日（日本t+1日）を探す
    jp_next_dates = jp_returns_cc.index[jp_returns_cc.index > us_date]
    if len(jp_next_dates) > 0:
        jp_next_date = jp_next_dates[0]
        # 10日以内なら共通日として認識
        if (jp_next_date - us_date).days <= 10:
            common_dates.append({
                'US_Date': us_date,
                'JP_Date': jp_next_date
            })

common_df = pd.DataFrame(common_dates)
print(f"  共通営業日: {len(common_df)}日")

# データセット構築
print("\n[6] データセット構築")

# 米国Close-to-Closeリターン（時点t）
us_cc_aligned = us_returns_cc.loc[common_df['US_Date']].reset_index(drop=True)
us_cc_aligned.columns = [f'US_CC_{col}' for col in us_cc_aligned.columns]

# 日本Close-to-Closeリターン（時点t+1）
jp_cc_aligned = jp_returns_cc.loc[common_df['JP_Date']].reset_index(drop=True)
jp_cc_aligned.columns = [f'JP_CC_{col}' for col in jp_cc_aligned.columns]

# 日本Open-to-Closeリターン（時点t+1）
jp_oc_aligned = jp_returns_oc.loc[common_df['JP_Date']].reset_index(drop=True)
jp_oc_aligned.columns = [f'JP_OC_{col}' for col in jp_oc_aligned.columns]

# 日付情報
dates_df = pd.DataFrame({
    'US_Date': common_df['US_Date'].values,
    'JP_Date': common_df['JP_Date'].values
})

# 結合
final_df = pd.concat([dates_df, us_cc_aligned, jp_cc_aligned, jp_oc_aligned], axis=1)

print(f"  最終データセット: {len(final_df)}日 × {len(final_df.columns)}列")

# NaN除外
print("\n[7] 欠損値処理")
before_count = len(final_df)
final_df = final_df.dropna()
after_count = len(final_df)
print(f"  除外前: {before_count}日")
print(f"  除外後: {after_count}日")
print(f"  除外数: {before_count - after_count}日")

# 保存
output_path = OUTPUT_DIR / "returns.parquet"
final_df.to_parquet(output_path, index=False)
print(f"\n[8] 保存完了: {output_path}")

# サマリー
print("\n[9] データセットサマリー")
print(f"  期間: {final_df['US_Date'].min().date()} ~ {final_df['US_Date'].max().date()}")
print(f"  日数: {len(final_df)}日")
print(f"  米国CC列: {len([c for c in final_df.columns if c.startswith('US_CC')])}列")
print(f"  日本CC列: {len([c for c in final_df.columns if c.startswith('JP_CC')])}列")
print(f"  日本OC列: {len([c for c in final_df.columns if c.startswith('JP_OC')])}列")

print("\n完了")
