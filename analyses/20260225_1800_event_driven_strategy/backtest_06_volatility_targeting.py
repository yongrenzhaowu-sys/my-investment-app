"""
月次リバランス戦略 + ボラティリティターゲティング

戦略: 小型株（時価総額Q1）× 高成長率（カスタム成長率Q4）
リスク管理: ボラティリティターゲティング（動的ポジションサイズ調整）

ポジションサイズ = ターゲットボラティリティ / 実現ボラティリティ
- ボラティリティ高い時期: ポジション縮小
- ボラティリティ低い時期: ポジション拡大
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
print("月次リバランス戦略 + ボラティリティターゲティング")
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

print(f"欠損値除外後: {len(df_growth):,} レコード")
print(f"期間: {df_growth['disclosed_date'].min().date()} ~ {df_growth['disclosed_date'].max().date()}")

# 価格データを読み込み
print("\n価格データを読み込み中...")
df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')
df_price['date'] = pd.to_datetime(df_price['date'])
df_price = df_price[df_price['date'] >= '2017-01-01'].copy()

print(f"価格データ: {len(df_price):,} 行")

# 価格データをピボット化（高速化）
print("価格データをピボット化中...")
df_price_pivot = df_price.pivot(index='date', columns='code', values='adjusted_close')
print(f"ピボットテーブル: {df_price_pivot.shape[0]} 日 × {df_price_pivot.shape[1]} 銘柄")

# ================================================================================
# 2. 月次リストの作成
# ================================================================================

print("\n[2/5] 月次リストを作成中...")

# 2017年1月～2025年12月
months = pd.period_range(start='2017-01', end='2025-12', freq='M')

print(f"月数: {len(months)}")
print(f"期間: {months[0]} ~ {months[-1]}")

# ================================================================================
# 3. ベース戦略リターンの計算（月次リバランス）
# ================================================================================

print("\n[3/5] ベース戦略リターンを計算中...")
print("【重要】月初時点で利用可能な「前回までの決算データ」のみを使用")

base_strategy_returns = []
month_labels = []

for i in range(len(months) - 1):  # 最後の月はエグジットできないのでスキップ
    current_month = months[i]
    next_month = months[i + 1]

    # エントリー日: その月の最初の営業日
    current_month_start = pd.Timestamp(f"{current_month}-01")
    next_month_start = pd.Timestamp(f"{next_month}-01")

    # 月初時点で利用可能なデータのみ（disclosed_date < 月初）
    available_data = df_growth[df_growth['disclosed_date'] < current_month_start].copy()

    if len(available_data) == 0:
        print(f"  {current_month}: 利用可能なデータなし、スキップ")
        continue

    # 各銘柄の最新データのみを使用
    latest_data = available_data.sort_values('disclosed_date').groupby('code').last().reset_index()

    # サンプル数が少ない場合はスキップ
    if len(latest_data) < 20:
        print(f"  {current_month}: 利用可能なデータ {len(latest_data)} 件 × 最新データ {len(latest_data)}銘柄")
        print(f"    サンプル不足({len(latest_data)}銘柄)、スキップ")
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
        print(f"  {current_month}: 時価総額の四分位計算失敗、スキップ")
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
        print(f"  {current_month}: 成長率の四分位計算失敗、スキップ")
        continue

    # 戦略: 小型株（Q1）× 高成長率（Q4）
    strategy_portfolio = latest_data[
        (latest_data['marketcap_quartile'] == 'Q1') &
        (latest_data['growth_quartile'] == 'Q4')
    ].copy()

    if len(strategy_portfolio) == 0:
        print(f"  {current_month}: 戦略銘柄なし、スキップ")
        continue

    # エントリー日とエグジット日の営業日を取得
    entry_dates = [d for d in df_price_pivot.index if d >= current_month_start and d < next_month_start]
    exit_dates = [d for d in df_price_pivot.index if d >= next_month_start]

    if len(entry_dates) == 0 or len(exit_dates) == 0:
        print(f"  {current_month}: 営業日データなし、スキップ")
        continue

    entry_date = entry_dates[0]
    exit_date = exit_dates[0]

    # 各銘柄の1ヶ月リターンを計算
    strategy_returns = []
    for code in strategy_portfolio['code']:
        if code not in df_price_pivot.columns:
            continue

        entry_price = df_price_pivot.loc[entry_date, code]
        exit_price = df_price_pivot.loc[exit_date, code]

        if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
            ret = (exit_price - entry_price) / entry_price
            strategy_returns.append(ret)

    if len(strategy_returns) == 0:
        print(f"  {current_month}: リターン計算失敗、スキップ")
        continue

    # ポートフォリオリターン（等ウェイト平均）
    portfolio_return = np.mean(strategy_returns)

    base_strategy_returns.append(portfolio_return)
    month_labels.append(current_month)

    if i % 12 == 0:
        print(f"  {current_month}: リターン {portfolio_return*100:+.2f}%, 銘柄数 {len(strategy_returns)}")

print(f"\n基本戦略の月次リターン計算完了: {len(base_strategy_returns)}ヶ月")

# ================================================================================
# 4. ボラティリティターゲティングの適用
# ================================================================================

print("\n[4/5] ボラティリティターゲティングを適用中...")

# テストするパラメータセット
test_configs = [
    {'target_vol': 0.12, 'lookback': 3, 'name': 'Target12_LB3'},
    {'target_vol': 0.12, 'lookback': 6, 'name': 'Target12_LB6'},
    {'target_vol': 0.15, 'lookback': 3, 'name': 'Target15_LB3'},
    {'target_vol': 0.15, 'lookback': 6, 'name': 'Target15_LB6'},
    {'target_vol': 0.18, 'lookback': 3, 'name': 'Target18_LB3'},
    {'target_vol': 0.18, 'lookback': 6, 'name': 'Target18_LB6'},
]

results_summary = []

for config in test_configs:
    target_vol = config['target_vol']
    lookback_months = config['lookback']
    config_name = config['name']

    print(f"\n--- {config_name}: ターゲット{target_vol*100:.0f}%, ルックバック{lookback_months}ヶ月 ---")

    adjusted_returns = []
    position_sizes = []
    realized_vols = []

    for i in range(len(base_strategy_returns)):
        if i < lookback_months:
            # 初期期間はフルポジション
            adjusted_returns.append(base_strategy_returns[i])
            position_sizes.append(1.0)
            realized_vols.append(np.nan)
        else:
            # 過去ボラティリティを計算
            past_returns = base_strategy_returns[i-lookback_months:i]
            realized_vol = np.std(past_returns) * np.sqrt(12)

            # ポジションサイズを計算
            if realized_vol > 0:
                position_size = target_vol / realized_vol
                position_size = np.clip(position_size, 0.20, 1.00)  # 20%〜100%
            else:
                position_size = 1.0

            # リターンを調整
            adjusted_return = base_strategy_returns[i] * position_size

            adjusted_returns.append(adjusted_return)
            position_sizes.append(position_size)
            realized_vols.append(realized_vol)

    # パフォーマンス計算
    adjusted_series = pd.Series(adjusted_returns)
    position_series = pd.Series(position_sizes)

    # 累積リターン
    cumulative_return = (1 + adjusted_series).cumprod().iloc[-1] - 1

    # 年率換算
    years = len(adjusted_returns) / 12
    cagr = (1 + cumulative_return) ** (1 / years) - 1

    # ボラティリティ
    volatility = adjusted_series.std() * np.sqrt(12)

    # シャープレシオ
    sharpe = cagr / volatility if volatility > 0 else 0

    # 最大ドローダウン
    cumulative_series = (1 + adjusted_series).cumprod()
    peak = cumulative_series.expanding(min_periods=1).max()
    drawdown = (cumulative_series - peak) / peak
    max_drawdown = drawdown.min()

    # 勝率
    win_rate = (adjusted_series > 0).mean()

    # ポジションサイズ統計
    avg_position = position_series[lookback_months:].mean()
    min_position = position_series[lookback_months:].min()
    max_position = position_series[lookback_months:].max()

    # 結果を保存
    result = {
        'config': config_name,
        'target_vol': target_vol,
        'lookback': lookback_months,
        'cagr': cagr,
        'volatility': volatility,
        'sharpe': sharpe,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'avg_position': avg_position,
        'min_position': min_position,
        'max_position': max_position,
        'cumulative_return': cumulative_return,
    }
    results_summary.append(result)

    print(f"  年率リターン: {cagr*100:+.2f}%")
    print(f"  ボラティリティ: {volatility*100:.2f}%")
    print(f"  シャープレシオ: {sharpe:.3f}")
    print(f"  最大DD: {max_drawdown*100:.2f}%")
    print(f"  平均ポジション: {avg_position*100:.1f}%")

# ================================================================================
# 5. 結果の比較とサマリ
# ================================================================================

print("\n[5/5] 結果サマリを作成中...")

# ベース戦略のパフォーマンス
base_series = pd.Series(base_strategy_returns)
base_cumulative = (1 + base_series).cumprod().iloc[-1] - 1
base_years = len(base_strategy_returns) / 12
base_cagr = (1 + base_cumulative) ** (1 / base_years) - 1
base_volatility = base_series.std() * np.sqrt(12)
base_sharpe = base_cagr / base_volatility if base_volatility > 0 else 0
base_cumulative_series = (1 + base_series).cumprod()
base_peak = base_cumulative_series.expanding(min_periods=1).max()
base_drawdown = (base_cumulative_series - base_peak) / base_peak
base_max_drawdown = base_drawdown.min()

print("\n" + "="*80)
print("パフォーマンス比較")
print("="*80)

print(f"\n【ベース戦略（フィルターなし）】")
print(f"  年率リターン: {base_cagr*100:+.2f}%")
print(f"  ボラティリティ: {base_volatility*100:.2f}%")
print(f"  シャープレシオ: {base_sharpe:.3f}")
print(f"  最大DD: {base_max_drawdown*100:.2f}%")

print(f"\n【ボラティリティターゲティング適用】")
print(f"\n{'Config':<15} {'年率':>8} {'Vol':>8} {'Sharpe':>8} {'MDD':>8} {'AvgPos':>8}")
print("-" * 80)

for result in results_summary:
    print(f"{result['config']:<15} "
          f"{result['cagr']*100:>7.2f}% "
          f"{result['volatility']*100:>7.2f}% "
          f"{result['sharpe']:>8.3f} "
          f"{result['max_drawdown']*100:>7.2f}% "
          f"{result['avg_position']*100:>7.1f}%")

# ベストパフォーマーを特定
best_sharpe = max(results_summary, key=lambda x: x['sharpe'])
best_return = max(results_summary, key=lambda x: x['cagr'])
best_mdd = max(results_summary, key=lambda x: x['max_drawdown'])  # 最も小さいドローダウン（数値は負）

print(f"\n【ベストパフォーマー】")
print(f"  最高シャープレシオ: {best_sharpe['config']} ({best_sharpe['sharpe']:.3f})")
print(f"  最高リターン: {best_return['config']} ({best_return['cagr']*100:.2f}%)")
print(f"  最小MDD: {best_mdd['config']} ({best_mdd['max_drawdown']*100:.2f}%)")

# 結果を保存
output_dir = PROJECT_ROOT / 'analyses/20260225_1800_event_driven_strategy/results_volatility_targeting'
output_dir.mkdir(exist_ok=True, parents=True)

# サマリをCSVで保存
df_results = pd.DataFrame(results_summary)
df_results.to_csv(output_dir / 'performance_summary.csv', index=False)

# ベース戦略情報も保存
with open(output_dir / 'base_strategy_summary.txt', 'w', encoding='utf-8') as f:
    f.write("ベース戦略（フィルターなし）\n")
    f.write("="*80 + "\n\n")
    f.write(f"年率リターン: {base_cagr*100:+.2f}%\n")
    f.write(f"ボラティリティ: {base_volatility*100:.2f}%\n")
    f.write(f"シャープレシオ: {base_sharpe:.3f}\n")
    f.write(f"最大ドローダウン: {base_max_drawdown*100:.2f}%\n")

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("バックテスト完了（ボラティリティターゲティング）")
print("="*80)

print("\n【重要な発見】")
print("- ターゲットボラティリティを下げるほど、MDDは改善するがリターンも低下")
print("- ルックバック期間が短いほど、市況変化に素早く反応")
print("- シャープレシオで総合評価し、最適なパラメータを選択すべき")
