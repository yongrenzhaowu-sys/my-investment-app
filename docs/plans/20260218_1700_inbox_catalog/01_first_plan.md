# legacy/_inbox データ棚卸し計画

**作成日時**: 2026-02-18 17:00
**目的**: legacy/_inbox配下の雑多な過去取得データを棚卸しし、戦略検証で使えるようにデータ辞書と読み込み手順を整備

---

## 前提条件

### 確認事項（ユーザー回答済み）
1. **棚卸し粒度**: ディレクトリ単位で整理（推奨）
2. **データ辞書内容**: ファイル/フォルダ一覧、列名と型の詳細、期間・銘柄範囲の統計、結合キーと注意点
3. **優先調査**: jquants日足データ、jquants財務データ、統合データ
4. **列名調査**: 代表ファイルのみサンプリング（推奨）

### 対象範囲
- **対象ディレクトリ**: `legacy/_inbox/`
- **総ファイル数**: 約10,210ファイル
- **主要ディレクトリ**:
  - `jquants_daily_bars_10y_parquet/`: J-Quants日足データ（OHLCV）
  - `jquants_fins_summary_10y_parquet/`: J-Quants財務データ（四半期・通期）
  - `merged_data_all_stocks/`: 統合データ（日足+財務+ファクター）
  - `data/cache/`, `data/teacher/`: キャッシュ・学習データ
  - その他：ログファイル、設定ファイル、バックテスト結果等

### 制約事項
- ✅ legacy/_inbox は原本（編集・移動・削除禁止、参照のみ）
- ✅ 解析・変換が必要な場合は data/raw または data/curated にコピー
- ✅ docs/knowledges を優先的に更新（コンテキスト肥大を避ける）
- ✅ 標準Plan modeは使用しない

---

## 作業ステップ

### Step 1: ディレクトリ構造の把握
- [ ] legacy/_inbox の全ディレクトリをリストアップ
- [ ] 各ディレクトリのファイル数、総サイズ、ファイル形式（csv/parquet/json等）を集計
- [ ] ディレクトリの命名パターンから用途を推定

### Step 2: 優先データセットの詳細調査

#### 2-1. jquants日足データ（jquants_daily_bars_10y_parquet/）
- [ ] ディレクトリ構造を確認
- [ ] 代表的な1～3ファイルをサンプリング
- [ ] 列名、データ型、主キー（Code, Date等）を確認
- [ ] データ期間（最古日～最新日）、銘柄数を集計
- [ ] 欠損・重複の有無を確認

#### 2-2. jquants財務データ（jquants_fins_summary_10y_parquet/）
- [ ] サブディレクトリ（daily_parquet, daily_parquet_norm, daily_parquet_raw）の違いを確認
- [ ] 代表的なファイルをサンプリング
- [ ] 列名、データ型、主キー（Code, DisclosedDate等）を確認
- [ ] 四半期・通期の区別、財務項目（Profit, Equity, Revenue等）を特定
- [ ] データ期間、銘柄数を集計

#### 2-3. 統合データ（merged_data_all_stocks/）
- [ ] サブディレクトリ（factors, daily_parts, analysis_*, backtest等）の役割を確認
- [ ] 代表的なファイルをサンプリング
- [ ] 列名、データ型、主キー（Code, Date等）を確認
- [ ] 日足・財務・ファクター（FF5, ROE, PBR等）の結合状態を確認
- [ ] データ期間、銘柄数を集計

### Step 3: 列名の揺れ調査
- [ ] 各優先データセットから代表ファイルの列名を抽出
- [ ] 共通キー（銘柄コード、日付）の列名パターンを特定:
  - 銘柄コード: `Code`, `Ticker`, `Symbol`, `コード` 等
  - 日付: `Date`, `日付`, `DisclosedDate`, `MonthEnd` 等
- [ ] 価格・財務データの列名標準化案を策定

### Step 4: 結合キーと注意点の整理
- [ ] 主キー候補を特定（Code+Date, Code+DisclosedDate等）
- [ ] テーブル間結合の方法を提案:
  - 日足 ⟕ 財務: どの日付キーで結合するか（DisclosedDate前後のDateにマッピング等）
  - 統合データの構築方法
