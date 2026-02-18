# データ更新スクリプト作成計画

**作成日時**: 2026-02-18 18:00
**目的**: J-Quants APIから日足データと財務データを定期的に更新するスクリプトを作成

---

## 前提条件

### ユーザー要件
1. **目的**: データを定期的に最新化したい
2. **保存先**: 新しいデータは別の場所に保存（legacy/_inboxは原本として保持）
3. **APIキー**: J-Quants APIのAPIキーは .env に設定済み

### 技術要件
- J-Quants API を使用
- parquet形式で保存（圧縮効率・クエリ性能）
- 既存データ（legacy/_inbox）との互換性を保つ

---

## アーキテクチャ設計

### ディレクトリ構造
```
workspace/
├── scripts/
│   └── fetch_jquants_data.py       # データ取得スクリプト（新規作成）
├── data/
│   └── fetched/                     # 新規データ保存先
│       ├── daily_bars/              # 日足データ（parquet）
│       ├── fins_summary/            # 財務データ（parquet）
│       └── logs/                    # 取得ログ
├── legacy/_inbox/                   # 原本（読み取り専用）
└── docs/
    └── knowledges/
        └── data_update_howto.md     # 更新手順書（新規作成）
```

### データ保存形式
- **日足データ**: `data/fetched/daily_bars/YYYYMMDD.parquet`（日付ごとに分割）
- **財務データ**: `data/fetched/fins_summary/YYYYMMDD.parquet`（開示日ごとに分割）
- **ログ**: `data/fetched/logs/fetch_YYYYMMDD_HHMMSS.log`

---

## スクリプト仕様

### scripts/fetch_jquants_data.py

#### 機能
1. J-Quants APIから日足データ（OHLCV）を取得
2. J-Quants APIから財務データ（Profit, Equity等）を取得
3. parquet形式で保存
4. 取得ログを記録
5. エラーハンドリング（API制限、ネットワークエラー等）

#### コマンドライン引数
```bash
python scripts/fetch_jquants_data.py --data-type daily     # 日足のみ
python scripts/fetch_jquants_data.py --data-type fins      # 財務のみ
python scripts/fetch_jquants_data.py --data-type all       # 両方（デフォルト）
python scripts/fetch_jquants_data.py --days 7              # 過去7日分
python scripts/fetch_jquants_data.py --start-date 2026-01-01 --end-date 2026-02-18
```

#### 依存ライブラリ
- `pandas`: データフレーム操作
- `pyarrow`: parquet保存
- `requests`: HTTP通信
- `python-dotenv`: .env読み込み
- `jquants-api-client`: J-Quants API公式ライブラリ（推奨）

#### 処理フロー
1. .env から APIキー読み込み
2. J-Quants APIにログイン（ID token取得）
3. 日足データ取得（`/prices/daily_quotes` エンドポイント）
4. 財務データ取得（`/fins/statements` エンドポイント）
5. parquet形式で保存（日付ごとに分割）
6. ログ記録
7. 完了メッセージ表示

---

## 実装ステップ

### Step 1: .env ファイル確認
- [ ] `legacy/_inbox/.env` の存在確認
- [ ] J-Quants APIキーの確認（`JQUANTS_MAIL_ADDRESS`, `JQUANTS_PASSWORD`）

### Step 2: スクリプト作成
- [ ] `scripts/fetch_jquants_data.py` の作成
- [ ] 日足データ取得機能の実装
- [ ] 財務データ取得機能の実装
- [ ] parquet保存機能の実装
- [ ] ログ記録機能の実装
- [ ] コマンドライン引数パース

### Step 3: テスト実行
- [ ] 過去1週間分のデータ取得テスト
- [ ] parquetファイルの確認
- [ ] legacy/_inbox のデータとの互換性確認

### Step 4: ドキュメント作成
- [ ] `docs/knowledges/data_update_howto.md` の作成
  - 実行手順
  - トラブルシューティング
  - データ確認方法

---

## 成果物

### 1. scripts/fetch_jquants_data.py
日足データと財務データを取得するスクリプト

### 2. docs/knowledges/data_update_howto.md
データ更新手順書（実行方法、トラブルシューティング等）

### 3. data/fetched/
新規データ保存先ディレクトリ

### 4. docs/sessions/20260218_1800_data_updater.md
作業サマリ

---

## 注意事項

### 1. APIレート制限
- J-Quants APIにはレート制限あり（詳細はプラン依存）
- 大量データ取得時は適切な待機時間を設定

### 2. データ互換性
- legacy/_inbox のデータ形式（列名、データ型）と互換性を保つ
- 既存の分析コード（analyses/）がそのまま使えるようにする

### 3. エラーハンドリング
- ネットワークエラー時は自動リトライ（最大3回）
- API制限エラー時は適切なエラーメッセージ表示

### 4. セキュリティ
- .env ファイルは git に含めない（.gitignore に追加済みか確認）
- APIキーをログに出力しない

---

## 推定所要時間
- Step 1: 5分（.env確認）
- Step 2: 30分（スクリプト作成）
- Step 3: 10分（テスト実行）
- Step 4: 15分（ドキュメント作成）
- **合計**: 約60分

---

**次回更新**: スクリプト完成後、実運用での改善点を反映
