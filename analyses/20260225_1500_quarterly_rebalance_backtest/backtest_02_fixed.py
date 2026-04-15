"""
3ヶ月リバランス戦略のバックテスト（修正版・高速化）

修正点:
1. リバランス日の翌営業日の価格でエントリー
2. 次回リバランス日の翌営業日の価格でエグジット
3. その期間の実際のリターンを計算（return_3Mは使わない）

高速化:
1. 価格データを事前にピボット化
2. 既存の成長率データを再利用
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
print("3ヶ月リバランス戦略のバックテスト（修正版・高速化）")
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
# 2. リバランス日の設定
# ================================================================================

print("\n[2/5] リバランス日を設定中...")

# 3ヶ月ごとのリバランス日（1月、4月、7月、10月の1日）
rebalance_dates = pd.date_range(
    start='2017-04-01',
    end='2025-07-01',
    freq='3MS'
)

print(f"リバランス回数: {len(rebalance_dates)}")
print(f"リバランス日: {rebalance_dates[0].date()} ~ {rebalance_dates[-1].date()}")

# ================================================================================
# 3. バックテストの実行
# ================================================================================

print("\n[3/5] バックテストを実行中...")

portfolio_returns = []
benchmark_all_returns = []
benchmark_small_returns = []
portfolio_sizes = []
rebalance_records = []

for i in range(len(rebalance_dates)):
    rebalance_date = rebalance_dates[i]

    # 次回リバランス日（エグジット日）
    if i < len(rebalance_dates) - 1:
        next_rebalance_date = rebalance_dates[i + 1]
    else:
        # 最後のリバランスはスキップ（エグジット日がない）
        print(f"  {rebalance_date.date()}: 最後のリバランス、スキップ")
        continue

    # リバランス日時点で利用可能な最新の決算データを使用（未来参照防止）
    available_data = df_growth[df_growth['disclosed_date'] < rebalance_date].copy()

    if len(available_data) == 0:
        print(f"  {rebalance_date.date()}: データなし、スキップ")
        continue

    # 各銘柄の最新の決算データのみを使用
    latest_data = available_data.sort_values('disclosed_date').groupby('code').last().reset_index()

    # 時価総額の四分位を再計算
    latest_data['marketcap_quartile'] = pd.qcut(
        latest_data['market_cap'],
        q=4,
        labels=['Q1', 'Q2', 'Q3', 'Q4'],
        duplicates='drop'
    )

    # カスタム成長率の四分位を再計算
    latest_data['growth_quartile'] = pd.qcut(
        latest_data['custom_growth_rate'],
        q=4,
        labels=['Q1', 'Q2', 'Q3', 'Q4'],
        duplicates='drop'
    )

    # 戦略: 小型株（Q1）× 高成長率（Q4）
    strategy_portfolio = latest_data[
        (latest_data['marketcap_quartile'] == 'Q1') &
        (latest_data['growth_quartile'] == 'Q4')
    ].copy()

    # ベンチマーク1: 全銘柄
    benchmark_all = latest_data.copy()

    # ベンチマーク2: 小型株
    benchmark_small = latest_data[latest_data['marketcap_quartile'] == 'Q1'].copy()

    # エントリー価格を取得（リバランス日の翌営業日）
    entry_dates = df_price_pivot.index[df_price_pivot.index >= rebalance_date]
    if len(entry_dates) == 0:
        print(f"  {rebalance_date.date()}: エントリー日なし、スキップ")
        continue
    entry_date = entry_dates[0]

    # エグジット価格を取得（次回リバランス日の翌営業日）
    exit_dates = df_price_pivot.index[df_price_pivot.index >= next_rebalance_date]
    if len(exit_dates) == 0:
        print(f"  {rebalance_date.date()}: エグジット日なし、スキップ")
        continue
    exit_date = exit_dates[0]

    # 戦略ポートフォリオのリターンを計算
    strategy_returns = []
    for code in strategy_portfolio['code']:
        if code not in df_price_pivot.columns:
            continue
        entry_price = df_price_pivot.loc[entry_date, code]
        exit_price = df_price_pivot.loc[exit_date, code]
        if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
            ret = (exit_price - entry_price) / entry_price
            strategy_returns.append(ret)

    # ベンチマーク1（全銘柄）のリターンを計算
    benchmark_all_rets = []
    for code in benchmark_all['code']:
        if code not in df_price_pivot.columns:
            continue
        entry_price = df_price_pivot.loc[entry_date, code]
        exit_price = df_price_pivot.loc[exit_date, code]
        if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
            ret = (exit_price - entry_price) / entry_price
            benchmark_all_rets.append(ret)

    # ベンチマーク2（小型株）のリターンを計算
    benchmark_small_rets = []
    for code in benchmark_small['code']:
        if code not in df_price_pivot.columns:
            continue
        entry_price = df_price_pivot.loc[entry_date, code]
        exit_price = df_price_pivot.loc[exit_date, code]
        if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
            ret = (exit_price - entry_price) / entry_price
            benchmark_small_rets.append(ret)

    # 等ウェイトポートフォリオの平均リターン
    portfolio_return = np.mean(strategy_returns) if len(strategy_returns) > 0 else 0.0
    benchmark_all_return = np.mean(benchmark_all_rets) if len(benchmark_all_rets) > 0 else 0.0
    benchmark_small_return = np.mean(benchmark_small_rets) if len(benchmark_small_rets) > 0 else 0.0
    portfolio_size = len(strategy_returns)

    portfolio_returns.append(portfolio_return)
    benchmark_all_returns.append(benchmark_all_return)
    benchmark_small_returns.append(benchmark_small_return)
    portfolio_sizes.append(portfolio_size)

    rebalance_records.append({
        'rebalance_date': rebalance_date,
        'entry_date': entry_date,
        'exit_date': exit_date,
        'portfolio_return': portfolio_return,
        'benchmark_all_return': benchmark_all_return,
        'benchmark_small_return': benchmark_small_return,
        'portfolio_size': portfolio_size
    })

    print(f"  {rebalance_date.date()}: 戦略={portfolio_return*100:+6.2f}%, "
          f"全銘柄={benchmark_all_return*100:+6.2f}%, "
          f"小型株={benchmark_small_return*100:+6.2f}%, "
          f"銘柄数={portfolio_size}")

# ================================================================================
# 4. パフォーマンス指標の計算
# ================================================================================

print("\n[4/5] パフォーマンス指標を計算中...")

# DataFrameに変換
df_backtest = pd.DataFrame(rebalance_records)
df_backtest['rebalance_date'] = pd.to_datetime(df_backtest['rebalance_date'])

# 累積リターンの計算
df_backtest['cumulative_return_strategy'] = (1 + df_backtest['portfolio_return']).cumprod()
df_backtest['cumulative_return_all'] = (1 + df_backtest['benchmark_all_return']).cumprod()
df_backtest['cumulative_return_small'] = (1 + df_backtest['benchmark_small_return']).cumprod()

# 最終的な累積リターン
final_return_strategy = df_backtest['cumulative_return_strategy'].iloc[-1] - 1
final_return_all = df_backtest['cumulative_return_all'].iloc[-1] - 1
final_return_small = df_backtest['cumulative_return_small'].iloc[-1] - 1

# 年率リターン（CAGR）
years = len(df_backtest) * 3 / 12
cagr_strategy = (df_backtest['cumulative_return_strategy'].iloc[-1] ** (1 / years)) - 1
cagr_all = (df_backtest['cumulative_return_all'].iloc[-1] ** (1 / years)) - 1
cagr_small = (df_backtest['cumulative_return_small'].iloc[-1] ** (1 / years)) - 1

# ボラティリティ（年率）
volatility_strategy = df_backtest['portfolio_return'].std() * np.sqrt(4)
volatility_all = df_backtest['benchmark_all_return'].std() * np.sqrt(4)
volatility_small = df_backtest['benchmark_small_return'].std() * np.sqrt(4)

# シャープレシオ
sharpe_strategy = cagr_strategy / volatility_strategy if volatility_strategy > 0 else 0
sharpe_all = cagr_all / volatility_all if volatility_all > 0 else 0
sharpe_small = cagr_small / volatility_small if volatility_small > 0 else 0

# 最大ドローダウン
def calculate_max_drawdown(cumulative_returns):
    running_max = cumulative_returns.cummax()
    drawdown = (cumulative_returns - running_max) / running_max
    return drawdown.min()

mdd_strategy = calculate_max_drawdown(df_backtest['cumulative_return_strategy'])
mdd_all = calculate_max_drawdown(df_backtest['cumulative_return_all'])
mdd_small = calculate_max_drawdown(df_backtest['cumulative_return_small'])

# 勝率
win_rate_strategy = (df_backtest['portfolio_return'] > 0).sum() / len(df_backtest)
win_rate_all = (df_backtest['benchmark_all_return'] > 0).sum() / len(df_backtest)
win_rate_small = (df_backtest['benchmark_small_return'] > 0).sum() / len(df_backtest)

# ================================================================================
# 5. 結果の表示
# ================================================================================

print("\n" + "="*80)
print("パフォーマンスサマリ（修正版）")
print("="*80)

print(f"\nバックテスト期間: {df_backtest['rebalance_date'].iloc[0].date()} ~ {df_backtest['rebalance_date'].iloc[-1].date()}")
print(f"リバランス回数: {len(df_backtest)}")
print(f"運用期間: {years:.1f}年")

print("\n【累積リターン】")
print(f"  戦略（小型株×高成長）: {final_return_strategy*100:+7.2f}%")
print(f"  ベンチマーク（全銘柄）: {final_return_all*100:+7.2f}%")
print(f"  ベンチマーク（小型株）: {final_return_small*100:+7.2f}%")

print("\n【年率リターン（CAGR）】")
print(f"  戦略（小型株×高成長）: {cagr_strategy*100:+7.2f}%")
print(f"  ベンチマーク（全銘柄）: {cagr_all*100:+7.2f}%")
print(f"  ベンチマーク（小型株）: {cagr_small*100:+7.2f}%")

print("\n【ボラティリティ（年率）】")
print(f"  戦略（小型株×高成長）: {volatility_strategy*100:7.2f}%")
print(f"  ベンチマーク（全銘柄）: {volatility_all*100:7.2f}%")
print(f"  ベンチマーク（小型株）: {volatility_small*100:7.2f}%")

print("\n【シャープレシオ】")
print(f"  戦略（小型株×高成長）: {sharpe_strategy:7.3f}")
print(f"  ベンチマーク（全銘柄）: {sharpe_all:7.3f}")
print(f"  ベンチマーク（小型株）: {sharpe_small:7.3f}")

print("\n【最大ドローダウン】")
print(f"  戦略（小型株×高成長）: {mdd_strategy*100:+7.2f}%")
print(f"  ベンチマーク（全銘柄）: {mdd_all*100:+7.2f}%")
print(f"  ベンチマーク（小型株）: {mdd_small*100:+7.2f}%")

print("\n【勝率】")
print(f"  戦略（小型株×高成長）: {win_rate_strategy*100:7.2f}%")
print(f"  ベンチマーク（全銘柄）: {win_rate_all*100:7.2f}%")
print(f"  ベンチマーク（小型株）: {win_rate_small*100:7.2f}%")

print("\n【アウトパフォーマンス】")
print(f"  vs 全銘柄: {(cagr_strategy - cagr_all)*100:+7.2f}% (年率)")
print(f"  vs 小型株: {(cagr_strategy - cagr_small)*100:+7.2f}% (年率)")

print("\n【平均銘柄数】")
print(f"  {df_backtest['portfolio_size'].mean():.1f} 銘柄")

# ================================================================================
# 6. 結果の保存
# ================================================================================

print("\n[5/5] 結果を保存中...")

output_dir = PROJECT_ROOT / 'analyses' / '20260225_1500_quarterly_rebalance_backtest' / 'results'
output_dir.mkdir(exist_ok=True, parents=True)

# 詳細データ
df_backtest.to_csv(output_dir / 'backtest_results_fixed.csv', index=False, encoding='utf-8-sig')

# サマリ
summary = {
    'version': 'fixed_no_lookahead',
    'backtest_period': {
        'start': str(df_backtest['rebalance_date'].iloc[0].date()),
        'end': str(df_backtest['rebalance_date'].iloc[-1].date()),
        'years': float(years)
    },
    'performance': {
        'strategy': {
            'cumulative_return': float(final_return_strategy),
            'cagr': float(cagr_strategy),
            'volatility': float(volatility_strategy),
            'sharpe_ratio': float(sharpe_strategy),
            'max_drawdown': float(mdd_strategy),
            'win_rate': float(win_rate_strategy)
        },
        'benchmark_all': {
            'cumulative_return': float(final_return_all),
            'cagr': float(cagr_all),
            'volatility': float(volatility_all),
            'sharpe_ratio': float(sharpe_all),
            'max_drawdown': float(mdd_all),
            'win_rate': float(win_rate_all)
        },
        'benchmark_small': {
            'cumulative_return': float(final_return_small),
            'cagr': float(cagr_small),
            'volatility': float(volatility_small),
            'sharpe_ratio': float(sharpe_small),
            'max_drawdown': float(mdd_small),
            'win_rate': float(win_rate_small)
        }
    },
    'outperformance': {
        'vs_all_cagr': float(cagr_strategy - cagr_all),
        'vs_small_cagr': float(cagr_strategy - cagr_small)
    },
    'portfolio_stats': {
        'avg_size': float(df_backtest['portfolio_size'].mean()),
        'min_size': int(df_backtest['portfolio_size'].min()),
        'max_size': int(df_backtest['portfolio_size'].max())
    }
}

with open(output_dir / 'summary_fixed.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

# テキストレポート
with open(output_dir / 'report_fixed.txt', 'w', encoding='utf-8') as f:
    f.write("3ヶ月リバランス戦略のバックテスト結果（修正版・未来参照なし）\n")
    f.write("="*80 + "\n\n")

    f.write(f"バックテスト期間: {summary['backtest_period']['start']} ~ {summary['backtest_period']['end']}\n")
    f.write(f"運用期間: {summary['backtest_period']['years']:.1f}年\n")
    f.write(f"リバランス回数: {len(df_backtest)}\n\n")

    f.write("="*80 + "\n")
    f.write("パフォーマンス比較\n")
    f.write("="*80 + "\n\n")

    f.write("【年率リターン（CAGR）】\n")
    f.write(f"  戦略（小型株×高成長）: {cagr_strategy*100:+7.2f}%\n")
    f.write(f"  ベンチマーク（全銘柄）: {cagr_all*100:+7.2f}%\n")
    f.write(f"  ベンチマーク（小型株）: {cagr_small*100:+7.2f}%\n\n")

    f.write("【シャープレシオ】\n")
    f.write(f"  戦略（小型株×高成長）: {sharpe_strategy:7.3f}\n")
    f.write(f"  ベンチマーク（全銘柄）: {sharpe_all:7.3f}\n")
    f.write(f"  ベンチマーク（小型株）: {sharpe_small:7.3f}\n\n")

    f.write("【最大ドローダウン】\n")
    f.write(f"  戦略（小型株×高成長）: {mdd_strategy*100:+7.2f}%\n")
    f.write(f"  ベンチマーク（全銘柄）: {mdd_all*100:+7.2f}%\n")
    f.write(f"  ベンチマーク（小型株）: {mdd_small*100:+7.2f}%\n\n")

    f.write("【アウトパフォーマンス】\n")
    f.write(f"  vs 全銘柄: {(cagr_strategy - cagr_all)*100:+7.2f}% (年率)\n")
    f.write(f"  vs 小型株: {(cagr_strategy - cagr_small)*100:+7.2f}% (年率)\n\n")

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("バックテスト完了（修正版）")
print("="*80)

print("\n【主要な発見】")
print(f"\n1. 年率リターン: {cagr_strategy*100:+.2f}%")
print(f"   - 全銘柄を {(cagr_strategy - cagr_all)*100:+.2f}% アウトパフォーム")
print(f"   - 小型株を {(cagr_strategy - cagr_small)*100:+.2f}% アウトパフォーム")

print(f"\n2. リスク調整後リターン:")
print(f"   - シャープレシオ: {sharpe_strategy:.3f}")
print(f"   - 最大ドローダウン: {mdd_strategy*100:.2f}%")

print(f"\n3. 勝率: {win_rate_strategy*100:.1f}%")

print(f"\n4. 平均銘柄数: {df_backtest['portfolio_size'].mean():.1f} 銘柄")

# 前回との比較
print("\n【前回（ルックアヘッドバイアスあり）との比較】")
print("前回の年率リターン: +25.07%")
print(f"今回の年率リターン: {cagr_strategy*100:+.2f}%")
print(f"差分: {(cagr_strategy - 0.2507)*100:+.2f}%")
