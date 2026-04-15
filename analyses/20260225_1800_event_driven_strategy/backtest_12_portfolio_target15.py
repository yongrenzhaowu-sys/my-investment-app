"""
ポートフォリオ最適化: ベース戦略 + Target15_LB3（レバレッジなし）

目的: レバレッジなしのボラティリティターゲティングでMDDをさらに削減

戦略:
- ベース戦略（低PBR×高ROE、年次リバランス）
- Target15_LB3（小型×高成長、月次リバランス、レバレッジなし）
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(r'C:\Users\yongr\claude project\workspace')

print("="*80)
print("ポートフォリオ最適化: ベース戦略 + Target15_LB3（レバレッジなし）")
print("="*80)

# ================================================================================
# 1. データ読み込み
# ================================================================================

print("\n[1/4] データ読み込み中...")

# ベース戦略
df_daily = pd.read_csv(PROJECT_ROOT / 'analyses/base_strategy_daily/daily_values.csv')
df_daily['date'] = pd.to_datetime(df_daily['date'])
df_daily['year_month'] = df_daily['date'].dt.to_period('M').dt.to_timestamp()
monthly_last = df_daily.groupby('year_month')['cumulative_value'].last()
monthly_returns = monthly_last.pct_change().dropna()
df_base = pd.DataFrame({'year_month': monthly_returns.index, 'return': monthly_returns.values})

# Target15_LB3（レバレッジなし）
df_target15 = pd.read_csv(
    PROJECT_ROOT / 'analyses/20260225_1800_event_driven_strategy/results_volatility_targeting/monthly_returns_target15_lb3.csv',
    parse_dates=['year_month']
)
# 月初に正規化
df_target15['year_month'] = df_target15['year_month'].dt.to_period('M').dt.to_timestamp()

print(f"ベース戦略: {len(df_base)}ヶ月（{df_base['year_month'].iloc[0].date()} ~ {df_base['year_month'].iloc[-1].date()}）")
print(f"Target15_LB3: {len(df_target15)}ヶ月（{df_target15['year_month'].iloc[0].date()} ~ {df_target15['year_month'].iloc[-1].date()}）")

# ================================================================================
# 2. 全期間の月次リターンを作成
# ================================================================================

print("\n[2/4] 全期間の月次リターンを作成中...")

# 全期間を特定
all_months = sorted(set(df_base['year_month'].tolist() + df_target15['year_month'].tolist()))
print(f"全期間: {all_months[0].date()} ~ {all_months[-1].date()}（{len(all_months)}ヶ月）")

# 各月のリターンを準備
full_period_data = []

for month in all_months:
    # ベース戦略のリターン
    base_return = df_base[df_base['year_month'] == month]['return'].values
    if len(base_return) > 0:
        base_ret = base_return[0]
        has_base = True
    else:
        base_ret = 0.0
        has_base = False

    # Target15のリターン
    target15_return = df_target15[df_target15['year_month'] == month]['return'].values
    if len(target15_return) > 0:
        target15_ret = target15_return[0]
        has_target15 = True
    else:
        target15_ret = 0.0
        has_target15 = False

    full_period_data.append({
        'year_month': month,
        'return_base': base_ret,
        'return_target15': target15_ret,
        'has_base': has_base,
        'has_target15': has_target15,
    })

df_full = pd.DataFrame(full_period_data)

# データ状況の確認
both = df_full['has_base'] & df_full['has_target15']
base_only = df_full['has_base'] & ~df_full['has_target15']
target15_only = ~df_full['has_base'] & df_full['has_target15']

print(f"\n期間別データ状況:")
print(f"  両戦略あり: {both.sum()}ヶ月")
print(f"  ベースのみ: {base_only.sum()}ヶ月")
print(f"  Target15のみ: {target15_only.sum()}ヶ月")

# ================================================================================
# 3. 単体戦略のパフォーマンス（全期間）
# ================================================================================

print("\n[3/4] 単体戦略のパフォーマンスを計算中（全期間）...")

# ベース戦略
base_returns_full = df_full['return_base'].values
base_cum = (1 + base_returns_full).cumprod()
base_peak = pd.Series(base_cum).expanding().max()
base_dd = (base_cum - base_peak) / base_peak
base_mdd_full = base_dd.min()

base_total_return = base_cum[-1] - 1
base_years = len(base_returns_full) / 12
base_cagr_full = (1 + base_total_return) ** (1 / base_years) - 1
base_vol_full = pd.Series(base_returns_full).std() * np.sqrt(12)
base_sharpe_full = base_cagr_full / base_vol_full if base_vol_full > 0 else 0

print(f"\nベース戦略（全期間）:")
print(f"  年率リターン: {base_cagr_full*100:+.2f}%")
print(f"  最大DD: {base_mdd_full*100:.2f}%")
print(f"  シャープレシオ: {base_sharpe_full:.3f}")

# Target15_LB3
target15_returns_full = df_full['return_target15'].values
target15_cum = (1 + target15_returns_full).cumprod()
target15_peak = pd.Series(target15_cum).expanding().max()
target15_dd = (target15_cum - target15_peak) / target15_peak
target15_mdd_full = target15_dd.min()

target15_total_return = target15_cum[-1] - 1
target15_years = len(target15_returns_full) / 12
target15_cagr_full = (1 + target15_total_return) ** (1 / target15_years) - 1
target15_vol_full = pd.Series(target15_returns_full).std() * np.sqrt(12)
target15_sharpe_full = target15_cagr_full / target15_vol_full if target15_vol_full > 0 else 0

print(f"\nTarget15_LB3（全期間）:")
print(f"  年率リターン: {target15_cagr_full*100:+.2f}%")
print(f"  最大DD: {target15_mdd_full*100:.2f}%")
print(f"  シャープレシオ: {target15_sharpe_full:.3f}")

# ================================================================================
# 4. ポートフォリオ最適化（全期間）
# ================================================================================

print("\n[4/4] ポートフォリオ最適化を実行中（全期間）...")

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

for weight_base, weight_target15 in allocations:
    # ポートフォリオリターン（欠損期間は動的配分）
    portfolio_returns = []

    for i, row in df_full.iterrows():
        if row['has_base'] and row['has_target15']:
            # 両戦略あり: 配分通り
            ret = row['return_base'] * weight_base + row['return_target15'] * weight_target15
        elif row['has_base']:
            # ベースのみ: ベース100%
            ret = row['return_base']
        elif row['has_target15']:
            # Target15のみ: Target15 100%
            ret = row['return_target15']
        else:
            # データなし: 0%
            ret = 0.0

        portfolio_returns.append(ret)

    portfolio_returns = np.array(portfolio_returns)

    # 累積リターン
    cumulative = (1 + portfolio_returns).cumprod()
    total_return = cumulative[-1] - 1

    # 年率リターン
    years = len(portfolio_returns) / 12
    cagr = (1 + total_return) ** (1 / years) - 1

    # MDD
    peak = pd.Series(cumulative).expanding().max()
    drawdown = (cumulative - peak) / peak
    mdd = drawdown.min()

    # ボラティリティ
    volatility = pd.Series(portfolio_returns).std() * np.sqrt(12)

    # シャープレシオ
    sharpe = cagr / volatility if volatility > 0 else 0

    # MDD判定
    mdd_status = "[OK]" if mdd >= -0.30 else "[NG]"

    results.append({
        'allocation': f"Base{int(weight_base*100)}_T15_{int(weight_target15*100)}",
        'weight_base': weight_base,
        'weight_target15': weight_target15,
        'cagr': cagr,
        'mdd': mdd,
        'volatility': volatility,
        'sharpe': sharpe,
        'mdd_status': mdd_status,
    })

    print(f"  {results[-1]['allocation']}: 年率{cagr*100:+.2f}%, MDD {mdd*100:.2f}%, Sharpe {sharpe:.3f} [{mdd_status}]")

df_results = pd.DataFrame(results)

# ================================================================================
# 5. 結果のサマリ
# ================================================================================

print("\n" + "="*80)
print("ポートフォリオ最適化結果（Target15使用、全期間評価）")
print("="*80)

# MDD -30%以下の設定
optimal_candidates = df_results[df_results['mdd'] >= -0.30]

if len(optimal_candidates) > 0:
    best = optimal_candidates.loc[optimal_candidates['cagr'].idxmax()]

    print(f"\n[推奨ポートフォリオ] {best['allocation']}")
    print(f"  配分: ベース{best['weight_base']*100:.0f}% + Target15 {best['weight_target15']*100:.0f}%")
    print(f"  年率リターン: {best['cagr']*100:+.2f}%")
    print(f"  最大DD: {best['mdd']*100:.2f}%")
    print(f"  ボラティリティ: {best['volatility']*100:.2f}%")
    print(f"  シャープレシオ: {best['sharpe']:.3f}")
    print(f"\n  MDD -30%以下を達成")
else:
    best = df_results.loc[df_results['mdd'].idxmax()]

    print(f"\n[重要] MDD -30%以下を達成できる配分が見つかりませんでした")
    print(f"\nMDDが最も低い設定: {best['allocation']}")
    print(f"  配分: ベース{best['weight_base']*100:.0f}% + Target15 {best['weight_target15']*100:.0f}%")
    print(f"  年率リターン: {best['cagr']*100:+.2f}%")
    print(f"  最大DD: {best['mdd']*100:.2f}%")
    print(f"  ボラティリティ: {best['volatility']*100:.2f}%")
    print(f"  シャープレシオ: {best['sharpe']:.3f}")
    print(f"\n  目標MDD -30%との差: {(best['mdd'] + 0.30)*100:.2f}%ポイント")

# ================================================================================
# 6. 結果を保存
# ================================================================================

output_dir = PROJECT_ROOT / 'analyses/20260225_1800_event_driven_strategy/results_portfolio_target15'
output_dir.mkdir(exist_ok=True, parents=True)

df_results.to_csv(output_dir / 'performance_summary.csv', index=False)

with open(output_dir / 'optimal_portfolio.txt', 'w', encoding='utf-8') as f:
    f.write(f"ポートフォリオ最適化結果（Target15使用、全期間: {all_months[0].date()} ~ {all_months[-1].date()}）\n")
    f.write("="*80 + "\n\n")
    f.write(f"評価期間: {len(all_months)}ヶ月\n")
    f.write(f"  両戦略あり: {both.sum()}ヶ月\n")
    f.write(f"  ベースのみ: {base_only.sum()}ヶ月\n")
    f.write(f"  Target15のみ: {target15_only.sum()}ヶ月\n\n")
    f.write(f"ベース戦略（単体、全期間）:\n")
    f.write(f"  年率リターン: {base_cagr_full*100:+.2f}%\n")
    f.write(f"  最大DD: {base_mdd_full*100:.2f}%\n")
    f.write(f"  シャープレシオ: {base_sharpe_full:.3f}\n\n")
    f.write(f"Target15_LB3（単体、全期間）:\n")
    f.write(f"  年率リターン: {target15_cagr_full*100:+.2f}%\n")
    f.write(f"  最大DD: {target15_mdd_full*100:.2f}%\n")
    f.write(f"  シャープレシオ: {target15_sharpe_full:.3f}\n\n")
    f.write("="*80 + "\n\n")

    if len(optimal_candidates) > 0:
        f.write(f"MDD -30%以下を達成\n\n")
        f.write(f"最適ポートフォリオ: {best['allocation']}\n\n")
        f.write(f"配分:\n")
        f.write(f"  ベース戦略: {best['weight_base']*100:.0f}%\n")
        f.write(f"  Target15_LB3: {best['weight_target15']*100:.0f}%\n\n")
        f.write(f"パフォーマンス:\n")
        f.write(f"  年率リターン: {best['cagr']*100:+.2f}%\n")
        f.write(f"  最大DD: {best['mdd']*100:.2f}%\n")
        f.write(f"  ボラティリティ: {best['volatility']*100:.2f}%\n")
        f.write(f"  シャープレシオ: {best['sharpe']:.3f}\n")
    else:
        f.write(f"MDD -30%以下を達成できませんでした\n\n")
        f.write(f"MDDが最も低い設定: {best['allocation']}\n\n")
        f.write(f"配分:\n")
        f.write(f"  ベース戦略: {best['weight_base']*100:.0f}%\n")
        f.write(f"  Target15_LB3: {best['weight_target15']*100:.0f}%\n\n")
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
    print(f"  {row['allocation']:18s}: {row['cagr']*100:+6.2f}%  {row['mdd']*100:7.2f}%  {row['sharpe']:.3f}  [{row['mdd_status']}]")

print("\n" + "="*80)
print("単体戦略との比較（全期間）:")
print("="*80)
print(f"  ベース戦略（単体）   : {base_cagr_full*100:+6.2f}%  {base_mdd_full*100:7.2f}%  {base_sharpe_full:.3f}")
print(f"  Target15_LB3（単体） : {target15_cagr_full*100:+6.2f}%  {target15_mdd_full*100:7.2f}%  {target15_sharpe_full:.3f}")

if len(optimal_candidates) > 0:
    print(f"  最適ポートフォリオ    : {best['cagr']*100:+6.2f}%  {best['mdd']*100:7.2f}%  {best['sharpe']:.3f}  [OK]")
else:
    print(f"  MDDが最も低い設定    : {best['cagr']*100:+6.2f}%  {best['mdd']*100:7.2f}%  {best['sharpe']:.3f}  [NG]")

print("\n完了！")
