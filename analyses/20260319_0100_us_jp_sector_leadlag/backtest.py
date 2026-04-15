"""
バックテスト実装

上位30%ロング・下位30%ショートの等ウェイト戦略
"""
import pandas as pd
import numpy as np
from pathlib import Path

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data/processed/us_jp_leadlag"
SIGNALS_PATH = Path(__file__).parent / "signals.parquet"
OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("="*80)
print("バックテスト（上位30%ロング・下位30%ショート）")
print("="*80)

# パラメータ
Q = 0.3  # 上位・下位の分位点（30%）

print(f"\nパラメータ:")
print(f"  上位: {Q*100:.0f}%をロング")
print(f"  下位: {Q*100:.0f}%をショート")
print(f"  ウェイト: 等ウェイト")

# データ読み込み
print("\n[1] データ読み込み")
df_returns = pd.read_parquet(INPUT_DIR / "returns.parquet")
df_signals = pd.read_parquet(SIGNALS_PATH)

print(f"  リターンデータ: {len(df_returns)}日")
print(f"  シグナルデータ: {len(df_signals)}日")

# 日付でマージ
df = df_returns.merge(df_signals, left_on='JP_Date', right_on='Date', how='inner', suffixes=('', '_signal'))

print(f"  マージ後: {len(df)}日")

# 日本のOpen-to-Closeリターン列
jp_oc_cols = [col for col in df.columns if col.startswith('JP_OC_')]
jp_tickers = [col.replace('JP_OC_', '') for col in jp_oc_cols]

print(f"  日本銘柄: {len(jp_tickers)}銘柄")

# バックテスト
print("\n[2] バックテスト実行")
portfolio_returns = []

for idx, row in df.iterrows():
    # シグナル
    signals = row[jp_tickers].values

    # 上位30%をロング
    n_long = int(len(signals) * Q)
    long_indices = np.argsort(signals)[-n_long:]

    # 下位30%をショート
    n_short = int(len(signals) * Q)
    short_indices = np.argsort(signals)[:n_short]

    # ウェイト
    weights = np.zeros(len(signals))
    weights[long_indices] = 1 / n_long
    weights[short_indices] = -1 / n_short

    # 翌日のOpen-to-Closeリターン
    returns_oc = row[jp_oc_cols].values

    # 戦略リターン
    R_t = np.sum(weights * returns_oc)
    portfolio_returns.append(R_t)

portfolio_returns = np.array(portfolio_returns)

print(f"  計算完了: {len(portfolio_returns)}日")

# 評価指標
print("\n[3] 評価指標")

# 年率リターン（AR）
AR = np.mean(portfolio_returns) * 252 * 100
print(f"  年率リターン (AR): {AR:.2f}%")

# 年率リスク（RISK）
RISK = np.std(portfolio_returns) * np.sqrt(252) * 100
print(f"  年率リスク (RISK): {AR:.2f}%")

# リスク・リターン（R/R = シャープレシオ相当）
RR = AR / RISK if RISK > 0 else 0
print(f"  R/R: {RR:.2f}")

# 最大ドローダウン（MDD）
cumulative = np.cumprod(1 + portfolio_returns)
running_max = np.maximum.accumulate(cumulative)
drawdown = (cumulative / running_max) - 1
MDD = np.min(drawdown) * 100
print(f"  最大ドローダウン (MDD): {MDD:.2f}%")

# 累積リターン
cumulative_return = (cumulative[-1] - 1) * 100
print(f"  累積リターン: {cumulative_return:.2f}%")

# 結果を保存
results_df = pd.DataFrame({
    'Date': df['JP_Date'].values,
    'Return': portfolio_returns,
    'Cumulative': cumulative
})

output_path = OUTPUT_DIR / "backtest_pca_sub.csv"
results_df.to_csv(output_path, index=False)
print(f"\n[4] 保存完了: {output_path}")

# サマリー保存
summary = {
    'Strategy': 'PCA_SUB',
    'AR': AR,
    'RISK': RISK,
    'R/R': RR,
    'MDD': MDD,
    'Cumulative_Return': cumulative_return,
    'N_Days': len(portfolio_returns),
    'Period_Start': df['JP_Date'].min(),
    'Period_End': df['JP_Date'].max()
}

summary_df = pd.DataFrame([summary])
summary_path = OUTPUT_DIR / "summary_pca_sub.csv"
summary_df.to_csv(summary_path, index=False)
print(f"  サマリー保存: {summary_path}")

print("\n完了")
