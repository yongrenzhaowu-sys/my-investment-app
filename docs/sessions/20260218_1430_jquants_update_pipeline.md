# セッションサマリ: J-Quants データ更新パイプライン構築

**日時**: 2026-02-18 14:30 ～
**目的**: J-Quantsから日本株OHLCV・財務データを週次で差分更新するパイプライン構築

---

## やったこと

### 1. 要件定義（インタビュー）
8問の選択肢形式で要件を明確化：
- 認証情報: J-Quants.envのAPIキー使用
- 保存形式: Parquet優先
- 価格データ: 調整済みのみ
- 財務有効日: 発表日以降のみ（未来参照回避）
- 更新頻度: 週1回実行、営業日判定含む
- 既存マスター: data/curatedを正にする
- 差分範囲: 直近3ヶ月のみ
- 銘柄範囲: 全上場銘柄

### 2. Legacy データ発見・調査
- `legacy/_inbox/jquants_daily_bars_10y_parquet/` （価格、最終日: 2026-01-22）
- `legacy/_inbox/jquants_fins_summary_10y_parquet/` （財務、最終日: 2026-01-09）
- 日付パーティション形式（date=YYYY-MM-DD.parquet）
- スキーマ確認完了（16カラム、108カラム）

### 3. 計画策定
- **01_first_plan.md**: 初期計画（API直接取得想定）
- **02_legacy_integration.md**: Legacy統合を含む修正計画
- **jquants_legacy_schema.md**: データスキーマ定義

### 4. 実装完了
#### スクリプト
1. **scripts/ingest/consolidate_legacy.py**
   - Legacy パーティションデータ統合（初回のみ）
   - dry-runモード: 最新1ヶ月分のみ統合
   - 本番モード: 全期間（10年分）統合

2. **scripts/ingest/update_jquants_prices.py**
   - J-Quants API から価格差分取得
   - 3ヶ月制約を自動分割対応
   - dry-runモード: 1銘柄×直近1週間のみ

3. **scripts/ingest/update_jquants_financials.py**
   - 財務データ差分取得
   - 同様にdry-runモード対応

4. **scripts/qc/qc_jquants.py**
   - 品質チェック（重複、欠損、異常値、未来参照）
   - レポート出力

#### ドキュメント
5. **docs/knowledges/jquants_update_runbook.md**
   - 実行手順マニュアル
   - トラブルシューティング
   - コマンド早見表

### 5. ディレクトリ作成
- `data/raw/jquants/prices/`
- `data/raw/jquants/financials/`
- `data/curated/jquants/prices/`
- `data/curated/jquants/financials/`
- `scripts/ingest/`
- `scripts/qc/`

---

## 決めたこと

### データフロー
```
[legacy/_inbox] (読み取り専用)
    ↓ 初回のみ
[consolidate_legacy.py] → data/curated/ (マスター)
    ↓ 週次
[update_jquants_*.py] → data/raw/ (一時保存)
    ↓
[qc_jquants.py] → data/curated/ (QC後追記)
```

### 差分更新ロジック
1. curated の最終日を取得
2. 最終日 + 1 ～ 今日までをAPI取得
3. 重複削除（後勝ち = API優先）
4. QC実行
5. curated に追記保存

### QC基準
- **エラー**: 重複（キー違反）、必須カラムの欠損
- **警告**: 異常値（close <= 0、volume < 0）、日付空白
- dry-runモードでも警告は表示、エラーでも処理継続しない

### カラムマッピング
- Legacy: `AdjO, AdjH, AdjL, AdjC, AdjVo` → curated: `open, high, low, close, volume`
- API: `AdjustmentOpen, ...` → curated: `open, ...`
- 財務: `DiscDate` → `disclosed_date`（有効日として使用）

---

## 次にやること

### 1. Dry-Run実行（推奨）
```bash
# 1. Legacy統合（最新1ヶ月分）
py scripts/ingest/consolidate_legacy.py --dry-run

# 2. 価格データ取得（1銘柄×直近1週間）
py scripts/ingest/update_jquants_prices.py --dry-run

# 3. 財務データ取得（1銘柄×直近1ヶ月）
py scripts/ingest/update_jquants_financials.py --dry-run

# 4. QC実行
py scripts/qc/qc_jquants.py --dry-run
```

### 2. 本番実行
dry-runで問題なければ `--dry-run` フラグを外して実行：
```bash
py scripts/ingest/consolidate_legacy.py
py scripts/ingest/update_jquants_prices.py
py scripts/ingest/update_jquants_financials.py
py scripts/qc/qc_jquants.py
```

### 3. 週次自動化（将来）
- cron/タスクスケジューラで毎週日曜21時実行
- エラー通知設定（メール/Slack）
- 営業日判定ロジック追加

### 4. データ検証
- curated データを読み込んで期間・銘柄数を確認
- サンプル銘柄（例: 7203トヨタ）の時系列を可視化
- 財務データと価格データの結合テスト

---

## 重要なパス・コマンド

### ディレクトリ
```
legacy/_inbox/jquants_daily_bars_10y_parquet/daily_parquet/
legacy/_inbox/jquants_fins_summary_10y_parquet/daily_parquet/
data/curated/jquants/prices/daily_quotes_all.parquet
data/curated/jquants/financials/statements_all.parquet
```

### コマンド
```bash
# 初回統合
py scripts/ingest/consolidate_legacy.py --dry-run

# 週次更新
py scripts/ingest/update_jquants_prices.py
py scripts/ingest/update_jquants_financials.py
py scripts/qc/qc_jquants.py

# データ確認
py -c "import pandas as pd; df=pd.read_parquet('data/curated/jquants/prices/daily_quotes_all.parquet'); print(df.info())"
```

### 環境変数
```
JQUANTS_REFRESH_TOKEN=xxx  （または J-Quants.env に REFRESH_TOKEN=xxx）
```

---

## 注意点

### Legacy データは読み取り専用
- **絶対に編集・移動・削除しない**
- consolidate_legacy.py は読み込みのみ
- curated を正として運用

### API制限
- 1日5000リクエストまで
- 1リクエストで最大3ヶ月まで → 自動分割対応済み
- リフレッシュトークンの有効期限に注意

### QC失敗時
- エラーを確認してから再実行
- 重複は後勝ちで自動解決
- 異常値は警告のみなら許容

### バックアップ
- curated は月次でバックアップ推奨
- raw は1ヶ月以上前のファイルを削除可

---

## 参照ドキュメント

- [計画書（初版）](../plans/20260218_1430_jquants_update_pipeline/01_first_plan.md)
- [計画書（Legacy統合版）](../plans/20260218_1430_jquants_update_pipeline/02_legacy_integration.md)
- [データスキーマ定義](../knowledges/jquants_legacy_schema.md)
- [実行マニュアル](../knowledges/jquants_update_runbook.md)

---

**ステータス**: 実装完了、Dry-Run実行待ち
**次のアクション**: Dry-Run実行 → 検証 → 本番実行
