"""
FF5ファクターのレジーム変化を可視化

ローリング分析結果から、ファクター有効性の時系列変化を分析
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# 日本語フォント設定（Windows環境）
plt.rcParams['font.sans-serif'] = ['MS Gothic', 'Yu Gothic', 'Meiryo']
plt.rcParams['axes.unicode_minus'] = False

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
RESULTS_DIR = Path(__file__).parent / "results"

print("="*80)
print("FF5ファクター レジーム変化可視化")
print("="*80)

# データ読み込み
print("\n[1] データ読み込み")
df = pd.read_csv(RESULTS_DIR / "ff5_rolling_factors.csv")
print(f"  ウィンドウ数: {len(df)}")
print(f"  期間: {df['window_start'].min()} ~ {df['window_end'].max()}")

# ウィンドウ終了月を日付型に変換（X軸用）
df['window_end_date'] = pd.to_datetime(df['window_end'].str.replace('-', '') + '01', format='%Y%m%d')

# 時系列グラフ作成
print("\n[2] 時系列グラフ作成")
fig, axes = plt.subplots(3, 2, figsize=(16, 12))
fig.suptitle('FF5+モメンタムファクター ローリング分析（12ヶ月ウィンドウ）', fontsize=16)

factors = ['MKT', 'SMB', 'HML', 'RMW', 'CMA', 'WML']

for i, factor in enumerate(factors):
    ax = axes[i // 2, i % 2]

    # データプロット
    ax.plot(df['window_end_date'], df[factor], marker='o', markersize=3, linewidth=1.5, label=factor)

    # ゼロライン
    ax.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5)

    # 移動平均（3ヶ月）
    df[f'{factor}_MA3'] = df[factor].rolling(window=3, center=True).mean()
    ax.plot(df['window_end_date'], df[f'{factor}_MA3'], linewidth=2, alpha=0.7, label=f'{factor} (MA3)')

    ax.set_title(f'{factor} ファクターリターン（年率）', fontsize=12)
    ax.set_xlabel('ウィンドウ終了月', fontsize=10)
    ax.set_ylabel('年率リターン', fontsize=10)
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)

    # Y軸フォーマット（パーセンテージ）
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))

plt.tight_layout()
output_path = RESULTS_DIR / "ff5_rolling_timeseries.png"
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"  保存完了: {output_path}")
plt.close()

# ヒートマップ作成
print("\n[3] ヒートマップ作成")
fig, ax = plt.subplots(figsize=(14, 6))

# データを転置（ファクター × 時期）
heatmap_data = df[['window_end'] + factors].set_index('window_end')[factors].T

# ヒートマップ
sns.heatmap(heatmap_data, cmap='RdYlGn', center=0, annot=False,
            fmt='.1%', cbar_kws={'label': '年率リターン'},
            xticklabels=5, yticklabels=True, ax=ax)

ax.set_title('FF5+モメンタムファクター ヒートマップ（12ヶ月ローリング）', fontsize=14)
ax.set_xlabel('ウィンドウ終了月', fontsize=11)
ax.set_ylabel('ファクター', fontsize=11)

plt.tight_layout()
output_path = RESULTS_DIR / "ff5_rolling_heatmap.png"
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"  保存完了: {output_path}")
plt.close()

# レジーム転換点検出
print("\n[4] レジーム転換点検出")
print("="*80)

regime_changes = []

for factor in factors:
    # 移動平均がゼロを跨ぐ時点を検出
    ma3 = df[f'{factor}_MA3']

    # 符号が変わる時点
    sign_changes = []
    for i in range(1, len(ma3)):
        if pd.notna(ma3.iloc[i-1]) and pd.notna(ma3.iloc[i]):
            if ma3.iloc[i-1] * ma3.iloc[i] < 0:  # 符号が異なる = ゼロを跨いだ
                sign_changes.append({
                    'factor': factor,
                    'date': df['window_end'].iloc[i],
                    'from': 'Positive' if ma3.iloc[i-1] > 0 else 'Negative',
                    'to': 'Positive' if ma3.iloc[i] > 0 else 'Negative'
                })

    regime_changes.extend(sign_changes)

    if len(sign_changes) > 0:
        print(f"\n{factor}: {len(sign_changes)}回のレジーム転換")
        for sc in sign_changes:
            print(f"  {sc['date']}: {sc['from']} -> {sc['to']}")
    else:
        # 常にプラスまたは常にマイナス
        avg = df[factor].mean()
        if avg > 0:
            print(f"\n{factor}: レジーム転換なし（常にプラス、平均{avg:.2%}）")
        else:
            print(f"\n{factor}: レジーム転換なし（常にマイナス、平均{avg:.2%}）")

# 統計サマリー
print("\n[5] 統計サマリー")
print("="*80)

summary = []
for factor in factors:
    data = df[factor].dropna()
    if len(data) > 0:
        mean_return = data.mean()
        std_return = data.std()
        sharpe = mean_return / std_return if std_return > 0 else 0
        min_return = data.min()
        max_return = data.max()
        positive_pct = (data > 0).sum() / len(data) * 100

        summary.append({
            'Factor': factor,
            'Mean': mean_return,
            'Std': std_return,
            'Sharpe': sharpe,
            'Min': min_return,
            'Max': max_return,
            'Positive%': positive_pct
        })

df_summary = pd.DataFrame(summary)
print(df_summary.to_string(index=False))

# CSV保存
summary_path = RESULTS_DIR / "ff5_regime_summary.csv"
df_summary.to_csv(summary_path, index=False)
print(f"\n保存完了: {summary_path}")

# テキストレポート
print("\n[6] テキストレポート作成")
report_path = RESULTS_DIR / "ff5_regime_summary.txt"

with open(report_path, 'w', encoding='utf-8') as f:
    f.write("="*80 + "\n")
    f.write("FF5+モメンタムファクター ローリング分析サマリー（12ヶ月ウィンドウ）\n")
    f.write("="*80 + "\n\n")

    f.write(f"分析期間: {df['window_start'].min()} ~ {df['window_end'].max()}\n")
    f.write(f"ウィンドウ数: {len(df)}\n")
    f.write(f"ウィンドウサイズ: 12ヶ月\n\n")

    f.write("="*80 + "\n")
    f.write("統計サマリー\n")
    f.write("="*80 + "\n\n")
    f.write(df_summary.to_string(index=False))
    f.write("\n\n")

    f.write("="*80 + "\n")
    f.write("レジーム転換点\n")
    f.write("="*80 + "\n\n")

    for factor in factors:
        changes = [rc for rc in regime_changes if rc['factor'] == factor]
        if len(changes) > 0:
            f.write(f"\n{factor}: {len(changes)}回のレジーム転換\n")
            for sc in changes:
                f.write(f"  {sc['date']}: {sc['from']} -> {sc['to']}\n")
        else:
            avg = df[factor].mean()
            if avg > 0:
                f.write(f"\n{factor}: レジーム転換なし（常にプラス、平均{avg:.2%}）\n")
            else:
                f.write(f"\n{factor}: レジーム転換なし（常にマイナス、平均{avg:.2%}）\n")

print(f"  保存完了: {report_path}")

print("\n完了")
