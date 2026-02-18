# データ読み込み手順（How-to）

**作成日**: 2026-02-18 17:00
**対象**: legacy/_inbox配下のデータセット
**目的**: 分析notebookから効率的にデータを読み込む

---

## 🎯 基本方針

1. **legacy/_inbox は原本**（読み取り専用）
   - 編集・移動・削除は禁止
   - 参照のみ

2. **解析時はコピーを作成**（必要な場合）
   - `data/raw/`: 生データのコピー
   - `data/curated/`: 加工済みデータ

3. **推奨ライブラリ**
   - `pandas`: データフレーム操作
   - `pyarrow`: parquetファイル読み込み（高速）

4. **パス指定**
   - 絶対パス推奨（プロジェクト間で共通利用）
   - 環境変数で管理（`.env`ファイル等）

---

## 📚 データセット別読み込み方法

### ✅ 推奨：統合データ（月次スナップショット）

**最も簡単で推奨**。日足・財務・ファクターが既に統合済み。

#### パス
```
legacy/_inbox/merged_data_all_stocks/factors/month_end_snapshot.parquet
```

#### 最小コード例
```python
import pandas as pd

# 月次スナップショット読み込み
df = pd.read_parquet(
    r"C:\Users\yongr\claude project\workspace\legacy\_inbox\merged_data_all_stocks\factors\month_end_snapshot.parquet",
    engine="pyarrow"
)

# 列確認
print(df.columns.tolist())
# ['Code', 'MonthEnd', 'Date', 'AdjustedClose', 'Vo', 'MarketCap',
#  'BM_Ratio', 'ROE', 'INV_Growth', 'Profit', 'Equity', 'SharesOut', ...]

# データ型確認
print(df.dtypes)

# 基本統計
print(df.describe())

# 先頭5行表示
print(df.head())
```

#### 列名とデータ型
| 列名 | 型 | 説明 |
|------|-----|------|
| Code | int | 銘柄コード（数値） |
| MonthEnd | datetime64 | 月末日 |
| Date | datetime64 | 取引日 |
| AdjustedClose | float64 | 調整後終値（円） |
| Vo | float64 | 出来高回転率 |
| MarketCap | float64 | 時価総額（円） |
| BM_Ratio | float64 | 簿価時価比率（Book-to-Market） |
| ROE | float64 | 自己資本利益率（%） |
| INV_Growth | float64 | 投資成長率 |
| Profit | float64 | 純利益（百万円） |
| Equity | float64 | 純資産（百万円） |
| SharesOut | int64 | 発行済株式数 |

#### フィルタリング例
```python
# 特定期間のデータ抽出
df_2020 = df[df['MonthEnd'].dt.year == 2020]

# 特定銘柄のデータ抽出
df_toyota = df[df['Code'] == 7203]  # トヨタ自動車

# 条件フィルター（ROE > 10%、かつ PBR < 1.5）
df_filtered = df[(df['ROE'] > 10) & (df['BM_Ratio'] > 0.6)]

# 欠損値除外
df_clean = df.dropna(subset=['BM_Ratio', 'ROE', 'INV_Growth'])
```

#### 注意点
- **日付型変換**: `pd.to_datetime(df['MonthEnd'])` で明示的に変換
- **欠損値**: `dropna()` または `fillna()` で処理
- **主キー**: `Code + MonthEnd` で一意

---

### 日足データ（OHLCV）

**日次バックテスト用**。日付ごとにファイル分割されている。

#### パス
```
legacy/_inbox/jquants_daily_bars_10y_parquet/daily_parquet/
```

#### 最小コード例（単一ファイル）
```python
import pandas as pd

# 特定日のデータ読み込み
df_day = pd.read_parquet(
    r"C:\Users\yongr\claude project\workspace\legacy\_inbox\jquants_daily_bars_10y_parquet\daily_parquet\date=2020-01-06.parquet",
    engine="pyarrow"
)

print(df_day.head())
```

#### 最小コード例（複数日統合）
```python
import pandas as pd
import glob

# 全ファイルを読み込んで結合
parquet_files = glob.glob(
    r"C:\Users\yongr\claude project\workspace\legacy\_inbox\jquants_daily_bars_10y_parquet\daily_parquet\*.parquet"
)

# 先頭10ファイルのみ（テスト用）
df_all = pd.concat(
    [pd.read_parquet(f, engine="pyarrow") for f in parquet_files[:10]],
    ignore_index=True
)

# 日付列を追加（ファイル名から抽出）
df_all['Date'] = pd.to_datetime(df_all['Date'])

print(f"総レコード数: {len(df_all):,}")
print(df_all.head())
```

