# 投資判断支援アプリ

J-Quants API（スタンダードプラン）を活用した、iPhone対応の投資判断支援アプリです。

## 機能

### 📋 仮説登録
- 銘柄コード、購入日、購入価格、購入理由を入力
- 撤退KPI（営業利益率の閾値）を設定
- **データ永続化**: Google Sheets対応（Streamlit Cloud）/ JSONファイル（ローカル）

### 📊 実力可視化（アルファ）
- 個別銘柄の騰落率を計算（購入時からの変化）
- S&P500との比較でアルファを算出
- 時系列グラフで推移を可視化

### 🎯 自動進捗チェック
- J-Quants財務データAPIで最新決算を取得
- 営業利益率を自動計算
- 撤退KPIを下回った場合は警告表示

### 📱 モバイル最適化
- iPhoneの縦画面に最適化されたレイアウト
- タップしやすいボタンデザイン

## セットアップ

### 1. Streamlit Secretsの設定

```bash
cd apps/investment-tracker

# secrets.toml.exampleからコピー
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# エディタで編集（APIキーとパスワードを設定）
notepad .streamlit/secrets.toml
```

詳細は [SETUP.md](SETUP.md) を参照してください。

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 3. アプリの起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が自動的に開きます。

### 4. ログイン

設定したパスワード（`APP_PASSWORD`）を入力してログインします。

## 使い方

### 仮説の登録

1. サイドバーの「仮説登録」フォームに入力
   - 銘柄コード（5桁、例: 72030）
   - 購入日
   - 購入価格
   - 購入理由（中計の注目点など）
   - 撤退KPI（営業利益率の閾値）

2. 「登録」ボタンをクリック

### 銘柄の詳細表示

1. 一覧から銘柄の展開ボタンをクリック
2. 「詳細を見る」ボタンをクリック
3. パフォーマンス、アルファ推移、KPIチェック結果を確認

### 仮説の削除

詳細画面の下部にある「この仮説を削除」ボタンをクリック

## データ保存

仮説データは `data/hypotheses.json` に保存されます。
このファイルは `.gitignore` に含まれているため、リポジトリにコミットされません。

## iPhone対応

### ホーム画面に追加

1. Safariでアプリにアクセス
2. 共有ボタン → ホーム画面に追加
3. アイコンをタップして起動

### ローカルネットワークでアクセス

PCでアプリを起動後、iPhoneから以下のURLにアクセス：

```
http://<PCのIPアドレス>:8501
```

## トラブルシューティング

### 認証エラー

環境変数 `JQUANTS_API_KEY` が設定されているか確認：

```powershell
[System.Environment]::GetEnvironmentVariable('JQUANTS_API_KEY', 'User')
```

### データ取得エラー

- J-Quants APIの月間リクエスト制限を確認
- 銘柄コードが正しいか確認（5桁、例: 72030）

## ライセンス

このプロジェクトは個人利用を目的としています。
