"""
FF5ローリング分析結果の可視化（matplotlib版）
"""
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# パス設定
RESULTS_DIR = Path(__file__).parent / "results"
df = pd.read_csv(RESULTS_DIR / "ff5_rolling_factors.csv")

print("="*80)
print("FF5ローリング分析結果の可視化")
print("="*80)
print(f"\nデータ数: {len(df)}ウィンドウ")
print(f"期間: {df['window_start'].min()} ~ {df['window_end'].max()}")

# 図の作成
fig, axes = plt.subplots(3, 2, figsize=(15, 12))
fig.suptitle('FF5 + WML Factors Rolling Analysis (2021-2026, 12-month windows)', fontsize=16)

factors = ['MKT', 'SMB', 'HML', 'RMW', 'CMA', 'WML']
colors = ['blue', 'green', 'red', 'purple', 'orange', 'brown']

for i, (factor, color) in enumerate(zip(factors, colors)):
    row = i // 2
    col = i % 2
    ax = axes[row, col]

    # ファクターリターンをプロット
    x = range(len(df))
    y = df[factor] * 100  # %表示

    ax.plot(x, y, color=color, linewidth=2, label=factor)
    ax.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    ax.set_title(f'{factor} Factor', fontsize=12, fontweight='bold')
    ax.set_xlabel('Window ID')
    ax.set_ylabel('Annual Return (%)')
    ax.grid(True, alpha=0.3)

    # 統計情報を表示
    mean_return = df[factor].mean() * 100
    std_return = df[factor].std() * 100
    sharpe = mean_return / std_return if std_return > 0 else 0

    info_text = f'Mean: {mean_return:+.2f}%\nStd: {std_return:.2f}%\nSR: {sharpe:.2f}'
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
            verticalalignment='top', fontsize=9,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()

# 保存
output_path = RESULTS_DIR / "ff5_rolling_timeseries.png"
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"\n時系列グラフを保存: {output_path}")

# ヒートマップ（簡易版）
fig2, ax2 = plt.subplots(figsize=(12, 8))

# データを行列形式に変換
factor_matrix = df[factors].T * 100  # %表示

# 手動でヒートマップを作成
im = ax2.imshow(factor_matrix, cmap='RdYlGn', aspect='auto', vmin=-20, vmax=20)

# 軸ラベル
ax2.set_yticks(range(len(factors)))
ax2.set_yticklabels(factors)
ax2.set_xlabel('Window ID')
ax2.set_title('FF5 + WML Factors Heatmap (Annual Returns %)', fontsize=14, fontweight='bold')

# カラーバー
cbar = plt.colorbar(im, ax=ax2)
cbar.set_label('Annual Return (%)', rotation=270, labelpad=20)

plt.tight_layout()

# 保存
output_path2 = RESULTS_DIR / "ff5_rolling_heatmap.png"
plt.savefig(output_path2, dpi=300, bbox_inches='tight')
print(f"ヒートマップを保存: {output_path2}")

# テキストサマリー
print("\n" + "="*80)
print("サマリー統計")
print("="*80)

summary_lines = []
for factor in factors:
    data = df[factor].dropna()
    if len(data) > 0:
        mean_return = data.mean() * 100
        std_return = data.std() * 100
        sharpe = mean_return / std_return if std_return > 0 else 0
        min_return = data.min() * 100
        max_return = data.max() * 100

        summary_lines.append(f"\n{factor}:")
        summary_lines.append(f"  平均年率リターン: {mean_return:+.2f}%")
        summary_lines.append(f"  標準偏差: {std_return:.2f}%")
        summary_lines.append(f"  シャープレシオ: {sharpe:.2f}")
        summary_lines.append(f"  最小/最大: {min_return:+.2f}% / {max_return:+.2f}%")

summary_text = '\n'.join(summary_lines)
print(summary_text)

# テキストファイルに保存
summary_path = RESULTS_DIR / "ff5_regime_summary.txt"
with open(summary_path, 'w', encoding='utf-8') as f:
    f.write("FF5 + WML Factors Rolling Analysis Summary\n")
    f.write("="*80 + "\n")
    f.write(f"Period: {df['window_start'].min()} ~ {df['window_end'].max()}\n")
    f.write(f"Windows: {len(df)}\n")
    f.write("="*80 + "\n")
    f.write(summary_text)

print(f"\nサマリーテキストを保存: {summary_path}")
print("\n完了")
