# J-Quants データ更新パイプライン 実装計画

**作成日**: 2026-02-18 14:30
**目的**: J-Quantsから日本株の日次OHLCV・財務データを週次で差分更新するパイプライン構築

---

## 1. 要件定義

### 1.1 インタビュー結果
| 項目 | 決定事項 |
|------|----------|
| 認証情報 | J-Quants.envのAPIキーを使用 |
| 保存形式 | Parquet優先 |
| 価格データ | 調整済みのみ |
| 財務有効日 | 発表日以降のみ（未来参照回避） |
| 更新頻度 | 週1回実行、営業日判定含む |
| 既存マスター | これからdata/curatedを正にする |
| 差分範囲 | 直近3ヶ月のみ差分更新 |
| 銘柄範囲 | 全上場銘柄 |

### 1.2 安全制約
- **legacy/** 配下は原本として扱う（編集・移動・削除禁止、参照のみ）
- 更新結果は **data/raw** と **data/curated** に作成
- 実行前にファイル一覧を提示して承認を取る

---

## 2. J-Quants API 仕様

### 2.1 認証
- **リフレッシュトークン取得**: https://jpx.cloud/jquants-api/auth.html
- **API仕様書**: https://jpx.cloud/jquants-api/

### 2.2 エンドポイント

#### 日次株価（OHLCV）
- **エンドポイント**: `/listed/v1/daily_quotes`
- **ドキュメント**: https://jpx.cloud/jquants-api/daily-quotes.html
- **取得項目**:
  - Date, Code（銘柄コード）
  - Open, High, Low, Close, Volume
  - AdjustmentFactor（調整係数）
  - AdjustmentOpen, AdjustmentHigh, AdjustmentLow, AdjustmentClose, AdjustmentVolume
- **取得方法**: `date_from`, `date_to` で期間指定（最大3ヶ月）

#### 財務データ
- **エンドポイント**: `/listed/v1/statements`
- **ドキュメント**: https://jpx.cloud/jquants-api/statements.html
- **取得項目**:
  - DisclosedDate（開示日）、DisclosedTime
  - Code（銘柄コード）、FiscalYear、FiscalQuarter
  - NetSales、OperatingProfit、OrdinaryProfit、Profit
  - TotalAssets、Equity、EquityToAssetRatio
  - EarningsPerShare、DividendPerShare
  - ForecastNetSales、ForecastOperatingProfit、ForecastProfit、ForecastEarningsPerShare、ForecastDividendPerShare
- **取得方法**: `disclosed_date_from`, `disclosed_date_to` で期間指定

#### リフレッシュトークン
- **エンドポイント**: `/auth/refresh`
- **用途**: アクセストークンの更新（有効期限24時間）

---

## 3. データフロー設計

### 3.1 ディレクトリ構成
```
data/
├── raw/jquants/
│   ├── prices/
│   │   └── daily_quotes_YYYYMMDD.parquet
│   └── financials/
│       └── statements_YYYYMMDD.parquet
└── curated/jquants/
    ├── prices/
    │   └── daily_quotes_all.parquet （統合・QC済み）
    └── financials/
        └── statements_all.parquet （統合・QC済み）
```

### 3.2 データパイプライン
```
[J-Quants API]
    ↓
[scripts/ingest/update_jquants_prices.py] → data/raw/jquants/prices/
[scripts/ingest/update_jquants_financials.py] → data/raw/jquants/financials/
    ↓
[scripts/qc/qc_jquants.py] （QC実施）
    ↓
data/curated/jquants/ （統合・QC済みデータ）
```

---

## 4. 差分更新ロジック

### 4.1 初回実行
- `data/curated/jquants/prices/daily_quotes_all.parquet` が存在しない場合
- 過去3ヶ月分をフル取得してcuratedに保存

### 4.2 差分更新（2回目以降）
1. **最終更新日の取得**
   - `data/curated/jquants/prices/daily_quotes_all.parquet` の最大Date
   - `data/curated/jquants/financials/statements_all.parquet` の最大DisclosedDate

2. **差分期間の決定**
   - 価格：`最終更新日 + 1日` ～ `本日`
   - 財務：`最終更新日 + 1日` ～ `本日`

3. **API取得**
   - 期間が3ヶ月超の場合は3ヶ月ずつ分割して取得

4. **統合**
   - 既存curated + 新規raw → 重複削除 → curated更新

### 4.3 3ヶ月制約の対応
- J-Quants APIは1リクエストで最大3ヶ月まで
- 3ヶ月超の場合はループで分割取得：
  ```python
  start_date = last_date + 1日
  while start_date < today:
      end_date = min(start_date + 90日, today)
      fetch_data(start_date, end_date)
      start_date = end_date + 1日
  ```

---

## 5. QC（品質チェック）項目

### 5.1 価格データ
- [ ] **重複チェック**: (Date, Code) の重複
- [ ] **日付連続性**: 営業日カレンダーと照合（欠損日を検出）
- [ ] **欠損値**: Close, Volume等の必須カラムがNullでないか
- [ ] **異常値**:
  - Close <= 0
  - Volume < 0
  - AdjustmentFactor <= 0 または極端な値（例：0.01未満、100超）
- [ ] **調整価格の整合性**: AdjustmentClose ≈ Close × AdjustmentFactor

### 5.2 財務データ
- [ ] **重複チェック**: (Code, DisclosedDate, FiscalYear, FiscalQuarter) の重複
- [ ] **欠損値**: Code, DisclosedDate, FiscalYearがNullでないか
- [ ] **異常値**:
  - Equity < 0（債務超過は正常値として許容）
  - TotalAssets < 0
  - EquityToAssetRatio > 100%（%単位の場合）
- [ ] **未来参照チェック**: DisclosedDate < FiscalPeriodEnd （発表日が期末日より前はNG）

### 5.3 共通
- [ ] **件数チェック**: 取得件数がゼロでないか、想定範囲内か
- [ ] **型チェック**: 各カラムのdtypeが想定通りか（Date→datetime64, Volume→int64等）

---

## 6. 実装計画

### 6.1 Phase 1: Dry-Run実装（優先）
**目的**: API呼び出しを最小化し、データフロー全体を通す

#### 6.1.1 実装ファイル
1. **scripts/ingest/update_jquants_prices.py**
   - 認証（J-Quants.envからAPIキー読み込み）
   - `/listed/v1/daily_quotes` 呼び出し
   - dry-runモード: 1銘柄（例：7203トヨタ）× 直近5営業日のみ取得
   - data/raw/jquants/prices/ にparquet保存

2. **scripts/ingest/update_jquants_financials.py**
   - `/listed/v1/statements` 呼び出し
   - dry-runモード: 1銘柄 × 直近1ヶ月のみ取得
   - data/raw/jquants/financials/ にparquet保存

3. **scripts/qc/qc_jquants.py**
   - data/raw → QC実行 → data/curated に統合
   - dry-runモード: QCエラーは警告のみ（処理は継続）

4. **docs/knowledges/jquants_update_runbook.md**
   - 実行方法: `python scripts/ingest/update_jquants_prices.py --dry-run`
   - トラブル対応: API制限、認証エラー、QC失敗時の対応

#### 6.1.2 Dry-Run実行手順
```bash
# 1. 価格データ取得（dry-run）
python scripts/ingest/update_jquants_prices.py --dry-run

# 2. 財務データ取得（dry-run）
python scripts/ingest/update_jquants_financials.py --dry-run

# 3. QC実行
python scripts/qc/qc_jquants.py --dry-run

# 4. curated確認
# data/curated/jquants/prices/daily_quotes_all.parquet が生成されていることを確認
```

### 6.2 Phase 2: 本番実装
- dry-runで問題なければ `--dry-run` フラグを外して全銘柄・全期間（直近3ヶ月）を取得
- QCエラー時は処理を停止し、ログ出力

### 6.3 Phase 3: 自動化（将来）
- 週次実行スクリプト（cron/タスクスケジューラ）
- 営業日判定ロジック追加
- エラー通知（メール/Slack等）

---

## 7. 依存ライブラリ

```python
pandas
pyarrow  # parquet読み書き
requests  # J-Quants API呼び出し
python-dotenv  # .env読み込み
```

インストール:
```bash
pip install pandas pyarrow requests python-dotenv
```

---

## 8. リスクと対策

| リスク | 対策 |
|--------|------|
| API制限（1日5000リクエスト等） | 銘柄リストを分割、リトライロジック |
| 認証トークン期限切れ | 自動リフレッシュロジック実装 |
| 3ヶ月超の差分発生 | ループ分割取得（4.3参照） |
| QC失敗 | dry-runで事前検証、ログ詳細化 |
| データ破損 | raw/curatedを分離、curatedは追記のみ（上書き禁止） |
| legacy/との不整合 | legacy/は参照のみ、curatedを正とする |

---

## 9. 成功基準

- [ ] dry-runで1銘柄×短期間のデータ取得・QC・統合が完了
- [ ] data/curated/jquants/ に統合データが生成される
- [ ] QCレポートでエラーゼロ（または許容範囲内）
- [ ] runbookに従って他の人が実行可能
- [ ] 本番実行で全銘柄×直近3ヶ月のデータ取得完了

---

## 10. Next Steps

1. ✅ 計画承認（本ドキュメント）
2. ⬜ 作成ファイル一覧提示 → ユーザー承認
3. ⬜ Dry-Run実装
   - scripts/ingest/update_jquants_prices.py
   - scripts/ingest/update_jquants_financials.py
   - scripts/qc/qc_jquants.py
   - docs/knowledges/jquants_update_runbook.md
4. ⬜ Dry-Run実行・検証
5. ⬜ 本番実行
6. ⬜ docs/sessions/ にサマリ保存

---

**計画作成者**: Claude Code
**レビュー待ち**: ユーザー承認後、実装開始
