# デプロイガイド（Streamlit Cloud）

## 概要

このアプリをStreamlit Cloudにデプロイして、インターネット経由でどこからでもアクセスできるようにします。

## 前提条件

- GitHubアカウント
- Streamlit Cloudアカウント（無料）: https://streamlit.io/cloud

## デプロイするファイル

### 含めるファイル ✅

```
apps/investment-tracker/
├── app.py                      # メインアプリ
├── requirements.txt            # 依存パッケージ
├── README.md                   # 説明
├── SETUP.md                    # セットアップ手順
├── QUICKSTART.md               # クイックスタート
├── .streamlit/
│   ├── config.toml             # Streamlit設定
│   └── secrets.toml.example    # Secretsテンプレート
└── src/
    ├── __init__.py
    ├── auth.py
    ├── api.py
    ├── alpha.py
    ├── kpi_check.py
    └── ui_components.py
```

### 除外するファイル ❌

```
apps/investment-tracker/
├── .streamlit/secrets.toml     # 機密情報（.gitignoreで除外済み）
└── data/hypotheses.json        # 個人データ（.gitignoreで除外済み）
```

## デプロイ手順

### 1. GitHubリポジトリにpush

```bash
cd "C:\Users\yongr\claude project\workspace"

# 変更をステージング
git add apps/investment-tracker/

# コミット
git commit -m "Add investment tracker app for Streamlit Cloud deployment"

# GitHubにpush
git push origin main
```

### 2. Streamlit Cloudにログイン

1. https://streamlit.io/cloud にアクセス
2. 「Sign in with GitHub」でログイン
3. GitHubアカウントと連携

### 3. 新しいアプリをデプロイ

1. 「New app」ボタンをクリック
2. 以下の情報を入力：

| 項目 | 値 |
|------|-----|
| Repository | あなたのリポジトリ名 |
| Branch | main（またはmaster） |
| Main file path | `apps/investment-tracker/app.py` |
| App URL | 好きな名前（例: investment-tracker） |

3. 「Advanced settings」をクリック
4. Python version: `3.11`（推奨）

### 4. Google Sheetsのセットアップ（重要）

Streamlit Cloudでは再起動時にデータが消えるため、Google Sheetsでデータを永続化します。

詳細な手順は [GSHEETS_SETUP.md](GSHEETS_SETUP.md) を参照してください。

**要約**:
1. Google Cloud Platformでプロジェクト作成
2. Google Sheets API、Google Drive APIを有効化
3. サービスアカウント作成 → JSONキーをダウンロード
4. Google Spreadsheetsを作成（シート名: `hypotheses`）
5. サービスアカウントに編集権限を付与

### 5. Secretsを設定

1. デプロイ画面下部の「Advanced settings」→「Secrets」をクリック
2. 以下の内容を入力：

```toml
# J-Quants API
JQUANTS_API_KEY = "あなたのAPIキー"
APP_PASSWORD = "アプリ用パスワード"

# Google Sheetsを使用
USE_GSHEETS = true

# Google Sheets接続設定
[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit"
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project-id.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

**重要**: サービスアカウントのJSONキーの内容をそのまま貼り付けてください。

3. 「Save」をクリック

### 5. デプロイ開始

「Deploy!」ボタンをクリック

### 6. デプロイ完了

数分後、アプリがデプロイされ、URLが表示されます。

例: `https://investment-tracker.streamlit.app`

## デプロイ後の確認

### 1. アプリにアクセス

生成されたURLにアクセスして、ログイン画面が表示されることを確認

### 2. ログインテスト

設定したパスワードでログインできることを確認

### 3. 機能テスト

- [ ] 仮説登録
- [ ] 詳細表示
- [ ] アルファ計算
- [ ] KPIチェック
- [ ] ログアウト

## iPhone対応

### Safariでアクセス

```
https://your-app.streamlit.app
```

### ホーム画面に追加

1. 共有ボタン → ホーム画面に追加
2. アイコンをタップして起動
3. PWA（Progressive Web App）として動作

## トラブルシューティング

### デプロイエラー: "No module named 'src'"

**原因**: インポートパスが正しくない

**対処法**:
Streamlit Cloudでは `apps/investment-tracker/` がルートディレクトリになるため、インポートパスは正しく設定されています。エラーが出る場合は、以下を確認：

```bash
# apps/investment-tracker/ に __init__.py があるか確認
ls apps/investment-tracker/src/__init__.py
```

### APIキーエラー

**原因**: Secretsが設定されていない

**対処法**:
1. Streamlit Cloud管理画面 → アプリ設定 → Secrets
2. `JQUANTS_API_KEY` と `APP_PASSWORD` を設定
3. 「Save」後、アプリを再起動

### パスワードエラー

**原因**: Secretsの`APP_PASSWORD`が設定されていない

**対処法**:
Secretsに以下を追加：
```toml
APP_PASSWORD = "your_password"
```

### データが保存されない

**注意**: Streamlit Cloudは再起動時にデータが消えます。

**対処法**:
永続化が必要な場合は、以下を検討：
- Google Sheets API（無料）
- Firebase Realtime Database（無料枠あり）
- PostgreSQL（Streamlit Cloudと連携可能）

## セキュリティ注意事項

### 公開アプリの注意点

- Streamlit Cloudにデプロイしたアプリはインターネットからアクセス可能
- パスワード認証はあるが、簡易的なもの
- 機密性の高いデータは保存しない

### Secretsの管理

- `secrets.toml` は絶対にGitにコミットしない（.gitignoreで除外済み）
- Streamlit CloudのSecretsは暗号化されて保存される
- パスワードは定期的に変更する

## コスト

- Streamlit Cloud無料プラン:
  - 1アプリまで無料
  - 月間リソース制限あり
  - プライベートリポジトリ対応

## 更新方法

コードを修正してGitHubにpushすると、自動的に再デプロイされます。

```bash
git add apps/investment-tracker/
git commit -m "Update app"
git push origin main
```

数分後、Streamlit Cloudが自動で更新を検知して再デプロイします。

## 参考リンク

- Streamlit Cloud公式ドキュメント: https://docs.streamlit.io/streamlit-community-cloud
- Secrets管理: https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management
