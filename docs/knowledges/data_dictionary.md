# legacy/_inbox データ辞書

**作成日**: 2026-02-18 17:00
**目的**: legacy/_inbox配下のデータセットを整理し、戦略検証での利用を支援

---

## 📊 概要

- **総ファイル数**: 約10,210ファイル
- **総サイズ**: 約1.8GB
- **データ期間**: 2016年1月～2026年1月（約10年間）
- **データソース**: J-Quants API（日本株式データ）
- **主要形式**: parquet（圧縮効率とクエリ性能に優れる）

---

## 📁 ディレクトリ一覧

| ディレクトリ | 役割・用途 | ファイル数 | 総サイズ | 形式 |
|------------|-----------|-----------|---------|------|
| **jquants_daily_bars_10y_parquet/** | 日足4本値（OHLCV） | 2,452 | 976MB | parquet |
| **jquants_fins_summary_10y_parquet/** | 財務データ（四半期・通期） | 4,878 | 210MB | parquet |
| **merged_data_all_stocks/** | 統合データ（日足+財務+ファクター） | 2,211 | 526MB | parquet |
| data/cache/ | キャッシュファイル | 数十 | 104MB | 混在 |
| data/teacher/ | 学習データ | - | - | - |
| logs/ | バックテストログ | 数百 | 数MB | log/txt |
| reports/ | レポート出力 | - | - | csv/png |
| その他 | 設定ファイル、スクリプト等 | - | - | 混在 |

---

## 🔍 主要データセット詳細

### 1. jquants日足データ（OHLCV）

#### パス
```
legacy/_inbox/jquants_daily_bars_10y_parquet/daily_parquet/
```

#### ファイル構造
- **分割方式**: 日付ごとに1ファイル（`date=YYYY-MM-DD.parquet`）
- **ファイル数**: 2,452ファイル
- **期間**: 2016-01-15 ～ 2026-01-XX（約10年分の営業日）
- **1ファイルあたり**: 約360～370KB

#### 列名とデータ型
| 列名 | データ型 | 説明 | 主キー | 備考 |
|------|---------|------|--------|------|
| **Date** | datetime64 | 取引日 | ✓ | YYYY-MM-DD形式 |
| **Code** | str/int | 銘柄コード | ✓ | 4桁（例：7203） |
| **Open** | float64 | 始値 | - | 円 |
| **High** | float64 | 高値 | - | 円 |
| **Low** | float64 | 安値 | - | 円 |
| **Close** | float64 | 終値 | - | 円 |
| **Volume** | int64 | 出来高 | - | 株数 |
| **AdjustedClose** | float64 | 調整後終値 | - | 分割・配当調整済み |

#### 主キー
- **Code + Date** （銘柄コード + 取引日）

#### 列名の揺れ
- `AdjustedClose`: 標準列名（推奨）
- 別名: `AdjustmentClose`, `AdjC`, `AdjClose`, `AdjCl`
- → **統一案**: `AdjustedClose` を標準とする

#### データ期間・範囲
- **期間**: 2016-01-15 ～ 2026-01-XX（約2,452営業日）
- **銘柄数**: 推定約4,000銘柄（上場・廃止を含む）
- **観測数**: 約900万～1,000万行（2,452日 × 約4,000銘柄）

#### サンプルデータ
```
Date        Code  Open   High   Low    Close  Volume    AdjustedClose
2016-01-15  7203  6425   6470   6320   6348   12345000  6348.0
2016-01-15  9984  3250   3280   3200   3245   8765000   3245.0
...
```

#### 注意点
1. **営業日のみ**: 休日・祝日はデータなし
2. **欠損値**: 売買停止・上場廃止銘柄は該当日のデータなし
3. **分割調整**: `AdjustedClose` は過去に遡って調整済み
4. **単位**: 価格は円、出来高は株数

---

### 2. jquants財務データ（四半期・通期）

#### パス
```
legacy/_inbox/jquants_fins_summary_10y_parquet/
├── daily_parquet/         # 生データ（日付で分割）
├── daily_parquet_norm/    # 正規化済み（推奨）
└── daily_parquet_raw/     # 生データ（バックアップ）
```

#### サブディレクトリの違い
- **daily_parquet**: 日付ごとに分割された生データ
- **daily_parquet_norm**: 列名正規化・型変換済み（**推奨**）
- **daily_parquet_raw**: バックアップ用生データ

#### ファイル構造
- **分割方式**: 開示日ごとに1ファイル
- **ファイル数**: 4,878ファイル
- **期間**: 2016年～2026年（約10年分の開示）

#### 列名とデータ型
| 列名 | データ型 | 説明 | 主キー | 備考 |
|------|---------|------|--------|------|
| **Code** | str/int | 銘柄コード | ✓ | 4桁（例：7203） |
| **DisclosedDate** | datetime64 | 開示日 | ✓ | YYYY-MM-DD |
| **CompanyName** | str | 会社名 | - | - |
| **Profit** | float64 | 純利益 | - | 百万円 |
| **Equity** | float64 | 純資産 | - | 百万円 |
| **Revenue** | float64 | 売上高 | - | 百万円（データにより欠損あり） |
| **Assets** | float64 | 総資産 | - | 百万円（データにより欠損あり） |
| **IssuedShareTotal** | int64 | 発行済株式総数 | - | 株数 |

#### 主キー
- **Code + DisclosedDate** （銘柄コード + 開示日）

#### 列名の揺れ
- `Profit`: 標準列名（推奨）
  - 別名: `NetIncome`, `ProfitAttributableToOwnersOfParent`
- `Equity`: 標準列名（推奨）
  - 別名: `NetAssets`, `TotalEquity`
- → **統一案**: `Profit`, `Equity` を標準とする

#### データ期間・範囲
- **期間**: 2016年～2026年（約10年分）
- **銘柄数**: 推定約4,000銘柄
- **観測数**: 約40万～50万行（四半期開示 × 銘柄数 × 年数）

#### サンプルデータ
```
Code  DisclosedDate  CompanyName      Profit   Equity    IssuedShareTotal
7203  2016-05-11     トヨタ自動車     2000000  15000000  3262997492
9984  2016-05-10     ソフトバンクG    800000   8000000   1188952334
...
```

#### 注意点
1. **開示タイミング**: 四半期決算発表日（通常、決算期末の1～2ヶ月後）
2. **四半期 vs 通期**: データにより区別が必要（`CurrentPeriodEndDate` 等で判定）
3. **欠損値**: 新規上場・データ未公開銘柄は該当期のデータなし
4. **単位**: 百万円（Profit, Equity, Revenue, Assets）

---

### 3. 統合データ（merged_data_all_stocks/）

#### パス
```
legacy/_inbox/merged_data_all_stocks/
├── factors/               # ファクターデータ（月次スナップショット等）
├── merged_parts/          # 日次統合データ（日付で分割）
├── daily_parts/           # 日次データ（パーツ）
├── fins_parts/            # 財務データ（パーツ）
├── analysis_daily/        # 日次分析結果
├── analysis_ff5/          # FF5ファクター分析結果
└── backtest/              # バックテスト結果
```

#### 重要ファイル

##### factors/month_end_snapshot.parquet（最重要）
- **サイズ**: 13MB
- **最終更新**: 2026-01-27
- **内容**: 月末時点の株価・財務・ファクター統合データ
- **用途**: FF5モデル等のバックテストで利用

##### 列名とデータ型
| 列名 | データ型 | 説明 | 主キー | 備考 |
|------|---------|------|--------|------|
| **Code** | int | 銘柄コード | ✓ | 数値型 |
| **MonthEnd** | datetime64 | 月末日 | ✓ | YYYY-MM-DD |
| **Date** | datetime64 | 取引日 | - | 月末またはそれ以前の営業日 |
| **AdjustedClose** | float64 | 調整後終値 | - | 円 |
| **Vo** | float64 | 出来高回転率 | - | - |
| **MarketCap** | float64 | 時価総額 | - | 円 |
| **BM_Ratio** | float64 | 簿価時価比率 | - | Book-to-Market |
| **ROE** | float64 | 自己資本利益率 | - | % |
| **INV_Growth** | float64 | 投資成長率 | - | - |
| **Profit** | float64 | 純利益 | - | 百万円 |
| **Equity** | float64 | 純資産 | - | 百万円 |
| **SharesOut** | int64 | 発行済株式数 | - | 株数 |

##### 主キー
- **Code + MonthEnd** （銘柄コード + 月末日）

##### データ期間・範囲
- **期間**: 2016-03 ～ 2026-01（約119ヶ月）
- **銘柄数**: 推定約4,000～5,000銘柄
- **観測数**: 約40万～50万行

##### サンプルデータ
```
Code  MonthEnd    Date        AdjustedClose  Vo      MarketCap   BM_Ratio  ROE    INV_Growth
7203  2016-03-31  2016-03-31  6500           0.85    25000000    0.60      12.5   0.05
9984  2016-03-31  2016-03-31  3300           1.20    35000000    0.45      8.0    0.10
...
```

##### merged_parts/merged-part-*.parquet
- **内容**: 日次統合データ（日足 + 財務）
- **分割方式**: パーティション（merged-part-001.parquet, merged-part-002.parquet等）
- **用途**: 日次バックテスト、詳細分析
- **列**: Date, Code, AdjustedClose, Profit, Equity, PBR, ROE等

#### 注意点
1. **既に統合済み**: 日足と財務が結合済みのため、最も利用しやすい
2. **ファクター計算済み**: BM_Ratio, ROE, INV_Growth等が計算済み
3. **月次 vs 日次**: month_end_snapshot（月次）とmerged_parts（日次）で用途を使い分け
4. **推奨**: 新規分析では `factors/month_end_snapshot.parquet` を優先利用

---

## 🔗 列名の揺れと統一案

### 銘柄コード
| 実際の列名 | 統一案 | 備考 |
|-----------|--------|------|
| Code | **Code** | 標準（4桁文字列または数値） |
| Ticker | Code | （必要に応じて変換） |
| Symbol | Code | （必要に応じて変換） |
| コード | Code | （日本語列名は避ける） |

### 日付
| 実際の列名 | 統一案 | 用途 |
|-----------|--------|------|
| Date | **Date** | 取引日（日足データ） |
| 日付 | Date | （日本語列名は避ける） |
| DisclosedDate | **DisclosedDate** | 開示日（財務データ） |
| MonthEnd | **MonthEnd** | 月末日（月次データ） |

### 価格
| 実際の列名 | 統一案 | 備考 |
|-----------|--------|------|
| AdjustedClose | **AdjustedClose** | 調整後終値（推奨） |
| AdjustmentClose | AdjustedClose | 揺れ |
| AdjC / AdjClose / AdjCl | AdjustedClose | 揺れ |
| Close | Close | 未調整終値 |
| Open / High / Low | Open / High / Low | 4本値 |

### 財務
| 実際の列名 | 統一案 | 備考 |
|-----------|--------|------|
| Profit | **Profit** | 純利益（百万円） |
| NetIncome | Profit | 揺れ |
| ProfitAttributableToOwnersOfParent | Profit | 揺れ |
| Equity | **Equity** | 純資産（百万円） |
| NetAssets | Equity | 揺れ |
| TotalEquity | Equity | 揺れ |

---

## 🔑 結合キーと注意点

### 主キー候補

#### 1. 日足データ
- **主キー**: `Code + Date`
- **一意性**: 1銘柄 × 1取引日 = 1レコード
- **注意**: 売買停止・上場廃止時は該当日のデータなし

#### 2. 財務データ
- **主キー**: `Code + DisclosedDate`
- **一意性**: 1銘柄 × 1開示日 = 1レコード（通常）
- **注意**: 修正開示・再発表時は重複の可能性あり → `keep='first'` で最新を優先

#### 3. 統合データ（月次スナップショット）
- **主キー**: `Code + MonthEnd`
- **一意性**: 1銘柄 × 1月末 = 1レコード
- **注意**: 月末営業日が基準

### テーブル間結合方法

#### パターン1: 日足 ⟕ 財務（直接結合）
**非推奨**（日付の不一致が多い）

```python
# DisclosedDateからDateへのマッピングが複雑
# → 統合データの利用を推奨
```

#### パターン2: 統合データの利用（推奨）
**推奨**（既に結合済み）

```python
import pandas as pd

# 月次スナップショット（日足+財務+ファクター）
df = pd.read_parquet('legacy/_inbox/merged_data_all_stocks/factors/month_end_snapshot.parquet')

# 必要な列のみ抽出
df = df[['Code', 'MonthEnd', 'AdjustedClose', 'BM_Ratio', 'ROE', 'INV_Growth']]
```

#### パターン3: 日次統合データの利用
**日次バックテスト用**

```python
import pandas as pd
import glob

# 日次統合データ（複数パーツを結合）
files = glob.glob('legacy/_inbox/merged_data_all_stocks/merged_parts/merged-part-*.parquet')
df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
```

---

## ⚠️ 懸念点・注意事項

### 1. 取引日カレンダー
- **営業日のみ**: 土日祝日・年末年始はデータなし
- **対処**: `pd.date_range(freq='B')` で営業日生成、またはTOPIX取引日カレンダーを参照

### 2. 欠損値
- **株価データ**: 売買停止・上場廃止時は欠損
  - 対処: `fillna()` で前方補完または削除
- **財務データ**: 新規上場・未公開企業は欠損
  - 対処: `dropna()` で削除、または推定値で補完

### 3. 上場廃止・新規上場
- **上場廃止**: 廃止日以降はデータなし
  - 注意: バックテストで「サバイバーシップバイアス」を避けるため、廃止銘柄も含める
- **新規上場**: 上場日以前はデータなし
  - 対処: 上場日以降のデータのみ利用

### 4. 株式分割・併合
- **AdjustedClose**: 過去に遡って調整済み（推奨）
- **Close（未調整）**: 分割・併合の影響を受ける
  - 注意: 未調整終値を使う場合は手動で調整が必要

### 5. データ更新頻度
- **legacy/_inbox**: 原本（更新なし）
- **実運用**: 最新データは別途J-Quants APIから取得が必要

### 6. 四半期 vs 通期
- **財務データ**: 四半期決算と通期決算が混在
  - 対処: `CurrentPeriodEndDate` やレコード間隔で判定
  - 推奨: 統合データ（month_end_snapshot）を利用（既に処理済み）

### 7. 列名の揺れ
- **AdjustedClose**: `AdjustmentClose`, `AdjC`, `AdjClose`, `AdjCl` 等の別名あり
  - 対処: 読み込み時に統一（`rename(columns={...})`）

### 8. 未来参照（lookahead bias）
- **禁止**: t日時点の特徴量は t+1日以降を参照しない
- **財務データ**: `DisclosedDate`（開示日）以降に利用可能
  - 注意: 決算日ではなく開示日を基準とする（CLAUDE.md遵守）

---

## 📝 推奨事項

1. **統合データを優先利用**:
   - `merged_data_all_stocks/factors/month_end_snapshot.parquet` は最も利用しやすい
   - 日足・財務・ファクターが既に統合済み

2. **列名を統一**:
   - `AdjustedClose`, `Code`, `Date`, `Profit`, `Equity` を標準とする
   - 読み込み時に `rename()` で統一

3. **主キーを明確化**:
   - 日足: `Code + Date`
   - 財務: `Code + DisclosedDate`
   - 月次: `Code + MonthEnd`

4. **未来参照を避ける**:
   - t日時点の特徴量は t+1日以降を参照しない（CLAUDE.md遵守）
   - DisclosedDate以降に財務データを利用

5. **legacy/_inbox は原本**:
   - 編集・移動・削除禁止（参照のみ）
   - 解析時は data/raw または data/curated にコピー

---

**最終更新**: 2026-02-18 17:00
**次回更新**: 新規データセット追加時、または列定義変更時
