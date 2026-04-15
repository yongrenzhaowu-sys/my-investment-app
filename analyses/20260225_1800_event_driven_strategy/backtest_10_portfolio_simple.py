"""
ポートフォリオ最適化（簡素版）: ベース戦略 + レバレッジ戦略

目的: MDDを-30%以下に抑えつつ、高リターンを実現

戦略:
- ベース戦略（低PBR×高ROE、年次リバランス）
  - 正確なデータ: 日次評価版から算出
- レバレッジ戦略（小型×高成長、月次リバランス、Target25_LB3）
  - 正確なデータ: extract_leverage_returns.pyから算出

配分比率テスト:
- Base20_Lev80, Base30_Lev70, Base40_Lev60, Base50_Lev50, Base60_Lev40, Base70_Lev30, Base80_Lev20
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("ポートフォリオ最適化（簡素版）: ベース戦略 + レバレッジ戦略")
print("="*80)

# ================================================================================
# 1. ベース戦略の月次リターンを準備
# ================================================================================

print("\n[1/3] ベース戦略の月次リターンを準備中...")

# 日次評価版から日次データを読み込み
df_daily = pd.read_csv(PROJECT_ROOT / 'analyses/base_strategy_daily/daily_values.csv')
df_daily['date'] = pd.to_datetime(df_daily['date'])
df_daily = df_daily.sort_values('date')

# 月次リターンを計算
df_daily['year_month'] = df_daily['date'].dt.to_period('M').dt.to_timestamp()

# 各月の最終日の累積値を取得
monthly_last = df_daily.groupby('year_month')['cumulative_value'].last()

# 月次リターンを計算
monthly_returns = monthly_last.pct_change().dropna()

df_base = pd.DataFrame({
    'year_month': monthly_returns.index,
    'return': monthly_returns.values
})

print(f"ベース戦略の月次リターン: {len(df_base)}ヶ月")
print(f"期間: {df_base['year_month'].iloc[0].date()} ~ {df_base['year_month'].iloc[-1].date()}")

# パフォーマンス確認
base_cumulative = (1 + df_base['return']).cumprod().iloc[-1] - 1
base_years = len(df_base) / 12
base_cagr = (1 + base_cumulative) ** (1 / base_years) - 1

base_cum_series = (1 + df_base['return']).cumprod()
base_peak = base_cum_series.expanding().max()
base_dd = (base_cum_series - base_peak) / base_peak
base_mdd = base_dd.min()

base_vol = df_base['return'].std() * np.sqrt(12)
base_sharpe = base_cagr / base_vol if base_vol > 0 else 0

print(f"ベース戦略の年率リターン: {base_cagr*100:+.2f}%")
print(f"ベース戦略のMDD: {base_mdd*100:.2f}%")
print(f"ベース戦略のSharpe: {base_sharpe:.3f}")

# ================================================================================
# 2. レバレッジ戦略の月次リターンを読み込み
# ================================================================================

print("\n[2/3] レバレッジ戦略（Target25_LB3）の月次リターンを読み込み中...")

df_leverage = pd.read_csv(
    PROJECT_ROOT / 'analyses/20260225_1800_event_driven_strategy/results_leverage/monthly_returns_target25_lb3.csv',
    parse_dates=['year_month']
)

print(f"レバレッジ戦略の月次リターン: {len(df_leverage)}ヶ月")
print(f"期間: {df_leverage['year_month'].iloc[0].date()} ~ {df_leverage['year_month'].iloc[-1].date()}")

# パフォーマンス確認
leverage_cumulative = (1 + df_leverage['return']).cumprod().iloc[-1] - 1
leverage_years = len(df_leverage) / 12
leverage_cagr = (1 + leverage_cumulative) ** (1 / leverage_years) - 1

leverage_cum_series = (1 + df_leverage['return']).cumprod()
leverage_peak = leverage_cum_series.expanding().max()
leverage_dd = (leverage_cum_series - leverage_peak) / leverage_peak
leverage_mdd = leverage_dd.min()

leverage_vol = df_leverage['return'].std() * np.sqrt(12)
leverage_sharpe = leverage_cagr / leverage_vol if leverage_vol > 0 else 0

print(f"レバレッジ戦略の年率リターン: {leverage_cagr*100:+.2f}%")
print(f"レバレッジ戦略のMDD: {leverage_mdd*100:.2f}%")
print(f"レバレッジ戦略のSharpe: {leverage_sharpe:.3f}")

# ================================================================================
# 3. 期間を合わせる
# ================================================================================

print("\n[3/3] 期間を合わせてポートフォリオ最適化を実行中...")

# 共通期間を特定
merged = pd.merge(
    df_base[['year_month', 'return']],
    df_leverage[['year_month', 'return']],
    on='year_month',
    how='inner',
    suffixes=('_base', '_leverage')
)

print(f"共通期間: {len(merged)}ヶ月")
print(f"期間: {merged['year_month'].iloc[0].date()} ~ {merged['year_month'].iloc[-1].date()}")

# ================================================================================
# 4. ポートフォリオ最適化（複数の配分比率でテスト）
# ================================================================================

allocations = [
    (0.20, 0.80),
    (0.30, 0.70),
    (0.40, 0.60),
    (0.50, 0.50),
    (0.60, 0.40),
    (0.70, 0.30),
    (0.80, 0.20),
]

results = []

for weight_base, weight_leverage in allocations:
    # ポートフォリオリターン
    portfolio_returns = (
        merged['return_base'] * weight_base +
        merged['return_leverage'] * weight_leverage
    )

    # 累積リターン
    cumulative = (1 + portfolio_returns).cumprod()
    total_return = cumulative.iloc[-1] - 1

    # 年率リターン
    years = len(portfolio_returns) / 12
    cagr = (1 + total_return) ** (1 / years) - 1

    # MDD
    peak = cumulative.expanding().max()
    drawdown = (cumulative - peak) / peak
    mdd = drawdown.min()

    # ボラティリティ
    volatility = portfolio_returns.std() * np.sqrt(12)

    # シャープレシオ
    sharpe = cagr / volatility if volatility > 0 else 0

    # MDD判定
    mdd_status = "[OK]" if mdd >= -0.30 else "[NG]"

    results.append({
        'allocation': f"Base{int(weight_base*100)}_Lev{int(weight_leverage*100)}",
        'weight_base': weight_base,
        'weight_leverage': weight_leverage,
        'cagr': cagr,
        'mdd': mdd,
        'volatility': volatility,
        'sharpe': sharpe,
        'mdd_status': mdd_status,
    })

    print(f"  {results[-1]['allocation']}: 年率{cagr*100:+.2f}%, MDD {mdd*100:.2f}%, Sharpe {sharpe:.3f} [{mdd_status}]")

# 結果をDataFrameに変換
df_results = pd.DataFrame(results)

# ================================================================================
# 5. 最適ポートフォリオの特定
# ================================================================================

print("\n" + "="*80)
print("ポートフォリオ最適化結果")
print("="*80)

# MDD -30%以下の設定
optimal_candidates = df_results[df_results['mdd'] >= -0.30]

if len(optimal_candidates) > 0:
    # リターンが最も高い設定
    best = optimal_candidates.loc[optimal_candidates['cagr'].idxmax()]

    print(f"\n【推奨ポートフォリオ】 {best['allocation']}")
    print(f"  配分: ベース{best['weight_base']*100:.0f}% + レバレッジ{best['weight_leverage']*100:.0f}%")
    print(f"  年率リターン: {best['cagr']*100:+.2f}%")
    print(f"  最大DD: {best['mdd']*100:.2f}%")
    print(f"  ボラティリティ: {best['volatility']*100:.2f}%")
    print(f"  シャープレシオ: {best['sharpe']:.3f}")
    print(f"\n   MDD -30%以下を達成！")
else:
    print("\n【重要】MDD -30%以下を達成できる配分が見つかりませんでした")
    print("\nMDDが最も低い設定:")
    best = df_results.loc[df_results['mdd'].idxmax()]

    print(f"  {best['allocation']}")
    print(f"  配分: ベース{best['weight_base']*100:.0f}% + レバレッジ{best['weight_leverage']*100:.0f}%")
    print(f"  年率リターン: {best['cagr']*100:+.2f}%")
    print(f"  最大DD: {best['mdd']*100:.2f}%")
    print(f"  ボラティリティ: {best['volatility']*100:.2f}%")
    print(f"  シャープレシオ: {best['sharpe']:.3f}")
    print(f"\n  目標MDD -30%との差: {(best['mdd'] + 0.30)*100:.2f}%ポイント")

# ================================================================================
# 6. 結果を保存
# ================================================================================

output_dir = PROJECT_ROOT / 'analyses/20260225_1800_event_driven_strategy/results_portfolio_final'
output_dir.mkdir(exist_ok=True, parents=True)

# 全結果を保存
df_results.to_csv(output_dir / 'performance_summary.csv', index=False)

# 最適ポートフォリオを保存
with open(output_dir / 'optimal_portfolio.txt', 'w', encoding='utf-8') as f:
    f.write(f"ポートフォリオ最適化結果（正確なデータ使用）\n")
    f.write("="*80 + "\n\n")
    f.write(f"ベース戦略（単体）:\n")
    f.write(f"  年率リターン: {base_cagr*100:+.2f}%\n")
    f.write(f"  最大DD: {base_mdd*100:.2f}%\n")
    f.write(f"  シャープレシオ: {base_sharpe:.3f}\n\n")
    f.write(f"レバレッジ戦略（単体）:\n")
    f.write(f"  年率リターン: {leverage_cagr*100:+.2f}%\n")
    f.write(f"  最大DD: {leverage_mdd*100:.2f}%\n")
    f.write(f"  シャープレシオ: {leverage_sharpe:.3f}\n\n")
    f.write("="*80 + "\n\n")

    if len(optimal_candidates) > 0:
        f.write(f" MDD -30%以下を達成\n\n")
        f.write(f"最適ポートフォリオ: {best['allocation']}\n\n")
        f.write(f"配分:\n")
        f.write(f"  ベース戦略（低PBR×高ROE）: {best['weight_base']*100:.0f}%\n")
        f.write(f"  レバレッジ戦略（Target25_LB3）: {best['weight_leverage']*100:.0f}%\n\n")
        f.write(f"パフォーマンス:\n")
        f.write(f"  年率リターン: {best['cagr']*100:+.2f}%\n")
        f.write(f"  最大DD: {best['mdd']*100:.2f}%\n")
        f.write(f"  ボラティリティ: {best['volatility']*100:.2f}%\n")
        f.write(f"  シャープレシオ: {best['sharpe']:.3f}\n")
    else:
        f.write(f" MDD -30%以下を達成できませんでした\n\n")
        f.write(f"MDDが最も低い設定: {best['allocation']}\n\n")
        f.write(f"配分:\n")
        f.write(f"  ベース戦略（低PBR×高ROE）: {best['weight_base']*100:.0f}%\n")
        f.write(f"  レバレッジ戦略（Target25_LB3）: {best['weight_leverage']*100:.0f}%\n\n")
        f.write(f"パフォーマンス:\n")
        f.write(f"  年率リターン: {best['cagr']*100:+.2f}%\n")
        f.write(f"  最大DD: {best['mdd']*100:.2f}%\n")
        f.write(f"  ボラティリティ: {best['volatility']*100:.2f}%\n")
        f.write(f"  シャープレシオ: {best['sharpe']:.3f}\n\n")
        f.write(f"目標MDD -30%との差: {(best['mdd'] + 0.30)*100:.2f}%ポイント\n")

print(f"\n保存先: {output_dir}")

print("\n" + "="*80)
print("全結果（配分 / 年率 / MDD / Sharpe）:")
print("="*80)
for _, row in df_results.iterrows():
    print(f"  {row['allocation']:15s}: {row['cagr']*100:+6.2f}%  {row['mdd']*100:7.2f}%  {row['sharpe']:.3f}  [{row['mdd_status']}]")

print("\n" + "="*80)
print("単体戦略との比較:")
print("="*80)
print(f"  ベース戦略（単体）   : {base_cagr*100:+6.2f}%  {base_mdd*100:7.2f}%  {base_sharpe:.3f}")
print(f"  レバレッジ戦略（単体）: {leverage_cagr*100:+6.2f}%  {leverage_mdd*100:7.2f}%  {leverage_sharpe:.3f}")

if len(optimal_candidates) > 0:
    print(f"  最適ポートフォリオ    : {best['cagr']*100:+6.2f}%  {best['mdd']*100:7.2f}%  {best['sharpe']:.3f}  ")
else:
    print(f"  最適ポートフォリオ    : {best['cagr']*100:+6.2f}%  {best['mdd']*100:7.2f}%  {best['sharpe']:.3f}  ")

print("\n完了！")
