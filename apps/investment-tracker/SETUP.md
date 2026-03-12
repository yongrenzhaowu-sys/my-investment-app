# セットアップガイド

## 1. Streamlit Secretsの設定

### secrets.tomlファイルを作成

```bash
cd apps/investment-tracker
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

### secrets.tomlを編集

`.streamlit/secrets.toml` を開いて、以下の値を実際の値に置き換えてください：

```toml
# J-Quants API V2 APIキー
JQUANTS_API_KEY = "あなたのAPIキーをここに入力"

# アプリログイン用パスワード
APP_PASSWORD = "あなたの好きなパスワードをここに入力"
```

**重要**:
- `secrets.toml` は `.gitignore` に含まれているため、Gitにコミットされません
- パスワードは英数字を推奨（記号は避ける）

## 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

## 3. アプリの起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が自動的に開きます。

## 4. ログイン

設定したパスワード（`APP_PASSWORD`）を入力してログインします。

## トラブルシューティング

### secrets.toml が見つからない

エラーメッセージ: `APP_PASSWORD が設定されていません`

**対処法**:
```bash
# secrets.toml.exampleからコピー
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# エディタで開いて編集
notepad .streamlit/secrets.toml
```

### APIキーが無効

エラーメッセージ: `APIキーの形式が不正です`

**対処法**:
- J-Quants の管理画面でAPIキーを確認
- コピー時に余分なスペースが入っていないか確認
- APIキーは20文字以上必要

### Windows環境変数を使いたい場合

Streamlit Secretsの代わりに、Windows環境変数でも動作します：

```powershell
[System.Environment]::SetEnvironmentVariable('JQUANTS_API_KEY', 'your_api_key', 'User')
```

この場合、`secrets.toml` の `JQUANTS_API_KEY` は不要です。
ただし、`APP_PASSWORD` は `secrets.toml` に必須です。

## iPhone対応

### ローカルネットワークでアクセス

1. PCのIPアドレスを確認:
   ```powershell
   ipconfig
   ```

2. iPhoneのブラウザで:
   ```
   http://<PCのIPアドレス>:8501
   ```

### ホーム画面に追加（PWA化）

1. Safariでアプリにアクセス
2. 共有ボタン → ホーム画面に追加
3. アイコンをタップして起動

## セキュリティ注意事項

- `secrets.toml` は絶対に公開しないでください
- `APP_PASSWORD` は定期的に変更することを推奨
- 公開ネットワークでアプリを起動しないでください