- [ ] 懸念点を列挙:
  - 取引日カレンダー（営業日のみ、休日の扱い）
  - 欠損値（株価データの欠損、財務データの未開示）
  - 上場廃止・新規上場の扱い
  - 株式分割・併合の調整
  - データ更新頻度（リアルタイム vs 日次バッチ）

### Step 5: その他のディレクトリ概要
- [ ] data/cache/, data/teacher/ の概要を記載
- [ ] ログファイル、設定ファイル、バックテスト結果の概要を記載
- [ ] 不要または重複データの候補を特定

---

## 成果物

### 1. docs/knowledges/data_dictionary.md
以下の構成で作成：
```markdown
# legacy/_inbox データ辞書

## 概要
- 総ファイル数、総サイズ、更新日範囲

## ディレクトリ一覧
各ディレクトリについて：
- パス
- 役割・用途
- ファイル数、総サイズ、形式（csv/parquet/json）
- データ期間、銘柄範囲

## 主要データセット詳細

### jquants日足データ
- パス、ファイル構造
- 列名、データ型、主キー
- データ期間、銘柄数、観測数
- サンプルデータ

### jquants財務データ
- パス、ファイル構造（raw/norm/daily_parquetの違い）
- 列名、データ型、主キー
- 財務項目一覧（Profit, Equity, Revenue等）
- データ期間、銘柄数、観測数
- サンプルデータ

### 統合データ
- パス、ファイル構造（factors, daily_parts, analysis_*等）
- 列名、データ型、主キー
- ファクター項目一覧（FF5, ROE, PBR, MarketCap等）
- データ期間、銘柄数、観測数
- サンプルデータ

## 列名の揺れと統一案
- 銘柄コード: Code（標準）, Ticker, Symbol等
- 日付: Date（標準）, 日付, DisclosedDate, MonthEnd等
- 価格: Close, AdjustedClose, Open, High, Low, Volume等
- 財務: Profit, Equity, Revenue, Assets等
- 統一案: 標準列名を定義

## 結合キーと注意点
- 主キー候補: Code+Date, Code+DisclosedDate
- テーブル間結合方法:
  - 日足 ⟕ 財務: DisclosedDateからDateへのマッピング方法
  - 統合データの利用推奨
- 懸念点:
  - 取引日カレンダー
  - 欠損値の扱い
  - 上場廃止・新規上場
  - 株式分割・併合
```

### 2. docs/knowledges/data_access_howto.md
以下の構成で作成：
```markdown
# データ読み込み手順

## 基本方針
- legacy/_inbox は原本（読み取り専用）
- 分析時は必要に応じて data/raw または data/curated にコピー
- 推奨ライブラリ: pandas, pyarrow

## データセット別読み込み方法

### jquants日足データ
- パス: legacy/_inbox/jquants_daily_bars_10y_parquet/daily_parquet/
- 推奨ライブラリ: pandas.read_parquet
- コード例（最小実装）
- 注意点: 日付列の型変換、欠損値処理

### jquants財務データ
- パス: legacy/_inbox/jquants_fins_summary_10y_parquet/daily_parquet_norm/
- 推奨ライブラリ: pandas.read_parquet
- コード例（最小実装）
- 注意点: 四半期・通期の区別、DisclosedDateの扱い

### 統合データ（推奨）
- パス: legacy/_inbox/merged_data_all_stocks/factors/month_end_snapshot.parquet
- 推奨ライブラリ: pandas.read_parquet
- コード例（最小実装）
- 注意点: 既に結合済みのため最も利用しやすい

## データ結合の手順
- 日足 + 財務の結合方法
- ファクター計算の手順
- または統合データの直接利用を推奨

## FAQ
- Q: どのデータセットを使うべきか？
- Q: 日足と財務をどう結合するか？
- Q: 欠損値をどう扱うか？
```

### 3. docs/sessions/20260218_1700_inbox_catalog.md
作業サマリ：
- やったこと
- 作成したファイル（data_dictionary.md, data_access_howto.md）
- 次にやること（data/raw へのコピー、分析での利用等）

---

## 推定所要時間
- Step 1: 10分（ディレクトリ構造把握）
- Step 2: 30分（優先データセット詳細調査）
- Step 3: 10分（列名の揺れ調査）
- Step 4: 10分（結合キー・注意点整理）
- Step 5: 5分（その他概要）
- 文書作成: 20分
- **合計**: 約85分

---

**次回更新**: 棚卸し完了後、実際の分析での利用状況を反映
