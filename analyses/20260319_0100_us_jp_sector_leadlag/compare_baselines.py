"""
ベースライン比較

1. MOM: 日本のみの単純モメンタム（60日平均）
2. PCA_PLAIN: 正則化なしPCA（λ=0）
3. PCA_SUB: 提案手法（λ=0.9）
"""
import pandas as pd
import numpy as np
from pathlib import Path
import pickle

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data/processed/us_jp_leadlag"
PRIOR_PATH = Path(__file__).parent / "prior_subspace.pkl"
OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("="*80)
print("ベースライン比較")
print("="*80)

# パラメータ
WINDOW_SIZE = 60
Q = 0.3
K = 3

# データ読み込み
print("\n[1] データ読み込み")
df = pd.read_parquet(INPUT_DIR / "returns.parquet")

# 事前部分空間読み込み
with open(PRIOR_PATH, 'rb') as f:
    prior = pickle.load(f)

C0 = prior['C0']
us_tickers = prior['us_tickers']
jp_tickers = prior['jp_tickers']
N_US = prior['N_US']
N_JP = prior['N_JP']

# リターン列
us_cc_cols = [f'US_CC_{t}' for t in us_tickers]
jp_cc_cols = [f'JP_CC_{t}' for t in jp_tickers]
jp_oc_cols = [f'JP_OC_{t}' for t in jp_tickers]
all_cc_cols = us_cc_cols + jp_cc_cols

returns_cc = df[all_cc_cols].values
returns_oc_jp = df[jp_oc_cols].values

print(f"  データ: {len(df)}日")
print(f"  米国: {N_US}銘柄、日本: {N_JP}銘柄")


def backtest_strategy(signals, returns_oc, q=0.3):
    """戦略バックテスト"""
    portfolio_returns = []

    for t in range(len(signals)):
        signal = signals[t]
        n_long = int(len(signal) * q)
        n_short = int(len(signal) * q)

        long_idx = np.argsort(signal)[-n_long:]
        short_idx = np.argsort(signal)[:n_short]

        weights = np.zeros(len(signal))
        weights[long_idx] = 1 / n_long
        weights[short_idx] = -1 / n_short

        R_t = np.sum(weights * returns_oc[t])
        portfolio_returns.append(R_t)

    return np.array(portfolio_returns)


def calculate_metrics(returns):
    """評価指標計算"""
    AR = np.mean(returns) * 252 * 100
    RISK = np.std(returns) * np.sqrt(252) * 100
    RR = AR / RISK if RISK > 0 else 0

    cumulative = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative / running_max) - 1
    MDD = np.min(drawdown) * 100

    return {'AR': AR, 'RISK': RISK, 'R/R': RR, 'MDD': MDD}


# 戦略1: MOM（日本のみの単純モメンタム）
print("\n[2] 戦略1: MOM（日本のみ60日平均）")
signals_mom = []

for t in range(WINDOW_SIZE, len(returns_cc)):
    window_jp = returns_cc[t - WINDOW_SIZE:t, N_US:]
    mean_returns_jp = np.mean(window_jp, axis=0)
    signals_mom.append(mean_returns_jp)

signals_mom = np.array(signals_mom)
returns_mom = backtest_strategy(signals_mom, returns_oc_jp[WINDOW_SIZE:], Q)
metrics_mom = calculate_metrics(returns_mom)

print(f"  AR: {metrics_mom['AR']:.2f}%, RISK: {metrics_mom['RISK']:.2f}%, R/R: {metrics_mom['R/R']:.2f}, MDD: {metrics_mom['MDD']:.2f}%")

# 戦略2: PCA_PLAIN（正則化なし、λ=0）
print("\n[3] 戦略2: PCA_PLAIN（λ=0）")
signals_plain = []

for t in range(WINDOW_SIZE, len(returns_cc)):
    window = returns_cc[t - WINDOW_SIZE:t]
    mean_w = np.mean(window, axis=0)
    std_w = np.std(window, axis=0) + 1e-8
    z_window = (window - mean_w) / std_w

    C_t = np.corrcoef(z_window.T)

    # 正則化なし（λ=0）
    eigenvalues, eigenvectors = np.linalg.eigh(C_t)
    idx = eigenvalues.argsort()[::-1][:K]
    V_K_t = eigenvectors[:, idx]

    V_U_t = V_K_t[:N_US, :]
    V_J_t = V_K_t[N_US:, :]

    us_return_t = returns_cc[t, :N_US]
    z_U_t = (us_return_t - mean_w[:N_US]) / std_w[:N_US]

    f_t = V_U_t.T @ z_U_t
    signal_jp = V_J_t @ f_t
    signals_plain.append(signal_jp)

    if (t - WINDOW_SIZE) % 500 == 0:
        print(f"  進捗: {t - WINDOW_SIZE}/{len(returns_cc) - WINDOW_SIZE}")

signals_plain = np.array(signals_plain)
returns_plain = backtest_strategy(signals_plain, returns_oc_jp[WINDOW_SIZE:], Q)
metrics_plain = calculate_metrics(returns_plain)

print(f"  AR: {metrics_plain['AR']:.2f}%, RISK: {metrics_plain['RISK']:.2f}%, R/R: {metrics_plain['R/R']:.2f}, MDD: {metrics_plain['MDD']:.2f}%")

# 戦略3: PCA_SUB（既存の結果を読み込み）
print("\n[4] 戦略3: PCA_SUB（既存結果）")
pca_sub_summary = pd.read_csv(OUTPUT_DIR / "summary_pca_sub.csv")
metrics_sub = {
    'AR': pca_sub_summary['AR'].iloc[0],
    'RISK': pca_sub_summary['RISK'].iloc[0],
    'R/R': pca_sub_summary['R/R'].iloc[0],
    'MDD': pca_sub_summary['MDD'].iloc[0]
}
print(f"  AR: {metrics_sub['AR']:.2f}%, RISK: {metrics_sub['RISK']:.2f}%, R/R: {metrics_sub['R/R']:.2f}, MDD: {metrics_sub['MDD']:.2f}%")

# 比較表作成
print("\n[5] 比較表")
comparison_df = pd.DataFrame({
    'Strategy': ['MOM', 'PCA_PLAIN', 'PCA_SUB'],
    'AR': [metrics_mom['AR'], metrics_plain['AR'], metrics_sub['AR']],
    'RISK': [metrics_mom['RISK'], metrics_plain['RISK'], metrics_sub['RISK']],
    'R/R': [metrics_mom['R/R'], metrics_plain['R/R'], metrics_sub['R/R']],
    'MDD': [metrics_mom['MDD'], metrics_plain['MDD'], metrics_sub['MDD']]
})

print(comparison_df.to_string(index=False))

# 保存
comparison_path = OUTPUT_DIR / "comparison_table.csv"
comparison_df.to_csv(comparison_path, index=False)
print(f"\n[6] 保存完了: {comparison_path}")

print("\n完了")
