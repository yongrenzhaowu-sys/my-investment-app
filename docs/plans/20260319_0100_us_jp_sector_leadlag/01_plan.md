# 日米業種リードラグ投資戦略 - 実装計画

**作成日**: 2026-03-19 01:00
**参照論文**: `docs/knowledges/日米業種リードラグ投資.pdf`
**実装期間**: 3～4時間（推定）

---

## 🎯 目標

部分空間正則化付きPCAを用いた日米業種リードラグ戦略を実装し、バックテストで有効性を検証する。

---

## 📊 戦略の詳細

### 仮説
米国市場で時点tに確定した業種別情報が、日本市場の翌営業日t+1の日中リターン（Open-to-Close）に波及する。

### データ
- **米国**: S&P 500の11セクターETF
  - XLB (Materials), XLC (Communication Services), XLE (Energy)
  - XLF (Financials), XLI (Industrials), XLK (Technology)
  - XLP (Consumer Staples), XLRE (Real Estate), XLU (Utilities)
  - XLV (Health Care), XLY (Consumer Discretionary)

- **日本**: TOPIX-17業種別ETF
  - 1617.T (食品), 1618.T (エネルギー資源), 1619.T (建設・資材)
  - 1620.T (素材・化学), 1621.T (医薬品), 1622.T (自動車・輸送機)
  - 1623.T (鉄鋼・非鉄), 1624.T (機械), 1625.T (電機・精密)
  - 1626.T (情報通信・サービス), 1627.T (電力・ガス)
  - 1628.T (運輸・物流), 1629.T (商社・卸売), 1630.T (小売)
  - 1631.T (銀行), 1632.T (金融), 1633.T (不動産)

- **期間**: 2010-01-01～2025-12-31

### シグナル構築

#### 1. 事前部分空間（K=3）
- **ファクター1**: グローバル（全銘柄に等重み）
- **ファクター2**: 国スプレッド（米国+、日本-）
- **ファクター3**: シクリカル・ディフェンシブ
  - シクリカル（米国）: XLB, XLE, XLF, XLRE
  - ディフェンシブ（米国）: XLK, XLP, XLU, XLV
  - シクリカル（日本）: 1618.T, 1625.T, 1629.T, 1631.T
  - ディフェンシブ（日本）: 1617.T, 1621.T, 1627.T, 1630.T

#### 2. 部分空間正則化PCA
```python
# 正則化相関行列（λ=0.9）
C_reg_t = (1 - λ) * C_t + λ * C_0

# 固有分解
V_t, Λ_t = eig(C_reg_t)

# 上位K=3個の固有ベクトルを抽出
V_U_t, V_J_t = V_t[:NU, :K], V_t[NU:, :K]

# 米国当日ショックを射影
f_t = V_U_t.T @ z_U_t

# 日本翌日シグナル
ẑ_J_t+1 = V_J_t @ f_t
```

#### 3. ロングショート戦略
- 上位30%（q=0.3）をロング
- 下位30%をショート
- 等ウェイト

---

## 🔧 実装タスク

### タスク1: データ取得（60分）
**ファイル**: `analyses/20260319_0100_us_jp_sector_leadlag/fetch_data.py`

```python
import yfinance as yf
import pandas as pd
from datetime import datetime

# 米国11セクターETF
us_tickers = ['XLB', 'XLC', 'XLE', 'XLF', 'XLI', 'XLK',
              'XLP', 'XLRE', 'XLU', 'XLV', 'XLY']

# 日本17業種ETF
jp_tickers = ['1617.T', '1618.T', '1619.T', '1620.T', '1621.T',
              '1622.T', '1623.T', '1624.T', '1625.T', '1626.T',
              '1627.T', '1628.T', '1629.T', '1630.T', '1631.T',
              '1632.T', '1633.T']

# データ取得（Open, Close, Adj Close）
# 期間: 2010-01-01 ~ 2025-12-31
```

**出力**:
- `data/raw/us_jp_leadlag/us_sectors.parquet`
- `data/raw/us_jp_leadlag/jp_sectors.parquet`

---

### タスク2: 前処理・リターン計算（30分）
**ファイル**: `analyses/20260319_0100_us_jp_sector_leadlag/preprocess.py`