#### 列名とデータ型
| 列名 | 型 | 説明 |
|------|-----|------|
| Date | datetime64 | 取引日 |
| Code | str/int | 銘柄コード |
| Open | float64 | 始値（円） |
| High | float64 | 高値（円） |
| Low | float64 | 安値（円） |
| Close | float64 | 終値（円） |
| Volume | int64 | 出来高（株数） |
| AdjustedClose | float64 | 調整後終値（円） |

#### 注意点
- **ファイル数**: 2,452ファイル（全読み込みは時間がかかる）
- **推奨**: 必要な期間のみ読み込む（`glob.glob()` でフィルター）
- **列名揺れ**: `AdjustedClose` が `AdjustmentClose` 等の場合あり → 統一処理必要

---

### 財務データ（四半期・通期）

**ファクター計算用**。開示日ごとにファイル分割。

#### パス
```
legacy/_inbox/jquants_fins_summary_10y_parquet/daily_parquet_norm/
```

#### 最小コード例（単一ファイル）
```python
import pandas as pd

# 特定開示日のデータ読み込み
df_fins = pd.read_parquet(
    r"C:\Users\yongr\claude project\workspace\legacy\_inbox\jquants_fins_summary_10y_parquet\daily_parquet_norm\disclosed_date=2020-05-11.parquet",
    engine="pyarrow"
)

print(df_fins.head())
```

#### 列名とデータ型
| 列名 | 型 | 説明 |
|------|-----|------|
| Code | str/int | 銘柄コード |
| DisclosedDate | datetime64 | 開示日 |
| CompanyName | str | 会社名 |
| Profit | float64 | 純利益（百万円） |
| Equity | float64 | 純資産（百万円） |
| Revenue | float64 | 売上高（百万円） |
| Assets | float64 | 総資産（百万円） |
| IssuedShareTotal | int64 | 発行済株式総数 |

#### 注意点
- **四半期 vs 通期**: データにより混在（期間判定が必要）
- **列名揺れ**: `Profit`（NetIncome等）、`Equity`（NetAssets等）
- **推奨**: 統合データ（月次スナップショット）の利用を推奨

---

### 統合データ（日次）

**日次バックテスト用**。merged_parts配下に複数パーティション。

#### パス
```
legacy/_inbox/merged_data_all_stocks/merged_parts/
```

#### 最小コード例
```python
import pandas as pd
import glob

# 全パーツを読み込んで結合
parquet_files = glob.glob(
    r"C:\Users\yongr\claude project\workspace\legacy\_inbox\merged_data_all_stocks\merged_parts\merged-part-*.parquet"
)

# ファイル数確認
print(f"ファイル数: {len(parquet_files)}")

# 先頭1ファイルのみ読み込み（テスト）
df_sample = pd.read_parquet(parquet_files[0], engine="pyarrow")
print(df_sample.columns.tolist())

# 全ファイル読み込み（時間がかかる）
# df_all = pd.concat(
#     [pd.read_parquet(f, engine="pyarrow") for f in parquet_files],
#     ignore_index=True
# )
```

#### 列名（推定）
| 列名 | 型 | 説明 |
|------|-----|------|
| Date | datetime64 | 取引日 |
| Code | int | 銘柄コード |
| AdjustedClose | float64 | 調整後終値（円） |
| Profit | float64 | 純利益（百万円） |
| Equity | float64 | 純資産（百万円） |
| PBR | float64 | 株価純資産倍率 |
| ROE | float64 | 自己資本利益率（%） |

#### 注意点
- **ファイル数**: 数百～数千ファイル（全読み込みは重い）
- **推奨**: 月次スナップショットで十分な場合はそちらを優先

---

## 🔗 データ結合の手順

### パターン1: 統合データを直接利用（推奨）

**最も簡単**。既に結合済み。

