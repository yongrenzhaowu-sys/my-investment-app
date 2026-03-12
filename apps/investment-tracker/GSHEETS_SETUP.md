# Google Sheetsセットアップガイド

## 概要

Streamlit Cloudではアプリ再起動時にローカルデータが消えるため、Google Sheetsを使ってデータを永続化します。

## 前提条件

- Googleアカウント
- Google Cloud Platformプロジェクト（無料）

## セットアップ手順

### 1. Google Cloudプロジェクトの作成

1. https://console.cloud.google.com/ にアクセス
2. 新しいプロジェクトを作成
   - プロジェクト名: `investment-tracker`（任意）
3. プロジェクトを選択

### 2. Google Sheets APIを有効化

1. 左メニュー → 「APIとサービス」 → 「ライブラリ」
2. 「Google Sheets API」を検索
3. 「有効にする」をクリック
4. 同様に「Google Drive API」も有効化

### 3. サービスアカウントの作成

1. 左メニュー → 「APIとサービス」 → 「認証情報」
2. 「認証情報を作成」 → 「サービスアカウント」
3. サービスアカウント名: `investment-tracker-sa`（任意）
4. 「作成して続行」をクリック
5. ロールは設定不要（スキップ）
6. 「完了」をクリック

### 4. サービスアカウントキーの作成

1. 作成したサービスアカウントをクリック
2. 「キー」タブ → 「鍵を追加」 → 「新しい鍵を作成」
3. キーのタイプ: **JSON**
4. 「作成」をクリック
5. JSONファイルがダウンロードされる（**重要: 安全に保管**）

JSONファイルの中身（例）:
```json
{
  "type": "service_account",
  "project_id": "investment-tracker-12345",
  "private_key_id": "abcdef1234567890",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg...\n-----END PRIVATE KEY-----\n",
  "client_email": "investment-tracker-sa@investment-tracker-12345.iam.gserviceaccount.com",
  "client_id": "123456789012345678901",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

### 5. Google Spreadsheetsの作成

1. https://sheets.google.com/ にアクセス
2. 新しいスプレッドシートを作成
3. スプレッドシート名: `investment-tracker-data`（任意）
4. シート名を「**hypotheses**」に変更（重要）
5. スプレッドシートのURLをコピー
   - 例: `https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7G8H9I0J/edit`
   - スプレッドシートID: `1A2B3C4D5E6F7G8H9I0J`

### 6. サービスアカウントに権限を付与

1. スプレッドシートの「共有」ボタンをクリック
2. サービスアカウントのメールアドレスを入力
   - 例: `investment-tracker-sa@investment-tracker-12345.iam.gserviceaccount.com`
3. 権限: **編集者**
4. 「送信」をクリック

### 7. Streamlit Secretsの設定

#### ローカル開発環境（.streamlit/secrets.toml）

`.streamlit/secrets.toml` に以下を追加：

```toml
# Google Sheetsを使用するかどうか
USE_GSHEETS = false  # ローカル開発時はfalse（JSONファイル使用）

# Google Sheets接続設定（Streamlit Cloud用）
[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7G8H9I0J/edit"
worksheet = "hypotheses"  # デフォルトシート名（省略可）
type = "service_account"
project_id = "investment-tracker-12345"
private_key_id = "abcdef1234567890"
private_key = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg...\n-----END PRIVATE KEY-----\n"
client_email = "investment-tracker-sa@investment-tracker-12345.iam.gserviceaccount.com"
client_id = "123456789012345678901"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

**重要**: ダウンロードしたJSONファイルの内容を、そのまま `[connections.gsheets]` セクションにコピーしてください。

#### Streamlit Cloud

1. Streamlit Cloud管理画面 → アプリ設定 → Secrets
2. 以下の内容を入力：

```toml
# J-Quants API
JQUANTS_API_KEY = "あなたのAPIキー"
APP_PASSWORD = "あなたのパスワード"

# Google Sheetsを使用
USE_GSHEETS = true

# Google Sheets接続設定
[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7G8H9I0J/edit"
type = "service_account"
project_id = "investment-tracker-12345"
private_key_id = "abcdef1234567890"
private_key = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg...\n-----END PRIVATE KEY-----\n"
client_email = "investment-tracker-sa@investment-tracker-12345.iam.gserviceaccount.com"
client_id = "123456789012345678901"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

3. 「Save」をクリック
4. アプリを再起動

## データ構造

Google Sheetsの「hypotheses」シートには、以下のカラムが自動作成されます：

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | 文字列 | 仮説のユニークID（UUID） |
| code | 文字列 | 銘柄コード（5桁） |
| name | 文字列 | 銘柄名 |
| purchase_date | 文字列 | 購入日（YYYY-MM-DD） |
| purchase_price | 数値 | 購入価格（円） |
| reason | 文字列 | 購入理由 |
| exit_kpi | 文字列 | 撤退KPI（JSON形式） |
| created_at | 文字列 | 作成日時（ISO8601） |

## 動作確認

### ローカル環境（JSONファイル）

1. `.streamlit/secrets.toml` で `USE_GSHEETS = false`
2. アプリ起動
3. 仮説登録
4. `data/hypotheses.json` にデータが保存されることを確認

### Streamlit Cloud（Google Sheets）

1. Streamlit CloudのSecretsで `USE_GSHEETS = true`
2. アプリ起動
3. 仮説登録
4. Google Spreadsheetsを開いて、データが保存されていることを確認

## トラブルシューティング

### エラー: "Google Sheets接続エラー"

**原因**: Secrets設定が正しくない

**対処法**:
1. `connections.gsheets` セクションが正しく設定されているか確認
2. `private_key` の改行文字（`\n`）が正しくエスケープされているか確認
3. サービスアカウントのメールアドレスがスプレッドシートに共有されているか確認

### エラー: "Permission denied"

**原因**: サービスアカウントに権限がない

**対処法**:
1. スプレッドシートの「共有」設定を確認
2. サービスアカウントのメールアドレスが「編集者」権限で追加されているか確認

### データが読み込めない

**原因**: シート名が正しくない

**対処法**:
1. スプレッドシートのシート名が「**hypotheses**」になっているか確認
2. Secretsの `worksheet = "hypotheses"` が正しいか確認

## セキュリティ注意事項

- サービスアカウントのJSONキーは絶対に公開しない
- `.streamlit/secrets.toml` は `.gitignore` に含まれている（コミット禁止）
- スプレッドシートは公開設定にしない（サービスアカウントのみに共有）

## 参考リンク

- Streamlit Google Sheets Connection: https://docs.streamlit.io/develop/tutorials/databases/gsheets
- Google Cloud Console: https://console.cloud.google.com/
- Google Sheets API: https://developers.google.com/sheets/api
