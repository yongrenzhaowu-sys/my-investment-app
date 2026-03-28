# Streamlit Cloud セットアップ手順

## 📋 必須設定：Secrets

Streamlit Cloudでアプリを動作させるには、以下のSecretsを設定する必要があります。

### 設定方法

1. **Streamlit Cloudにログイン**
   - https://share.streamlit.io/ にアクセス

2. **アプリを選択**
   - デプロイ済みのアプリを選択

3. **Settings → Secrets を開く**
   - 右上の「⚙️ Settings」→「Secrets」タブ

4. **以下のSecretsを追加**

```toml
# アプリのパスワード（ログイン用）
APP_PASSWORD = "your-secure-password"

# 初期資金（円）
initial_capital = 6711800

# J-Quants API認証情報
JQUANTS_REFRESH_TOKEN = "your-jquants-refresh-token"
JQUANTS_MAIL_ADDRESS = "your-email@example.com"

# Google Sheets統合（オプション）
USE_GSHEETS = true
GSHEETS_CSV_URL = "https://docs.google.com/spreadsheets/d/.../export?format=csv"
GSHEETS_APPS_SCRIPT_URL = "https://script.google.com/macros/s/.../exec"
```

5. **Save** をクリック

6. **アプリを再起動**
   - Streamlit Cloudが自動的にアプリを再起動します
   - 数秒〜数十秒で新しい設定が反映されます

---

## 🔐 Secretsの値の説明

### APP_PASSWORD
- アプリのログインパスワード
- 推奨：12文字以上の英数字＋記号

### initial_capital
- 投資の初期資金（円）
- 数値のみ（カンマ不要）
- 例：`6711800`（6,711,800円）

### JQUANTS_REFRESH_TOKEN
- J-Quants APIのリフレッシュトークン
- 取得方法：https://jpx.cloud/jquants/

### JQUANTS_MAIL_ADDRESS
- J-Quantsに登録したメールアドレス

### USE_GSHEETS（オプション）
- Google Sheets統合を使用する場合：`true`
- 使用しない場合：`false`

### GSHEETS_CSV_URL（オプション）
- Google SheetsのCSV公開URL
- Google Sheetsの「ファイル」→「共有」→「ウェブに公開」→「CSV形式」で取得

### GSHEETS_APPS_SCRIPT_URL（オプション）
- Google Apps ScriptのWebアプリURL
- Apps Scriptをデプロイして取得

---

## 💡 初期資金を変更する方法

### ローカル環境
1. アプリ内の「📊 損益サマリー」→「⚙️ 初期資金設定」から変更
2. 「更新」ボタンをクリック
3. `data/settings.json` に保存されます

### Streamlit Cloud
1. **Streamlit Cloud Settings → Secrets** を開く
2. `initial_capital` の値を変更
3. **Save** をクリック
4. アプリが自動的に再起動され、新しい値が反映されます

**注意**：Streamlit Cloudでは、アプリ内のUIから初期資金を変更できません。必ずSecretsから変更してください。

---

## 🧪 動作確認

1. **ログイン**
   - 設定した`APP_PASSWORD`でログイン

2. **損益サマリー確認**
   - 「📊 損益サマリー」を開く
   - 「⚙️ 初期資金設定」を展開
   - 設定した`initial_capital`が表示されることを確認

3. **J-Quants API動作確認**
   - 仮説を登録してみる
   - 銘柄情報が取得できることを確認

---

## 🚨 トラブルシューティング

### エラー：「APP_PASSWORD が設定されていません」
→ Secretsに`APP_PASSWORD`を追加してください

### エラー：「認証エラー」（J-Quants）
→ `JQUANTS_REFRESH_TOKEN`と`JQUANTS_MAIL_ADDRESS`が正しいか確認してください

### 初期資金が1,000,000円のまま
→ Secretsに`initial_capital`を追加してください（数値のみ、カンマ不要）

### Google Sheets統合が動作しない
→ `USE_GSHEETS = true`、`GSHEETS_CSV_URL`、`GSHEETS_APPS_SCRIPT_URL`をすべて設定してください

---

## 📚 参考リンク

- [Streamlit Secrets管理](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management)
- [J-Quants API](https://jpx.cloud/jquants/)
- [Google Sheets API](https://developers.google.com/sheets/api)
