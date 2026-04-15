# 調整済み株価の検証方法（J-Quants API）

**作成日**: 2026-03-19
**重要度**: 🚨 CRITICAL
**適用範囲**: 全ての株価データ分析

## 🎯 背景

2026-03-18のFF5ファクター分析で、**J-Quants APIの`AdjC`列が実際には調整されていない**ことを発見しました。

### 発見の経緯
1. 銘柄スクリーニングで極端なリターン値（+3,273%）を検出
2. 株価データを確認したところ、`AdjC = C`（調整なし）
3. `AdjFactor`列は存在するが、適用されていない
4. 株式分割（例: 10分割でAdjFactor 1.0→0.1）が反映されていない

### 影響
- **リターン計算が誤る**（株式分割時に10倍のリターンとして計算）
- **時価総額が誤る**（株価×発行済株式数）
- **PBRが誤る**（株価/BPS）
- **ファクター分析が誤る**（SMB, HML, WML等）

---

## ✅ 必須の検証手順

### 1. AdjFactorの確認

```python
import pandas as pd

# データ読み込み
df_prices = pd.read_parquet("daily_bars_2021_2026.parquet")

# AdjFactorが1.0以外のレコードを確認
adj_records = df_prices[df_prices['AdjFactor'] != 1.0]
print(f"調整係数が1.0でないレコード: {len(adj_records):,}レコード")

# 具体例を表示
sample = adj_records.head(10)
print(sample[['Code', 'Date', 'C', 'AdjC', 'AdjFactor']])
```

**期待される結果**
- `AdjFactor != 1.0`のレコードが存在する
- `AdjC = C`の場合は**調整されていない**

### 2. 正しい調整の適用

```python
# 正しい調整済み株価の計算
df_prices['AdjC_Correct'] = df_prices['C'] * df_prices['AdjFactor']

# 検証: 調整前後の比較
df_compare = df_prices[df_prices['AdjFactor'] != 1.0].head(10)
print(df_compare[['Code', 'Date', 'C', 'AdjC', 'AdjC_Correct', 'AdjFactor']])
```

**確認ポイント**
- `AdjC_Correct`が`C`と異なる
- 株式分割時（AdjFactor < 1.0）に価格が下がる

### 3. 時系列での連続性確認

```python
# 特定銘柄の時系列推移を確認
code = "9434"  # 例: ソフトバンク
df_code = df_prices[df_prices['Code'] == code].sort_values('Date')

# AdjFactorの変化点を確認
adj_changes = df_code[df_code['AdjFactor'] != df_code['AdjFactor'].shift(1)]
print(f"{code}のAdjFactor変化点: {len(adj_changes)}回")
print(adj_changes[['Date', 'C', 'AdjC', 'AdjC_Correct', 'AdjFactor']])

# グラフ化（推奨）
import matplotlib.pyplot as plt
fig, axes = plt.subplots(2, 1, figsize=(12, 8))

axes[0].plot(df_code['Date'], df_code['C'], label='C (終値)', alpha=0.7)
axes[0].plot(df_code['Date'], df_code['AdjC'], label='AdjC (API提供)', alpha=0.7)
axes[0].set_title(f'{code} - 調整前株価')
axes[0].legend()
axes[0].grid(True)

axes[1].plot(df_code['Date'], df_code['AdjC_Correct'], label='AdjC_Correct (C × AdjFactor)', alpha=0.7)
axes[1].set_title(f'{code} - 調整済み株価（正しい）')
axes[1].legend()
axes[1].grid(True)

plt.tight_layout()
plt.savefig('adjusted_price_validation.png', dpi=150)
```

---

## 🔧 標準的な修正パターン

### パターン1: 株価データ読み込み時

```python
def load_adjusted_prices(parquet_path):
    """
    J-Quants APIの株価データを正しく調整

    Args:
        parquet_path: parquetファイルのパス

    Returns:
        pd.DataFrame: 調整済み株価データ
    """
    df = pd.read_parquet(parquet_path)

    # 日付型に変換
    df['Date'] = pd.to_datetime(df['Date'])

    # Codeを4桁に統一
    df['Code'] = df['Code'].str[:4]

    # ✅ 調整済み株価を正しく計算
    df['AdjC_Correct'] = df['C'] * df['AdjFactor']
    df['Price'] = df['AdjC_Correct']

    # ✅ 重複データの除外（同じCode×Dateで最も取引量が多いレコードを採用）
    df = df.sort_values(['Code', 'Date', 'Vo'], ascending=[True, True, False])
    df = df.drop_duplicates(subset=['Code', 'Date'], keep='first')

    print(f"調整係数が1.0でないレコード: {(df['AdjFactor'] != 1.0).sum():,}レコード")
    print(f"重複除外後: {len(df):,}レコード")

    return df
```

### パターン2: リターン計算時