```python
# Close-to-Closeリターン（米国、相関行列推定用）
r_cc_us_t = (Close_t / Close_t-1) - 1

# Close-to-Closeリターン（日本、相関行列推定用）
r_cc_jp_t = (Close_t / Close_t-1) - 1

# Open-to-Closeリターン（日本、戦略評価用）
r_oc_jp_t = (Close_t / Open_t) - 1

# 共通営業日のみ抽出（米国t日と日本t+1日が両方存在）
```

**出力**:
- `data/processed/us_jp_leadlag/returns.parquet`

---

### タスク3: 事前部分空間の構築（30分）
**ファイル**: `analyses/20260319_0100_us_jp_sector_leadlag/build_prior_subspace.py`

```python
# ファクター1: グローバル（全銘柄に等重み）
v1 = np.ones(N) / np.sqrt(N)

# ファクター2: 国スプレッド
v2_raw = np.concatenate([np.ones(NU), -np.ones(NJ)])
v2 = orthogonalize(v2_raw, v1)

# ファクター3: シクリカル・ディフェンシブ
cyclical_us = ['XLB', 'XLE', 'XLF', 'XLRE']
defensive_us = ['XLK', 'XLP', 'XLU', 'XLV']
cyclical_jp = ['1618.T', '1625.T', '1629.T', '1631.T']
defensive_jp = ['1617.T', '1621.T', '1627.T', '1630.T']

v3_raw = sign_vector(cyclical_us, defensive_us, cyclical_jp, defensive_jp)
v3 = orthogonalize(v3_raw, [v1, v2])

V0 = np.column_stack([v1, v2, v3])

# 長期ウィンドウ（2010-2014）で固有値推定
C_full = corr_matrix(returns['2010':'2014'])
D0 = diag(V0.T @ C_full @ V0)

# ターゲット行列
C0_raw = V0 @ D0 @ V0.T
C0 = normalize_to_correlation(C0_raw)
```

**出力**:
- `analyses/20260319_0100_us_jp_sector_leadlag/prior_subspace.pkl`

---

### タスク4: シグナル生成（60分）
**ファイル**: `analyses/20260319_0100_us_jp_sector_leadlag/generate_signals.py`

```python
def generate_signal(t, window_size=60, lambda_reg=0.9, K=3):
    """
    時点tの米国リターンから、t+1の日本リターンを予測

    Args:
        t: 現在時点
        window_size: ローリングウィンドウサイズ（60営業日）
        lambda_reg: 正則化パラメータ（0.9）
        K: 抽出する固有ベクトル数（3）

    Returns:
        signal_jp_t+1: 日本17業種のシグナル
    """
    # ウィンドウ内データ
    window = returns[t-window_size:t]

    # 標準化
    z_t = standardize(window)

    # ウィンドウ内相関行列
    C_t = np.corrcoef(z_t.T)

    # 正則化
    C_reg_t = (1 - lambda_reg) * C_t + lambda_reg * C0

    # 固有分解
    eigenvalues, eigenvectors = np.linalg.eigh(C_reg_t)
    idx = eigenvalues.argsort()[::-1][:K]
    V_K_t = eigenvectors[:, idx]

    # 米国・日本ブロックに分割
    V_U_t = V_K_t[:NU, :]
    V_J_t = V_K_t[NU:, :]

    # 米国当日リターンを標準化
    z_U_t = standardize_with_window_params(r_cc_us_t, window)

    # ファクタースコア
    f_t = V_U_t.T @ z_U_t

    # 日本翌日シグナル
    signal_jp_t_plus_1 = V_J_t @ f_t

    return signal_jp_t_plus_1
```

**出力**:
- `analyses/20260319_0100_us_jp_sector_leadlag/signals.parquet`

---

### タスク5: バックテスト実装（60分）
**ファイル**: `analyses/20260319_0100_us_jp_sector_leadlag/backtest.py`

