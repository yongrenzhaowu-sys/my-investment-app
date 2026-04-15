"""
事前部分空間の構築

K=3の直交ファクター:
1. グローバルファクター: 全銘柄に等重み
2. 国スプレッドファクター: 米国+、日本-
3. シクリカル・ディフェンシブファクター: 景気敏感vs防衛
"""
import pandas as pd
import numpy as np
from pathlib import Path
import pickle

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data/processed/us_jp_leadlag"
OUTPUT_DIR = Path(__file__).parent
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("="*80)
print("事前部分空間の構築（K=3）")
print("="*80)

# データ読み込み
print("\n[1] データ読み込み")
df = pd.read_parquet(INPUT_DIR / "returns.parquet")
print(f"  データ: {len(df)}日")

# 米国・日本の銘柄リスト
us_tickers = [col.replace('US_CC_', '') for col in df.columns if col.startswith('US_CC_')]
jp_tickers = [col.replace('JP_CC_', '') for col in df.columns if col.startswith('JP_CC_')]

print(f"  米国: {len(us_tickers)}銘柄 - {us_tickers}")
print(f"  日本: {len(jp_tickers)}銘柄 - {jp_tickers}")

N_US = len(us_tickers)
N_JP = len(jp_tickers)
N = N_US + N_JP

# シクリカル・ディフェンシブの分類（論文準拠）
cyclical_us = ['XLB', 'XLE', 'XLF', 'XLRE']
defensive_us = ['XLK', 'XLP', 'XLU', 'XLV']
cyclical_jp = ['1618.T', '1625.T', '1629.T', '1631.T']
defensive_jp = ['1617.T', '1621.T', '1627.T', '1630.T']

print(f"\n[2] シクリカル・ディフェンシブ分類")
print(f"  米国シクリカル: {cyclical_us}")
print(f"  米国ディフェンシブ: {defensive_us}")
print(f"  日本シクリカル: {cyclical_jp}")
print(f"  日本ディフェンシブ: {defensive_jp}")

# ファクター1: グローバル（全銘柄に等重み）
print("\n[3] ファクター1: グローバル")
v1 = np.ones(N) / np.sqrt(N)
print(f"  v1: {N}次元、ノルム={np.linalg.norm(v1):.4f}")

# ファクター2: 国スプレッド（米国+、日本-）
print("\n[4] ファクター2: 国スプレッド")
v2_raw = np.concatenate([np.ones(N_US), -np.ones(N_JP)])

# v1に直交化
v2 = v2_raw - (v2_raw @ v1) * v1
v2 = v2 / np.linalg.norm(v2)
print(f"  v2: {N}次元、ノルム={np.linalg.norm(v2):.4f}")
print(f"  v1⊥v2: {v1 @ v2:.6f}（0に近いほど直交）")

# ファクター3: シクリカル・ディフェンシブ
print("\n[5] ファクター3: シクリカル・ディフェンシブ")

# 符号ベクトル作成
all_tickers = us_tickers + jp_tickers
v3_raw = np.zeros(N)

for i, ticker in enumerate(all_tickers):
    if ticker in cyclical_us or ticker in cyclical_jp:
        v3_raw[i] = +1  # シクリカル
    elif ticker in defensive_us or ticker in defensive_jp:
        v3_raw[i] = -1  # ディフェンシブ
    else:
        v3_raw[i] = 0  # その他

# v1, v2に直交化（Gram-Schmidt）
v3 = v3_raw - (v3_raw @ v1) * v1 - (v3_raw @ v2) * v2
v3 = v3 / np.linalg.norm(v3)
print(f"  v3: {N}次元、ノルム={np.linalg.norm(v3):.4f}")
print(f"  v1⊥v3: {v1 @ v3:.6f}")
print(f"  v2⊥v3: {v2 @ v3:.6f}")

# V0行列（列ベクトル）
V0 = np.column_stack([v1, v2, v3])
print(f"\n[6] V0行列")
print(f"  形状: {V0.shape}")
print(f"  直交性確認: V0^T @ V0")
print(V0.T @ V0)

# 長期ウィンドウで固有値推定（論文: 2010-2014使用）
print("\n[7] 固有値推定（長期ウィンドウ）")
print("  注意: 利用可能データは2018-06-20以降のため、全期間を使用")

# Close-to-Close リターンを取得
us_cc_cols = [f'US_CC_{t}' for t in us_tickers]
jp_cc_cols = [f'JP_CC_{t}' for t in jp_tickers]
all_cc_cols = us_cc_cols + jp_cc_cols

returns_cc = df[all_cc_cols].values
print(f"  リターン行列: {returns_cc.shape}")

# 標準化
returns_cc_std = (returns_cc - np.mean(returns_cc, axis=0)) / np.std(returns_cc, axis=0)

# 相関行列
C_full = np.corrcoef(returns_cc_std.T)
print(f"  相関行列: {C_full.shape}")

# 事前方向に沿った固有値
D0_raw = V0.T @ C_full @ V0
D0 = np.diag(np.diag(D0_raw))  # 対角成分のみ
print(f"  D0:")
print(D0)

# ターゲット行列
print("\n[8] ターゲット行列C0の構築")
C0_raw = V0 @ D0 @ V0.T
print(f"  C0_raw: {C0_raw.shape}")

# 対角を1に正規化（相関行列化）
diag_sqrt_inv = np.diag(1.0 / np.sqrt(np.diag(C0_raw)))
C0 = diag_sqrt_inv @ C0_raw @ diag_sqrt_inv

# 対角が1になるように微調整
np.fill_diagonal(C0, 1.0)
print(f"  C0（正規化後）: {C0.shape}")
print(f"  対角要素: min={np.diag(C0).min():.4f}, max={np.diag(C0).max():.4f}")
print(f"  非対角要素範囲: [{C0[~np.eye(N, dtype=bool)].min():.4f}, {C0[~np.eye(N, dtype=bool)].max():.4f}]")

# 保存
print("\n[9] 保存")
prior_subspace = {
    'V0': V0,
    'D0': D0,
    'C0': C0,
    'us_tickers': us_tickers,
    'jp_tickers': jp_tickers,
    'N_US': N_US,
    'N_JP': N_JP,
    'N': N
}

output_path = OUTPUT_DIR / "prior_subspace.pkl"
with open(output_path, 'wb') as f:
    pickle.dump(prior_subspace, f)
print(f"  保存完了: {output_path}")

print("\n完了")