```python
def calculate_return(df, period_days=180):
    """
    調整済み株価を使ってリターンを計算

    Args:
        df: 株価データ（Date, Code, Price列を含む）
        period_days: リターン計算期間（日数）

    Returns:
        pd.DataFrame: リターン付きデータ
    """
    df = df.sort_values(['Code', 'Date'])

    # period_days前の価格を取得
    df['Price_Prev'] = df.groupby('Code')['Price'].shift(period_days // 5)  # 営業日ベース

    # リターン計算
    df['Return'] = (df['Price'] / df['Price_Prev']) - 1

    # 異常値除外（±500%以上は除外）
    df.loc[(df['Return'] < -5) | (df['Return'] > 5), 'Return'] = pd.NA

    return df
```

### パターン3: 時価総額計算時

```python
def calculate_market_cap(df_prices, df_fins):
    """
    調整済み株価を使って時価総額を計算

    Args:
        df_prices: 株価データ（Date, Code, Price列を含む）
        df_fins: 財務データ（Code, Eq, BPS列を含む）

    Returns:
        pd.DataFrame: 時価総額付きデータ
    """
    # 最新の株価を取得
    latest_prices = df_prices.sort_values('Date').groupby('Code').last().reset_index()
    latest_prices = latest_prices[['Code', 'Price']]

    # 最新の財務データを取得
    latest_fins = df_fins.sort_values('DiscDate').groupby('Code').last().reset_index()
    latest_fins = latest_fins[['Code', 'Eq', 'BPS']]

    # マージ
    merged = latest_prices.merge(latest_fins, on='Code', how='inner')

    # ✅ 時価総額計算（調整済み株価を使用）
    merged['MarketCap'] = merged['Price'] * (merged['Eq'] / merged['BPS'])

    return merged
```

---

## 🚨 よくある間違い

### ❌ 間違い1: AdjCをそのまま使用

```python
# ❌ 間違い
df_prices['Price'] = df_prices['AdjC']  # AdjC = Cの可能性
```

```python
# ✅ 正しい
df_prices['Price'] = df_prices['C'] * df_prices['AdjFactor']
```

### ❌ 間違い2: AdjFactorの確認を省略

```python
# ❌ 間違い（確認せずに使用）
df_prices['Return'] = df_prices['AdjC'].pct_change()
```

```python
# ✅ 正しい（確認してから使用）
print(f"AdjFactor != 1.0: {(df_prices['AdjFactor'] != 1.0).sum()}レコード")
df_prices['AdjC_Correct'] = df_prices['C'] * df_prices['AdjFactor']
df_prices['Return'] = df_prices['AdjC_Correct'].pct_change()
```

### ❌ 間違い3: 重複データを無視

```python
# ❌ 間違い（重複データをそのまま使用）
df_prices = pd.read_parquet("daily_bars.parquet")
```

```python
# ✅ 正しい（重複データを除外）
df_prices = pd.read_parquet("daily_bars.parquet")
df_prices = df_prices.sort_values(['Code', 'Date', 'Vo'], ascending=[True, True, False])
df_prices = df_prices.drop_duplicates(subset=['Code', 'Date'], keep='first')
```

---

## 📊 実績データ

### 修正前（誤り）
- データソース: `AdjC`列（未調整）
- 最大リターン: **+3,273%**
- 異常銘柄数: 多数

### 修正後（正しい）
- データソース: `C × AdjFactor`
- 最大リターン: **+568.73%**
- 異常銘柄数: ほぼゼロ

### 具体例: 銘柄9434（ソフトバンク）
- AdjFactorの変化: 1.0 → 0.1 → 1.0（株式分割）
- `AdjC`（誤り）: 分割の影響なし
- `AdjC_Correct`（正しい）: 分割で価格が1/10に

---

## ✅ チェックリスト

新しい株価データを使う前に、以下を必ず確認：

- [ ] `AdjFactor != 1.0`のレコード数を確認
- [ ] `AdjC = C`かどうかを確認
- [ ] `AdjC_Correct = C × AdjFactor`を計算
- [ ] 重複データ（同じCode×Date）を除外
- [ ] 特定銘柄の時系列推移を可視化
- [ ] リターン計算の異常値（±500%超）を確認
- [ ] 時価総額の異常値（極端に大きい/小さい）を確認

---

## 🔗 関連資料

### 本セッション
- `docs/sessions/20260319_0000_ff5_corrected_screening.md`

### 実装ファイル
- `analyses/20260318_1800_ff5_rolling_6years/calculate_ff5_rolling_corrected.py`
- `analyses/20260318_1800_ff5_rolling_6years/screen_stocks_corrected.py`

### 過去の教訓
- `docs/knowledges/20260225_1900_lookahead_bias_correction.md`（ルックアヘッドバイアス防止）
- `docs/knowledges/20260318_1730_bps_recovery_technique.md`（BPS代替計算）

---

**更新日**: 2026-03-19
**ステータス**: ✅ 完了