```python
def backtest(signals, returns_oc, q=0.3):
    """
    ロングショート戦略のバックテスト

    Args:
        signals: 日本17業種のシグナル
        returns_oc: 日本のOpen-to-Closeリターン
        q: 上位・下位の分位点（0.3 = 30%）

    Returns:
        strategy_returns: 戦略リターン系列
    """
    portfolio_returns = []

    for t in range(len(signals)):
        # 時点tのシグナル
        signal_t = signals.iloc[t]

        # 上位30%をロング
        long_set = signal_t.nlargest(int(len(signal_t) * q)).index

        # 下位30%をショート
        short_set = signal_t.nsmallest(int(len(signal_t) * q)).index

        # 等ウェイト
        weights = pd.Series(0.0, index=signal_t.index)
        weights[long_set] = 1 / len(long_set)
        weights[short_set] = -1 / len(short_set)

        # 翌日t+1のOpen-to-Closeリターン
        returns_t_plus_1 = returns_oc.iloc[t + 1]

        # 戦略リターン
        R_t_plus_1 = (weights * returns_t_plus_1).sum()
        portfolio_returns.append(R_t_plus_1)

    return pd.Series(portfolio_returns)
```

**評価指標**:
- 年率リターン（AR）
- 年率リスク（RISK）
- シャープレシオ相当（R/R）
- 最大ドローダウン（MDD）

**出力**:
- `analyses/20260319_0100_us_jp_sector_leadlag/backtest_results.csv`

---

### タスク6: ベースライン比較（30分）
**ファイル**: `analyses/20260319_0100_us_jp_sector_leadlag/compare_baselines.py`

実装する戦略：
1. **MOM**: 日本側のみの単純モメンタム（60日平均）
2. **PCA_PLAIN**: 正則化なしPCA（λ=0）
3. **PCA_SUB**: 提案手法（λ=0.9）
4. **DOUBLE**: MOMとPCA_SUBのダブルソート

**出力**:
- `analyses/20260319_0100_us_jp_sector_leadlag/comparison_table.csv`
- `analyses/20260319_0100_us_jp_sector_leadlag/cumulative_returns.png`

---

## 📈 期待される結果（論文ベース）

| 戦略 | AR (%) | RISK (%) | R/R | MDD (%) |
|:---:|---:|---:|---:|---:|
| MOM | 5.63 | 10.59 | 0.53 | 16.97 |
| PCA_PLAIN | 6.24 | 9.94 | 0.62 | 23.65 |
| **PCA_SUB** | **23.79** | **10.70** | **2.22** | **9.58** |
| DOUBLE | 18.86 | 11.16 | 1.69 | 12.10 |

---

## ⚠️ 重要な注意事項

### 1. データの整合性
- 米国t日終値確定後に、日本t+1日のOpen価格が利用可能
- 共通営業日（米国t日と日本t+1日が両方存在）のみ使用
- 休日・祝日の違いに注意

### 2. ルックアヘッドバイアス防止
```python
# ✅ 正しい: 時点tまでのデータで、t+1を予測
signal_t = generate_signal(window=returns[:t])
entry_t_plus_1 = returns_oc[t+1]

# ❌ 間違い: t+1のデータを使ってt+1を予測
signal_t = generate_signal(window=returns[:t+1])  # NG!
```

### 3. yfinanceのデータ取得
- 調整済み終値（Adj Close）を使用
- Open価格は未調整の場合があるため、Adj Closeとの比率で調整
```python
adj_factor = df['Adj Close'] / df['Close']
df['Adj Open'] = df['Open'] * adj_factor
```

---

## 🚀 実装順序（推奨）

1. **タスク1**: データ取得（yfinance）
2. **タスク2**: 前処理・リターン計算
3. **タスク3**: 事前部分空間の構築
4. **タスク4**: シグナル生成（60日ローリング）
5. **タスク5**: バックテスト実装
6. **タスク6**: ベースライン比較・可視化

---

## 📁 出力構造

```
analyses/20260319_0100_us_jp_sector_leadlag/
├── fetch_data.py
├── preprocess.py
├── build_prior_subspace.py
├── generate_signals.py
├── backtest.py
├── compare_baselines.py
├── visualize.py
├── prior_subspace.pkl
├── signals.parquet
├── backtest_results.csv
├── comparison_table.csv
└── cumulative_returns.png

data/
├── raw/us_jp_leadlag/
│   ├── us_sectors.parquet
│   └── jp_sectors.parquet
└── processed/us_jp_leadlag/
    └── returns.parquet
```

---

## 📚 参照資料

- 論文: `docs/knowledges/日米業種リードラグ投資.pdf`
- ルックアヘッドバイアス防止: `docs/knowledges/20260225_1900_lookahead_bias_correction.md`

---

**次回セッション開始時**: このファイルを確認してタスク1から開始
