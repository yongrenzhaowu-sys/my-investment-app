# クイックスタートガイド

## 初回セットアップ（1回のみ）

### 1. secrets.tomlを作成

```powershell
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
notepad .streamlit/secrets.toml
```

### 2. APIキーとパスワードを設定

`secrets.toml` を編集：

```toml
JQUANTS_API_KEY = "あなたのAPIキー"
APP_PASSWORD = "あなたのパスワード"
```

保存して閉じる。

## アプリ起動

### Windows PowerShellで実行

```powershell
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
streamlit run app.py
```

### ログイン

1. ブラウザで自動的に開く（開かない場合は `http://localhost:8501`）
2. 設定したパスワード（`APP_PASSWORD`）を入力
3. 「ログイン」ボタンをクリック

## iPhoneからアクセス

### 1. PCのIPアドレスを確認

```powershell
ipconfig
```

`IPv4 アドレス` をメモ（例: `192.168.1.100`）

### 2. iPhoneのブラウザでアクセス

```
http://192.168.1.100:8501
```

### 3. ログイン

同じパスワードでログイン

### 4. ホーム画面に追加（推奨）

Safari で:
1. 共有ボタン → ホーム画面に追加
2. アイコンをタップして起動

## 使い方

### 仮説登録

1. サイドバーの「仮説登録」フォームに入力
   - 銘柄コード（5桁、例: 72030）
   - 購入日、購入価格
   - 購入理由
   - 撤退KPI（営業利益率の閾値）
2. 「登録」ボタンをクリック

### 銘柄詳細表示

1. 一覧から銘柄を展開
2. 「詳細を見る」ボタンをクリック
3. パフォーマンス指標、アルファ推移グラフ、KPIチェック結果を確認

### ログアウト

サイドバー下部の「ログアウト」ボタンをクリック

## トラブルシューティング

### ログインできない

- パスワードを確認（`secrets.toml` の `APP_PASSWORD`）
- 英数字のみ推奨（記号は避ける）

### APIエラー

- `secrets.toml` の `JQUANTS_API_KEY` を確認
- J-Quantsの管理画面でAPIキーが有効か確認

### ポート8501が使用中

別のポートで起動:
```powershell
streamlit run app.py --server.port 8502
```

## 停止方法

PowerShellで `Ctrl+C` を押す