```python
import pandas as pd

# 月次スナップショット（日足+財務+ファクター）
df = pd.read_parquet(
    r"C:\Users\yongr\claude project\workspace\legacy\_inbox\merged_data_all_stocks\factors\month_end_snapshot.parquet",
    engine="pyarrow"
)

# 必要な列のみ抽出
df = df[['Code', 'MonthEnd', 'AdjustedClose', 'BM_Ratio', 'ROE', 'INV_Growth']]

# フィルタリング
df = df.dropna(subset=['BM_Ratio', 'ROE', 'INV_Growth'])

print(df.head())
```

### パターン2: 日足 + 財務を手動結合（非推奨）

**複雑**。DisclosedDateからDateへのマッピングが必要。

```python
import pandas as pd

# 日足データ読み込み（簡略例）
df_daily = pd.read_parquet(
    r"C:\Users\yongr\claude project\workspace\legacy\_inbox\jquants_daily_bars_10y_parquet\daily_parquet\date=2020-01-06.parquet",
    engine="pyarrow"
)

# 財務データ読み込み（簡略例）
df_fins = pd.read_parquet(
    r"C:\Users\yongr\claude project\workspace\legacy\_inbox\jquants_fins_summary_10y_parquet\daily_parquet_norm\disclosed_date=2020-05-11.parquet",
    engine="pyarrow"
)

# 結合（複雑なため省略、統合データ利用を推奨）
# DisclosedDate → Date へのマッピングが必要
# ...
```

**推奨**: パターン1（統合データ）を利用する。

---

## ❓ FAQ

### Q1: どのデータセットを使うべきか？

**A**: 用途により異なります。

| 用途 | 推奨データセット | 理由 |
|------|---------------|------|
| 月次リバランス戦略 | **月次スナップショット** | 最も簡単、既に統合済み |
| 日次バックテスト | **日次統合データ** | 日足+財務が結合済み |
| 価格データのみ | 日足データ | OHLCV取得 |
| 財務データのみ | 財務データ | Profit, Equity取得 |

**初心者**: 月次スナップショット（`month_end_snapshot.parquet`）を推奨。

### Q2: 日足と財務をどう結合するか？

**A**: 統合データ（月次スナップショット、または日次統合データ）の利用を強く推奨。

手動結合は複雑（DisclosedDate → Date のマッピング処理が必要）。

### Q3: 欠損値をどう扱うか？

**A**: 用途により異なります。

```python
import pandas as pd

df = pd.read_parquet("...")

# 方法1: 欠損行を削除
df_clean = df.dropna(subset=['BM_Ratio', 'ROE'])

# 方法2: 欠損値を0で埋める（非推奨、バイアスあり）
df_filled = df.fillna({'BM_Ratio': 0, 'ROE': 0})

# 方法3: 前方補完（時系列データの場合）
df_ffill = df.sort_values(['Code', 'Date']).fillna(method='ffill')
```

**推奨**: 欠損行を削除（`dropna()`）が最もシンプルで安全。

### Q4: 列名が期待と異なる場合は？

**A**: 読み込み時に列名を統一する。

```python
import pandas as pd

df = pd.read_parquet("...")

# 列名の揺れを統一
column_mapping = {
    'AdjustmentClose': 'AdjustedClose',
    'AdjC': 'AdjustedClose',
    'NetIncome': 'Profit',
    'NetAssets': 'Equity'
}

df = df.rename(columns=column_mapping)
```

### Q5: 未来参照を避けるには？

**A**: DisclosedDate（開示日）以降にのみ財務データを利用する。

```python
import pandas as pd

# 月次スナップショット（既に開示日考慮済み）
df = pd.read_parquet("month_end_snapshot.parquet")

# t月末時点のファクター値 → t+1月初の売買に使用
# （統合データは既に正しくマッピング済み）
```

**注意**: t日時点の特徴量は t+1日以降を参照しない（CLAUDE.md遵守）。

### Q6: 全データを一度に読み込むとメモリ不足になる場合は？

**A**: チャンク読み込みまたは必要な列・期間のみ抽出する。

```python
import pandas as pd

# 方法1: 列を絞る
df = pd.read_parquet(
    "month_end_snapshot.parquet",
    columns=['Code', 'MonthEnd', 'AdjustedClose', 'ROE'],
    engine="pyarrow"
)

# 方法2: 期間を絞る（読み込み後フィルター）
df = pd.read_parquet("month_end_snapshot.parquet")
df = df[df['MonthEnd'] >= '2020-01-01']

# 方法3: チャンク読み込み（csvの場合）
# for chunk in pd.read_csv("data.csv", chunksize=10000):
#     process(chunk)
```

