"""
真のイベントドリブン戦略のバックテスト（サンプル版：2018年1年間）

戦略: 小型株（時価総額Q1）× 高成長率（カスタム成長率Q4）
エントリー: 決算発表日の翌営業日
エグジット: エントリーから21営業日後（約1ヶ月）
保有期間: 約1ヶ月

重要: 決算発表日の翌営業日に正確にエントリー（月次集計ではない）
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
import json
from datetime import timedelta
warnings.filterwarnings('ignore')

# プロジェクトルート
PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("真のイベントドリブン戦略のバックテスト（サンプル版：2019年）")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/5] データ読み込み中...")

# 既存の成長率データを読み込む
df_growth = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_by_marketcap/growth_rate_by_marketcap.csv',
    parse_dates=['disclosed_date']
)

print(f"成長率データ: {len(df_growth):,} レコード")

# 必要な列のみ抽出
df_growth = df_growth[['code', 'disclosed_date', 'custom_growth_rate', 'market_cap']].copy()
df_growth = df_growth.dropna()

# 2019年のデータのみ
df_growth = df_growth[
    (df_growth['disclosed_date'] >= '2019-01-01') &
    (df_growth['disclosed_date'] < '2020-01-01')
].copy()

print(f"2019年データ: {len(df_growth):,} レコード")
print(f"期間: {df_growth['disclosed_date'].min().date()} ~ {df_growth['disclosed_date'].max().date()}")

# 価格データを読み込み
print("\n価格データを読み込み中...")
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[
    (df_price['date'] >= '2018-01-01') &
    (df_price['date'] < '2020-12-31')
].copy()

print(f"価格データ: {len(df_price):,} 行")

# 価格データをピボット化（高速化）
print("価格データをピボット化中...")
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')
print(f"ピボットテーブル: {df_price_pivot.shape[0]} 日 × {df_price_pivot.shape[1]} 銘柄")

# 営業日リスト
trading_days = sorted(df_price_pivot.index)
trading_days_set = set(trading_days)

def get_next_trading_day(date, trading_days):
    """指定日の翌営業日を取得"""
    for td in trading_days:
        if td > date:
            return td
    return None

def get_trading_day_after_n_days(start_date, n_days, trading_days):
    """start_dateからn営業日後の日付を取得"""
    idx = trading_days.index(start_date)
    target_idx = idx + n_days
    if target_idx < len(trading_days):
        return trading_days[target_idx]
    return None

# ================================================================================
# 2. 決算発表日ごとのイベント処理
# ================================================================================

print("\n[2/5] 決算発表イベントを処理中...")

# 決算発表日のユニークリストを取得（日付順）
disclosed_dates = sorted(df_growth['disclosed_date'].unique())
print(f"決算発表日数: {len(disclosed_dates)}日")

positions = []  # (code, entry_date, exit_date, entry_price, exit_price)

for i, disclosed_date in enumerate(disclosed_dates):
    if i % 50 == 0:
        print(f"  処理中: {i}/{len(disclosed_dates)} ({i/len(disclosed_dates)*100:.1f}%)")

    # その日に決算発表があった銘柄
    disclosed_today = df_growth[df_growth['disclosed_date'] == disclosed_date].copy()

    # その時点で利用可能なデータ（disclosed_date <= disclosed_dateの最新データ）
    available_data = df_growth[df_growth['disclosed_date'] <= disclosed_date].copy()
    latest_data = available_data.sort_values('disclosed_date').groupby('code').last().reset_index()

    # サンプル数が少ない場合はスキップ
    if len(latest_data) < 20:
        continue

    # 時価総額の四分位を計算
    try:
        latest_data['marketcap_quartile'] = pd.qcut(
            latest_data['market_cap'],
            q=4,
            labels=['Q1', 'Q2', 'Q3', 'Q4'],
            duplicates='drop'
        )
    except ValueError:
        continue

    # カスタム成長率の四分位を計算
    try:
        latest_data['growth_quartile'] = pd.qcut(
            latest_data['custom_growth_rate'],
            q=4,
            labels=['Q1', 'Q2', 'Q3', 'Q4'],
            duplicates='drop'
        )
    except ValueError:
        continue

    # 戦略: 小型株（Q1）× 高成長率（Q4）かつ、その日に決算発表があった銘柄
    strategy_candidates = latest_data[
        (latest_data['marketcap_quartile'] == 'Q1') &
        (latest_data['growth_quartile'] == 'Q4')
    ].copy()

    # その日に決算発表があった銘柄のみ
    disclosed_codes = set(disclosed_today['code'])
    strategy_portfolio = strategy_candidates[strategy_candidates['code'].isin(disclosed_codes)].copy()

    if len(strategy_portfolio) == 0:
        continue

    # エントリー日: 決算発表日の翌営業日
    entry_date = get_next_trading_day(disclosed_date, trading_days)
    if entry_date is None:
        continue

    # エグジット日: エントリーから21営業日後
    exit_date = get_trading_day_after_n_days(entry_date, 21, trading_days)
    if exit_date is None:
        continue

    # 各銘柄のポジションを記録
    for code in strategy_portfolio['code']:
        if code not in df_price_pivot.columns:
            continue

        entry_price = df_price_pivot.loc[entry_date, code]
        exit_price = df_price_pivot.loc[exit_date, code]

        if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
            positions.append({
                'code': code,
                'disclosed_date': disclosed_date,
                'entry_date': entry_date,
                'exit_date': exit_date,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'return': (exit_price - entry_price) / entry_price
            })

print(f"\n総ポジション数: {len(positions)}")

# ================================================================================
# 3. 日次ポートフォリオの構築
# ================================================================================

print("\n[3/5] 日次ポートフォリオを構築中...")

df_positions = pd.DataFrame(positions)

# 各日のアクティブなポジションを集計
daily_portfolio = {}

for date in trading_days:
    if date < pd.Timestamp('2019-01-01') or date >= pd.Timestamp('2020-01-01'):
        continue

    # その日にアクティブなポジション
    active = df_positions[
        (df_positions['entry_date'] <= date) &
        (df_positions['exit_date'] > date)
    ]

    if len(active) > 0:
        daily_portfolio[date] = {
            'count': len(active),
            'codes': list(active['code'])
        }

print(f"ポートフォリオがアクティブな日数: {len(daily_portfolio)}")
print(f"平均ポジション数: {np.mean([p['count'] for p in daily_portfolio.values()]):.1f}")

# ================================================================================
# 4. パフォーマンス計算
# ================================================================================

print("\n[4/5] パフォーマンスを計算中...")

# 全ポジションの平均リターン
total_return = df_positions['return'].mean()
print(f"\n全ポジションの平均リターン: {total_return*100:+.2f}%")
print(f"総ポジション数: {len(df_positions)}")
print(f"勝率: {(df_positions['return'] > 0).mean()*100:.2f}%")

# 月次リターンに集約
df_positions['entry_month'] = pd.to_datetime(df_positions['entry_date']).dt.to_period('M')
monthly_returns = df_positions.groupby('entry_month')['return'].mean()

print(f"\n月次リターン:")
for month, ret in monthly_returns.items():
    print(f"  {month}: {ret*100:+6.2f}%")

# 累積リターン
cumulative_return = (1 + monthly_returns).cumprod() - 1
final_cumulative_return = cumulative_return.iloc[-1]

# 年率換算
months_count = len(monthly_returns)
years = months_count / 12
cagr = (1 + final_cumulative_return) ** (1 / years) - 1

# ボラティリティ
volatility = monthly_returns.std() * np.sqrt(12)

# シャープレシオ
sharpe = cagr / volatility if volatility > 0 else 0

# 最大ドローダウン
cumulative_series = (1 + monthly_returns).cumprod()
peak = cumulative_series.expanding(min_periods=1).max()
drawdown = (cumulative_series - peak) / peak
max_drawdown = drawdown.min()

# ベンチマーク（全銘柄の平均）
print("\nベンチマーク計算中...")

# 2019年の全銘柄の月次リターンを計算
benchmark_monthly = []
for month in pd.period_range('2019-01', '2019-12', freq='M'):
    month_start = pd.Timestamp(f"{month}-01")
    next_month = month + 1
    next_month_start = pd.Timestamp(f"{next_month}-01")

    # 月初と翌月初の営業日を取得
    entry_dates = [d for d in trading_days if d >= month_start]
    if len(entry_dates) == 0:
        continue
    entry_date = entry_dates[0]

    exit_dates = [d for d in trading_days if d >= next_month_start]
    if len(exit_dates) == 0:
        continue
    exit_date = exit_dates[0]

    # 全銘柄の平均リターン
    returns = []
    for code in df_price_pivot.columns:
        entry_price = df_price_pivot.loc[entry_date, code]
        exit_price = df_price_pivot.loc[exit_date, code]
        if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
            ret = (exit_price - entry_price) / entry_price
            returns.append(ret)

    if len(returns) > 0:
        benchmark_monthly.append(np.mean(returns))

benchmark_monthly_series = pd.Series(benchmark_monthly)
benchmark_cumulative_return = (1 + benchmark_monthly_series).cumprod().iloc[-1] - 1
benchmark_cagr = (1 + benchmark_cumulative_return) ** (1 / years) - 1
benchmark_volatility = benchmark_monthly_series.std() * np.sqrt(12)
benchmark_sharpe = benchmark_cagr / benchmark_volatility if benchmark_volatility > 0 else 0

# ================================================================================
# 5. 結果の出力
# ================================================================================

print("\n" + "="*80)
print("パフォーマンスサマリ（2019年サンプル）")
print("="*80)

print(f"\n【真のイベントドリブン戦略】")
print(f"  累積リターン: {final_cumulative_return*100:+.2f}%")
print(f"  年率リターン: {cagr*100:+.2f}%")
print(f"  ボラティリティ: {volatility*100:.2f}%")
print(f"  シャープレシオ: {sharpe:.3f}")
print(f"  最大ドローダウン: {max_drawdown*100:.2f}%")
print(f"  総ポジション数: {len(df_positions)}")
print(f"  勝率: {(df_positions['return'] > 0).mean()*100:.2f}%")

print(f"\n【ベンチマーク（全銘柄）】")
print(f"  累積リターン: {benchmark_cumulative_return*100:+.2f}%")
print(f"  年率リターン: {benchmark_cagr*100:+.2f}%")
print(f"  ボラティリティ: {benchmark_volatility*100:.2f}%")
print(f"  シャープレシオ: {benchmark_sharpe:.3f}")

print(f"\n【アウトパフォーマンス】")
print(f"  年率: {(cagr - benchmark_cagr)*100:+.2f}%")

print("\n" + "="*80)
print("サンプルバックテスト完了")
print("="*80)

# 参考：月次集計版との比較用
print("\n【参考】月次集計版（2019年部分）の想定リターン:")
print("  月次集計版は月初にエントリーするため、タイミングがずれる")
print("  真のイベントドリブンは決算発表日の翌営業日にエントリー")
print("\n  → 真のイベントドリブンの方がタイミングが正確")
print("  → 情報の鮮度を最大化できる")
print("\n  2019年は上昇相場のため、タイミングの違いが明確に")
print("  どちらがより効果的かを確認できる")
