"""
シグナル生成（部分空間正則化PCA）

60日ローリングウィンドウでλ=0.9の正則化PCAを適用し、
米国t日のリターンから日本t+1日のリターンを予測
"""
import pandas as pd
import numpy as np
from pathlib import Path
import pickle

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data/processed/us_jp_leadlag"
PRIOR_PATH = Path(__file__).parent / "prior_subspace.pkl"
OUTPUT_DIR = Path(__file__).parent
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("="*80)
print("シグナル生成（部分空間正則化PCA）")
print("="*80)

# パラメータ
WINDOW_SIZE = 60  # 論文準拠
LAMBDA_REG = 0.9  # 正則化パラメータ
K = 3  # 固有ベクトル数

print(f"\nパラメータ:")
print(f"  ウィンドウサイズ: {WINDOW_SIZE}営業日")
print(f"  正則化λ: {LAMBDA_REG}")
print(f"  固有ベクトル数K: {K}")

# データ読み込み
print("\n[1] データ読み込み")
df = pd.read_parquet(INPUT_DIR / "returns.parquet")
print(f"  データ: {len(df)}日")

# 事前部分空間読み込み
with open(PRIOR_PATH, 'rb') as f:
    prior = pickle.load(f)

C0 = prior['C0']
us_tickers = prior['us_tickers']
jp_tickers = prior['jp_tickers']
N_US = prior['N_US']
N_JP = prior['N_JP']

print(f"  米国: {N_US}銘柄")
print(f"  日本: {N_JP}銘柄")
print(f"  事前相関行列C0: {C0.shape}")

# Close-to-Closeリターン取得
us_cc_cols = [f'US_CC_{t}' for t in us_tickers]
jp_cc_cols = [f'JP_CC_{t}' for t in jp_tickers]
all_cc_cols = us_cc_cols + jp_cc_cols

returns_cc = df[all_cc_cols].values
print(f"  リターン行列: {returns_cc.shape}")

# シグナル生成
print(f"\n[2] ローリングウィンドウシグナル生成")
print(f"  開始: {WINDOW_SIZE}日目から")

signals = []
valid_dates = []

for t in range(WINDOW_SIZE, len(returns_cc)):
    # ウィンドウ内データ
    window = returns_cc[t - WINDOW_SIZE:t]

    # 標準化（ウィンドウ内）
    mean_w = np.mean(window, axis=0)
    std_w = np.std(window, axis=0) + 1e-8  # ゼロ除算回避
    z_window = (window - mean_w) / std_w

    # ウィンドウ内相関行列
    C_t = np.corrcoef(z_window.T)

    # 正則化
    C_reg_t = (1 - LAMBDA_REG) * C_t + LAMBDA_REG * C0

    # 固有分解（上位K個）
    eigenvalues, eigenvectors = np.linalg.eigh(C_reg_t)
    idx = eigenvalues.argsort()[::-1][:K]
    V_K_t = eigenvectors[:, idx]

    # 米国・日本ブロックに分割
    V_U_t = V_K_t[:N_US, :]
    V_J_t = V_K_t[N_US:, :]

    # 米国当日リターンを標準化
    us_return_t = returns_cc[t, :N_US]
    z_U_t = (us_return_t - mean_w[:N_US]) / std_w[:N_US]

    # ファクタースコア
    f_t = V_U_t.T @ z_U_t

    # 日本翌日シグナル（標準化スケール）
    signal_jp_t_plus_1 = V_J_t @ f_t

    signals.append(signal_jp_t_plus_1)
    valid_dates.append(df['JP_Date'].iloc[t])

    # 進捗表示（100日ごと）
    if (t - WINDOW_SIZE + 1) % 100 == 0:
        print(f"  進捗: {t - WINDOW_SIZE + 1}/{len(returns_cc) - WINDOW_SIZE}日")

# DataFrameに変換
signals_df = pd.DataFrame(signals, columns=jp_tickers)
signals_df.insert(0, 'Date', valid_dates)

print(f"\n[3] 結果")
print(f"  シグナル数: {len(signals_df)}日")
print(f"  期間: {signals_df['Date'].min().date()} ~ {signals_df['Date'].max().date()}")
print(f"  シグナル列: {len(jp_tickers)}銘柄")

# 統計情報
print(f"\n[4] シグナル統計")
signal_stats = signals_df[jp_tickers].describe()
print(signal_stats)

# 保存
output_path = OUTPUT_DIR / "signals.parquet"
signals_df.to_parquet(output_path, index=False)
print(f"\n[5] 保存完了: {output_path}")

print("\n完了")