### Q7: legacy/_inbox のデータを編集したい場合は？

**A**: 絶対に編集しない。data/raw または data/curated にコピーしてから編集する。

```python
import shutil
import pandas as pd

# 1. legacy/_inbox からコピー
shutil.copy(
    r"legacy\_inbox\merged_data_all_stocks\factors\month_end_snapshot.parquet",
    r"data\raw\month_end_snapshot.parquet"
)

# 2. コピーしたファイルを編集
df = pd.read_parquet("data/raw/month_end_snapshot.parquet")
df_processed = df.dropna()  # 例：欠損値除去

# 3. 加工済みデータを保存
df_processed.to_parquet("data/curated/month_end_snapshot_clean.parquet")
```

---

## 🚀 推奨ワークフロー

### 1. 新規分析プロジェクト開始時

```python
import pandas as pd
from pathlib import Path

# プロジェクトルート
PROJECT_ROOT = Path(r"C:\Users\yongr\claude project\workspace")

# 統合データ（月次スナップショット）を読み込み
df = pd.read_parquet(
    PROJECT_ROOT / "legacy/_inbox/merged_data_all_stocks/factors/month_end_snapshot.parquet",
    engine="pyarrow"
)

# 基本確認
print(f"データ期間: {df['MonthEnd'].min()} ~ {df['MonthEnd'].max()}")
print(f"銘柄数: {df['Code'].nunique()}")
print(f"総レコード数: {len(df):,}")
print(f"列: {df.columns.tolist()}")

# 欠損値確認
print(df.isnull().sum())
```

### 2. データクリーニング

```python
# 欠損値除外
df_clean = df.dropna(subset=['BM_Ratio', 'ROE', 'INV_Growth'])

# 異常値除外（例：ROE > 100%）
df_clean = df_clean[df_clean['ROE'] < 100]

# 日付型確認
df_clean['MonthEnd'] = pd.to_datetime(df_clean['MonthEnd'])
df_clean = df_clean.sort_values(['Code', 'MonthEnd']).reset_index(drop=True)
```

### 3. ファクター計算（例：PBR）

```python
# PBR = MarketCap / Equity
df_clean['PBR'] = df_clean['MarketCap'] / df_clean['Equity']

# 異常値除外
df_clean = df_clean[(df_clean['PBR'] > 0) & (df_clean['PBR'] < 50)]
```

### 4. 保存（必要な場合）

```python
# 加工済みデータを保存
df_clean.to_parquet(
    PROJECT_ROOT / "data/curated/month_end_snapshot_clean.parquet",
    engine="pyarrow",
    index=False
)

print("保存完了: data/curated/month_end_snapshot_clean.parquet")
```

---

## 📝 テンプレートコード

### 最小テンプレート（月次スナップショット）

```python
import pandas as pd
from pathlib import Path

# パス設定
PROJECT_ROOT = Path(r"C:\Users\yongr\claude project\workspace")
DATA_PATH = PROJECT_ROOT / "legacy/_inbox/merged_data_all_stocks/factors/month_end_snapshot.parquet"

# データ読み込み
df = pd.read_parquet(DATA_PATH, engine="pyarrow")

# 基本確認
print(df.info())
print(df.head())

# 欠損値除外
df = df.dropna(subset=['BM_Ratio', 'ROE', 'INV_Growth'])

# 分析開始
# ...
```

### 汎用テンプレート（日足+財務）

```python
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\yongr\claude project\workspace")

# 統合データ（月次スナップショット）推奨
df = pd.read_parquet(
    PROJECT_ROOT / "legacy/_inbox/merged_data_all_stocks/factors/month_end_snapshot.parquet",
    engine="pyarrow"
)

# または日次統合データ
# import glob
# files = glob.glob(str(PROJECT_ROOT / "legacy/_inbox/merged_data_all_stocks/merged_parts/*.parquet"))
# df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

# データクリーニング
df = df.dropna(subset=['Code', 'MonthEnd', 'AdjustedClose'])
df['MonthEnd'] = pd.to_datetime(df['MonthEnd'])
df = df.sort_values(['Code', 'MonthEnd']).reset_index(drop=True)

print(f"データ準備完了: {len(df):,}行")
```

---

**最終更新**: 2026-02-18 17:00
**次回更新**: 新規データセット追加時、またはユーザーからのフィードバック反映時
