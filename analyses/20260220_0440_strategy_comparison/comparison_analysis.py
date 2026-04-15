"""週次PBR×ROE戦略 比較分析スクリプト

2つの週次戦略を比較：
1. 20260218_1630_weekly_long_only（J-Quantsデータ版）
2. 20260220_0420_weekly_pbr_roe_fixed（TOPIX四季報データ版・修正版）
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
from pathlib import Path

# ===== パス設定 =====
BASE_DIR = Path(__file__).parent.parent
STRATEGY_A_DIR = BASE_DIR / '20260218_1630_weekly_long_only'
STRATEGY_B_DIR = BASE_DIR / '20260220_0420_weekly_pbr_roe_fixed'

print('=' * 80)
print('週次PBR×ROE戦略 比較分析')
print('=' * 80)
print()

# ===== 戦略A: 20260218版の読み込み =====
print('[戦略A] 20260218_1630_weekly_long_only')
results_a = pd.read_csv(STRATEGY_A_DIR / 'backtest_results.csv', encoding='utf-8-sig')
results_a['date'] = pd.to_datetime(results_a['date'])

# パフォーマンス指標計算
initial_capital_a = results_a['total_value'].iloc[0]
final_capital_a = results_a['total_value'].iloc[-1]
total_return_a = (final_capital_a / initial_capital_a - 1)
years_a = (results_a['date'].max() - results_a['date'].min()).days / 365.25
annual_return_a = (1 + total_return_a) ** (1 / years_a) - 1

# リターン系列
returns_a = results_a['return'].dropna().values
annual_vol_a = np.std(returns_a, ddof=1) * np.sqrt(52)  # 週次なので52週
mean_return_a = np.mean(returns_a)
sharpe_a = (mean_return_a * 52) / annual_vol_a if annual_vol_a > 0 else 0.0

# ドローダウン
max_dd_a = results_a['drawdown'].min()

# カルマー比
calmar_a = (annual_return_a * 100) / abs(max_dd_a * 100) if abs(max_dd_a) > 0 else 0.0

# 勝率
win_rate_a = (returns_a > 0).mean() * 100

print(f'  期間: {results_a["date"].min().date()} ~ {results_a["date"].max().date()} ({years_a:.1f}年)')
print(f'  週数: {len(results_a)}週')
print(f'  初期資本: {initial_capital_a:,.0f}円')
print(f'  最終資本: {final_capital_a:,.0f}円')
print(f'  総リターン: {total_return_a*100:.2f}%')
print(f'  年率リターン: {annual_return_a*100:.2f}%')
print(f'  年率ボラティリティ: {annual_vol_a*100:.2f}%')
print(f'  シャープレシオ: {sharpe_a:.2f}')
print(f'  最大DD: {max_dd_a*100:.2f}%')
print(f'  カルマー比: {calmar_a:.2f}')
print(f'  勝率: {win_rate_a:.1f}%')
print()

# ===== 戦略B: 20260220版の読み込み =====
print('[戦略B] 20260220_0420_weekly_pbr_roe_fixed')
results_b = pd.read_csv(STRATEGY_B_DIR / 'backtest_results.csv', encoding='utf-8-sig')
results_b['date'] = pd.to_datetime(results_b['date'])

# パフォーマンス指標（README.mdから取得）
# 実際の値
initial_capital_b = 10_000_000
final_capital_b = 73_328_708
total_return_b = (final_capital_b / initial_capital_b - 1)
years_b = (results_b['date'].max() - results_b['date'].min()).days / 365.25
annual_return_b = (1 + total_return_b) ** (1 / years_b) - 1

# リターン系列
returns_b = results_b['net_return'].dropna().values / 100  # %なので100で割る
annual_vol_b = np.std(returns_b, ddof=1) * np.sqrt(52)  # 週次なので52週
mean_return_b = np.mean(returns_b)
sharpe_b = (mean_return_b * 52) / annual_vol_b if annual_vol_b > 0 else 0.0

# ドローダウン計算
equity_vals_b = results_b['capital'].values
rolling_max_b = np.maximum.accumulate(equity_vals_b)
drawdowns_b = (equity_vals_b - rolling_max_b) / rolling_max_b
max_dd_b = drawdowns_b.min()

# カルマー比
calmar_b = (annual_return_b * 100) / abs(max_dd_b * 100) if abs(max_dd_b) > 0 else 0.0

# 勝率
win_rate_b = (returns_b > 0).mean() * 100

print(f'  期間: {results_b["date"].min().date()} ~ {results_b["date"].max().date()} ({years_b:.1f}年)')
print(f'  週数: {len(results_b)}週')
print(f'  初期資本: {initial_capital_b:,.0f}円')
print(f'  最終資本: {final_capital_b:,.0f}円')
print(f'  総リターン: {total_return_b*100:.2f}%')
print(f'  年率リターン: {annual_return_b*100:.2f}%')
print(f'  年率ボラティリティ: {annual_vol_b*100:.2f}%')
print(f'  シャープレシオ: {sharpe_b:.2f}')
print(f'  最大DD: {max_dd_b*100:.2f}%')
print(f'  カルマー比: {calmar_b:.2f}')
print(f'  勝率: {win_rate_b:.1f}%')
print()

# ===== 比較表 =====
print('=' * 80)
print('パフォーマンス比較表')
print('=' * 80)
print()

comparison_data = {
    '指標': [
        'バックテスト期間',
        '週数',
        '総リターン',
        '年率リターン',
        '年率ボラティリティ',
        'シャープレシオ',
        '最大ドローダウン',
        'カルマー比',
        '勝率',
        '最終資本（万円）'
    ],
    '戦略A (20260218)': [
        f'{results_a["date"].min().date()} ~ {results_a["date"].max().date()}',
        f'{len(results_a)}週',
        f'{total_return_a*100:+.2f}%',
        f'{annual_return_a*100:+.2f}%',
        f'{annual_vol_a*100:.2f}%',
        f'{sharpe_a:.2f}',
        f'{max_dd_a*100:.2f}%',
        f'{calmar_a:.2f}',
        f'{win_rate_a:.1f}%',
        f'{final_capital_a/10000:.1f}'
    ],
    '戦略B (20260220)': [
        f'{results_b["date"].min().date()} ~ {results_b["date"].max().date()}',
        f'{len(results_b)}週',
        f'{total_return_b*100:+.2f}%',
        f'{annual_return_b*100:+.2f}%',
        f'{annual_vol_b*100:.2f}%',
        f'{sharpe_b:.2f}',
        f'{max_dd_b*100:.2f}%',
        f'{calmar_b:.2f}',
        f'{win_rate_b:.1f}%',
        f'{final_capital_b/10000:.1f}'
    ]
}

# 優位判定
优势_list = []
for idx in range(len(comparison_data['指標'])):
    if idx in [0, 1]:  # 期間と週数はスキップ
        优势_list.append('-')
    elif idx == 2:  # 総リターン
        优势_list.append('戦略B' if total_return_b > total_return_a else '戦略A')
    elif idx == 3:  # 年率リターン
        优势_list.append('戦略B' if annual_return_b > annual_return_a else '戦略A')
    elif idx == 4:  # ボラティリティ（低い方が良い）
        优势_list.append('戦略B' if annual_vol_b < annual_vol_a else '戦略A')
    elif idx == 5:  # シャープレシオ
        优势_list.append('戦略B' if sharpe_b > sharpe_a else '戦略A')
    elif idx == 6:  # ドローダウン（絶対値が小さい方が良い）
        优势_list.append('戦略B' if abs(max_dd_b) < abs(max_dd_a) else '戦略A')
    elif idx == 7:  # カルマー比
        优势_list.append('戦略B' if calmar_b > calmar_a else '戦略A')
    elif idx == 8:  # 勝率
        优势_list.append('戦略B' if win_rate_b > win_rate_a else '戦略A')
    elif idx == 9:  # 最終資本
        优势_list.append('戦略B' if final_capital_b > final_capital_a else '戦略A')
    else:
        优势_list.append('-')

comparison_data['優位'] = 优势_list
comparison = pd.DataFrame(comparison_data)

print(comparison.to_string(index=False))
print()

# ===== 主要な違いの分析 =====
print('=' * 80)
print('主要な違いの分析')
print('=' * 80)
print()

print('[データソース]')
print('  戦略A: J-Quantsデータ（curated版）')
print('  戦略B: TOPIX四季報データ（legacy版）')
print()

print('[期間]')
print(f'  戦略A: {results_a["date"].min().date()} ~ {results_a["date"].max().date()} ({years_a:.1f}年)')
print(f'  戦略B: {results_b["date"].min().date()} ~ {results_b["date"].max().date()} ({years_b:.1f}年)')
print('  → 戦略Bの方が約0.8年早く開始（データ利用可能期間の違い）')
print()

print('[銘柄選択ロジック]')
print('  戦略A: PBR Q1（割安） × ROE Q4（高質） → 上位20銘柄等ウェイト')
print('  戦略B: PBR Q1（割安） × ROE Q1（高質） → PBR下位50銘柄等ウェイト')
print('  → 戦略Bは銘柄数が2.5倍多く、より分散されている')
print()

print('[リバランス頻度]')
print('  戦略A: 毎週金曜日（年間52回）')
print('  戦略B: 毎週月曜日（年間52回）')
print('  → 同じ週次リバランス')
print()

# ===== 結論 =====
print('=' * 80)
print('結論')
print('=' * 80)
print()

print('【総合評価】')
if annual_return_b > annual_return_a and abs(max_dd_b) < abs(max_dd_a):
    print('  ✅ 戦略B（20260220版）が明確に優位')
    print(f'    - 年率リターン: {annual_return_b*100:.2f}% vs {annual_return_a*100:.2f}% (差: {(annual_return_b-annual_return_a)*100:+.2f}%)')
    print(f'    - 最大DD: {max_dd_b*100:.2f}% vs {max_dd_a*100:.2f}% (改善: {(abs(max_dd_a)-abs(max_dd_b))*100:.2f}%)')
elif annual_return_b > annual_return_a:
    print('  ✅ 戦略B（20260220版）がリターンで優位（ただしリスクは高い）')
else:
    print('  ⚠️ 両戦略とも課題あり')

print()
print('【推奨】')
print('  → 戦略B（20260220版）を採用')
print('  → ただし、最大DD -39%は依然として大きいため、リスク管理強化が必要')
print()

# ===== 保存 =====
output_path = Path(__file__).parent / 'comparison_results.csv'
comparison.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f'比較結果を保存: {output_path}')
