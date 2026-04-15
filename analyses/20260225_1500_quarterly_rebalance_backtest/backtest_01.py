"""
3ヶ月リバランス戦略のバックテスト

戦略: 小型株（時価総額Q1）× 高成長率（カスタム成長率Q4）
リバランス: 3ヶ月ごと（1月、4月、7月、10月）
ウェイト: 等ウェイト
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
import json
from datetime import datetime
warnings.filterwarnings('ignore')

# プロジェクトルート
PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("3ヶ月リバランス戦略のバックテスト")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/6] データ読み込み中...")

# 既存の成長率データを読み込む
df = pd.read_csv(
    PROJECT_ROOT / 'analyses/custom_growth_rate_by_marketcap/growth_rate_by_marketcap.csv',
    parse_dates=['disclosed_date']
)

print(f"元データ: {len(df):,} レコード")
print(f"期間: {df['disclosed_date'].min()} ~ {df['disclosed_date'].max()}")

# 必要な列を確認
required_cols = ['code', 'disclosed_date', 'custom_growth_rate', 'market_cap', 'return_3M']
print(f"\n必要な列: {required_cols}")
print(f"利用可能な列: {df.columns.tolist()}")

# return_3Mがない場合は価格データから計算する必要があるが、今回は既存データを使用
if 'return_3M' not in df.columns:
    print("\n警告: return_3M列が存在しません。価格データから計算します...")
    # 価格データの読み込みと計算（省略）
    raise ValueError("return_3M列が必要です")

# 欠損値除外
df = df.dropna(subset=['custom_growth_rate', 'market_cap', 'return_3M'])

print(f"欠損値除外後: {len(df):,} レコード")

# ================================================================================
# 2. リバランス日の設定
# ================================================================================

print("\n[2/6] リバランス日を設定中...")

# 3ヶ月ごとのリバランス日（1月、4月、7月、10月の1日）
rebalance_dates = pd.date_range(
    start='2017-04-01',
    end='2025-07-01',
    freq='3MS'  # 3ヶ月ごとの月初
)

print(f"リバランス回数: {len(rebalance_dates)}")
print(f"リバランス日: {rebalance_dates[0]} ~ {rebalance_dates[-1]}")

# ================================================================================
# 3. バックテストの実行
# ================================================================================

print("\n[3/6] バックテストを実行中...")

portfolio_returns = []
benchmark_all_returns = []
benchmark_small_returns = []
portfolio_sizes = []
rebalance_records = []

for i, rebalance_date in enumerate(rebalance_dates):
    # その時点で利用可能な最新の決算データを使用（未来参照防止）
    available_data = df[df['disclosed_date'] < rebalance_date].copy()

    if len(available_data) == 0:
        print(f"  {rebalance_date.date()}: データなし、スキップ")
        continue

    # 各銘柄の最新の決算データのみを使用
    latest_data = available_data.sort_values('disclosed_date').groupby('code').last().reset_index()

    # 時価総額の四分位を再計算（その時点でのユニバース）
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

    # ベンチマーク1: 全銘柄等ウェイト
    benchmark_all = latest_data.copy()

    # ベンチマーク2: 小型株等ウェイト
    benchmark_small = latest_data[latest_data['marketcap_quartile'] == 'Q1'].copy()

    # ポートフォリオリターンの計算（等ウェイト）
    if len(strategy_portfolio) > 0:
        portfolio_return = strategy_portfolio['return_3M'].mean()
        portfolio_size = len(strategy_portfolio)
    else:
        portfolio_return = 0.0
        portfolio_size = 0

    benchmark_all_return = benchmark_all['return_3M'].mean() if len(benchmark_all) > 0 else 0.0
    benchmark_small_return = benchmark_small['return_3M'].mean() if len(benchmark_small) > 0 else 0.0

    portfolio_returns.append(portfolio_return)
    benchmark_all_returns.append(benchmark_all_return)
    benchmark_small_returns.append(benchmark_small_return)
    portfolio_sizes.append(portfolio_size)

    rebalance_records.append({
        'rebalance_date': rebalance_date,
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

print("\n[4/6] パフォーマンス指標を計算中...")

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
years = len(df_backtest) * 3 / 12  # 3ヶ月ごとのリバランス
cagr_strategy = (df_backtest['cumulative_return_strategy'].iloc[-1] ** (1 / years)) - 1
cagr_all = (df_backtest['cumulative_return_all'].iloc[-1] ** (1 / years)) - 1
cagr_small = (df_backtest['cumulative_return_small'].iloc[-1] ** (1 / years)) - 1

# ボラティリティ（年率）
volatility_strategy = df_backtest['portfolio_return'].std() * np.sqrt(4)  # 四半期→年率
volatility_all = df_backtest['benchmark_all_return'].std() * np.sqrt(4)
volatility_small = df_backtest['benchmark_small_return'].std() * np.sqrt(4)

# シャープレシオ（リスクフリーレート=0と仮定）
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
print("パフォーマンスサマリ")
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

print("\n[5/6] 結果を保存中...")

output_dir = PROJECT_ROOT / 'analyses' / '20260225_1500_quarterly_rebalance_backtest' / 'results'
output_dir.mkdir(exist_ok=True, parents=True)

# 詳細データ
df_backtest.to_csv(output_dir / 'backtest_results.csv', index=False, encoding='utf-8-sig')

# サマリ
summary = {
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

with open(output_dir / 'summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

# テキストレポート
with open(output_dir / 'report.txt', 'w', encoding='utf-8') as f:
    f.write("3ヶ月リバランス戦略のバックテスト結果\n")
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
print("バックテスト完了！")
print("="*80)

# ================================================================================
# 主要な発見のハイライト
# ================================================================================

print("\n【主要な発見】")
print(f"\n1. 年率リターン: {cagr_strategy*100:+.2f}%")
print(f"   - 全銘柄を {(cagr_strategy - cagr_all)*100:+.2f}% アウトパフォーム")
print(f"   - 小型株を {(cagr_strategy - cagr_small)*100:+.2f}% アウトパフォーム")

print(f"\n2. リスク調整後リターン:")
print(f"   - シャープレシオ: {sharpe_strategy:.3f}")
print(f"   - 最大ドローダウン: {mdd_strategy*100:.2f}%")

print(f"\n3. 勝率: {win_rate_strategy*100:.1f}%")

print(f"\n4. 平均銘柄数: {df_backtest['portfolio_size'].mean():.1f} 銘柄")

if cagr_strategy > cagr_all and cagr_strategy > cagr_small:
    print("\n✅ 戦略は両方のベンチマークを上回りました！")
else:
    print("\n⚠️ 戦略はベンチマークを下回りました")

if sharpe_strategy > 0.5:
    print(f"✅ シャープレシオ {sharpe_strategy:.3f} は良好です")
else:
    print(f"⚠️ シャープレシオ {sharpe_strategy:.3f} は低いです")
