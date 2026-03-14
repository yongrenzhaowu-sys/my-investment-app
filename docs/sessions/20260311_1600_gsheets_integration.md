# セッション記録: Google Sheets統合

**日時**: 2026-03-11 16:00
**作業時間**: 約1時間
**ステータス**: ✅ 実装完了

## やったこと

### Google Sheets統合によるデータ永続化

Streamlit Cloudではアプリ再起動時にローカルデータが消えるため、Google Sheetsを使ってデータを永続化する機能を実装しました。

### 実装した機能

#### 1. Google Sheets接続モジュール
- `src/gsheets_client.py` を新規作成
- `st.connection("gsheets", type=GSheetsConnection)` を使用
- `load_hypotheses()`: Google Sheetsからデータ読み込み
- `save_hypotheses()`: Google Sheetsへデータ保存
- エラーハンドリング（初回アクセス時の空シート対応）

#### 2. app.pyの修正
- ローカル環境（JSONファイル）とクラウド環境（Google Sheets）の自動切り替え
- `USE_GSHEETS` フラグで制御
- フォールバック機能（Google Sheets接続エラー時はJSONファイル使用）

#### 3. ドキュメント作成
- `GSHEETS_SETUP.md`: Google Sheetsセットアップガイド
  - Google Cloud Platformプロジェクト作成
  - Google Sheets API有効化
  - サービスアカウント作成
  - JSONキーのダウンロード
  - スプレッドシート作成・共有
  - Streamlit Secrets設定

#### 4. 依存パッケージ更新
- `requirements.txt` に `st-gsheets-connection>=0.0.3` を追加

#### 5. Secrets設定テンプレート更新
- `.streamlit/secrets.toml.example` を更新
- `USE_GSHEETS` フラグ追加
- `[connections.gsheets]` セクション追加
- サービスアカウントJSONキーの設定例

#### 6. デプロイガイド更新
- `DEPLOY.md` にGoogle Sheetsセットアップ手順を追加
- Streamlit CloudのSecrets設定例を更新

## データ構造

### Google Sheetsのカラム構成

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | 文字列 | UUID |
| code | 文字列 | 銘柄コード（5桁） |
| name | 文字列 | 銘柄名 |
| purchase_date | 文字列 | 購入日（YYYY-MM-DD） |
| purchase_price | 数値 | 購入価格 |
| reason | 文字列 | 購入理由 |
| exit_kpi | 文字列 | 撤退KPI（JSON形式） |
| created_at | 文字列 | 作成日時 |

## Streamlit Secrets設定

### ローカル環境（.streamlit/secrets.toml）

```toml
USE_GSHEETS = false  # JSONファイル使用
```

### Streamlit Cloud

```toml
USE_GSHEETS = true

[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/YOUR_ID/edit"
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "sa@project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "..."
client_x509_cert_url = "..."
```

## 修正ファイル一覧

- ✅ `requirements.txt` （st-gsheets-connection追加）
- ✅ `src/gsheets_client.py` （新規作成）
- ✅ `app.py` （Google Sheets対応）
- ✅ `GSHEETS_SETUP.md` （新規作成）
- ✅ `.streamlit/secrets.toml.example` （更新）
- ✅ `DEPLOY.md` （更新）
- ✅ `README.md` （更新）

## 次の手順（Streamlit Cloudデプロイ時）

### 1. Google Cloudセットアップ

1. Google Cloud Platformでプロジェクト作成
2. Google Sheets API、Google Drive APIを有効化
3. サービスアカウント作成 → JSONキーをダウンロード

### 2. Google Spreadsheetsの準備

1. 新しいスプレッドシートを作成
2. シート名を「**hypotheses**」に変更
3. サービスアカウントに編集権限を付与

### 3. Streamlit Cloudデプロイ

1. GitHubにpush
2. Streamlit Cloudでアプリ作成
3. Secretsに以下を設定：
   - `JQUANTS_API_KEY`
   - `APP_PASSWORD`
   - `USE_GSHEETS = true`
   - `[connections.gsheets]` セクション全体

### 4. 動作確認

1. アプリにアクセス
2. 仮説登録
3. Google Spreadsheetsでデータ確認

## 重要な注意点

### セキュリティ
- サービスアカウントのJSONキーは絶対に公開しない
- `.streamlit/secrets.toml` は `.gitignore` に含まれている
- スプレッドシートは公開設定にしない

### データ同期
- Google Sheetsはリアルタイムで同期
- 複数ユーザーが同時に編集可能（競合に注意）
- キャッシュ設定: `ttl=0`（常に最新データ取得）

### エラーハンドリング
- Google Sheets接続エラー時はJSONファイルにフォールバック
- 初回アクセス時の空シート対応済み
- データが見つからない場合は空リストを返す

## 学んだこと

### st.connection() の使い方
- Streamlitの標準的なデータ接続方法
- サービスアカウント認証が必要
- TOML形式でSecrets設定

### Google Sheets APIの制限
- 1分間に100リクエストまで
- 1日あたり500リクエストまで（無料プラン）
- キャッシュ（ttl）設定で制限を回避

### Streamlit Cloudの特性
- アプリ再起動時にローカルストレージが消える
- 永続化が必要なデータは外部サービスを使用
- Google Sheets、Firebase、PostgreSQLなどが選択肢

## 参考リンク

- Streamlit Google Sheets Connection: https://docs.streamlit.io/develop/tutorials/databases/gsheets
- Google Cloud Console: https://console.cloud.google.com/
- st-gsheets-connection: https://github.com/streamlit/gsheets-connection
