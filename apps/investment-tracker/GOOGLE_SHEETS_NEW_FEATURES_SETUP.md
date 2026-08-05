# 新機能のGoogle Sheets連携設定手順

## 概要

オプション取引と追加投資の記録をGoogle Sheetsで管理できるようにする設定手順です。

**前提条件**: 既に基本的なGoogle Sheets連携が完了していること（`SIMPLE_GSHEETS_SETUP.md`参照）

---

## ステップ1: AdditionalInvestmentsシートを作成

### 1-1. スプレッドシートを開く

既存のスプレッドシート（保有銘柄を管理しているもの）を開きます。

### 1-2. 新しいシートを作成

1. 左下の「**+**」をクリック
2. シート名を「**AdditionalInvestments**」に変更

### 1-3. ヘッダー行を追加

1行目（A1セル）から以下の列名を入力：

```
date	amount
```

**簡単な方法**: 上記をコピーして、A1セルに貼り付け（タブ区切り）

**列の説明**:
- `date`: 追加投資日（YYYY-MM-DD形式）
- `amount`: 追加投資額（円）

---

## ステップ2: OptionTradesシートを作成

### 2-1. 新しいシートを作成

1. 左下の「**+**」をクリック
2. シート名を「**OptionTrades**」に変更

### 2-2. ヘッダー行を追加

1行目（A1セル）から以下の列名を入力：

```
id	date	description	profit	created_at
```

**簡単な方法**: 上記をコピーして、A1セルに貼り付け（タブ区切り）

**列の説明**:
- `id`: 取引ID（UUID）
- `date`: 取引日（YYYY-MM-DD形式）
- `description`: 取引内容（例: プットオプション売却）
- `profit`: 損益（円、利益はプラス、損失はマイナス）
- `created_at`: 記録日時（ISO 8601形式）

---

## ステップ3: AdditionalInvestmentsシートをCSVとして公開

### 3-1. 公開設定

1. **AdditionalInvestmentsシートを選択**（重要）
2. **ファイル → 共有 → ウェブに公開**
3. **「リンク」タブを選択**
4. **公開するシート**: 「**AdditionalInvestments**」を選択
5. **形式**: 「**カンマ区切りの値（.csv）**」を選択
6. **公開**をクリック

### 3-2. URLをコピー

表示されるURLをコピーしてください。

例: `https://docs.google.com/spreadsheets/d/e/2PACX-1vS.../pub?gid=XXXXXX&single=true&output=csv`

このURLが `ADDITIONAL_INVESTMENTS_READ_URL` になります。

---

## ステップ4: OptionTradesシートをCSVとして公開

### 4-1. 公開設定

1. **OptionTradesシートを選択**（重要）
2. **ファイル → 共有 → ウェブに公開**
3. **「リンク」タブを選択**
4. **公開するシート**: 「**OptionTrades**」を選択
5. **形式**: 「**カンマ区切りの値（.csv）**」を選択
6. **公開**をクリック

### 4-2. URLをコピー

表示されるURLをコピーしてください。

例: `https://docs.google.com/spreadsheets/d/e/2PACX-1vS.../pub?gid=YYYYYY&single=true&output=csv`

このURLが `OPTION_TRADES_READ_URL` になります。

---

## ステップ5: secrets.tomlに追加

### 5-1. ファイルを開く

`.streamlit/secrets.toml` を開きます。

### 5-2. URLを追加

以下の行を追加します：

```toml
# 追加投資シート（AdditionalInvestments）のCSV公開URL
ADDITIONAL_INVESTMENTS_READ_URL = "ここにAdditionalInvestmentsシートのURLを貼り付け"

# オプション取引シート（OptionTrades）のCSV公開URL
OPTION_TRADES_READ_URL = "ここにOptionTradesシートのURLを貼り付け"
```

**例**:
```toml
ADDITIONAL_INVESTMENTS_READ_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS.../pub?gid=123456&single=true&output=csv"
OPTION_TRADES_READ_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS.../pub?gid=789012&single=true&output=csv"
```

---

## ステップ6: Google Apps Scriptを更新

### 6-1. スクリプトエディタを開く

1. スプレッドシートで **拡張機能 → Apps Script**
2. 既存のスクリプトが表示されます

### 6-2. スクリプトを更新

既存のコードを、**`google_apps_script_latest.js`** の内容に**置き換え**てください。

**重要な変更点**:
- `doPost` 関数に `save_additional_investments` アクションを追加
- `doPost` 関数に `save_option_trades` アクションを追加
- `saveAdditionalInvestments` 関数を追加
- `saveOptionTrades` 関数を追加

### 6-3. 保存してデプロイ

1. **保存**アイコンをクリック
2. **デプロイ → デプロイを管理**
3. 既存のデプロイの右側にある **鉛筆アイコン（編集）** をクリック
4. **バージョン**: 「新しいバージョン」を選択
5. **説明**: 「オプション取引と追加投資機能を追加」
6. **デプロイ**をクリック

**注意**: 初めてデプロイする場合は、**デプロイ → 新しいデプロイ**を選択してください。

---

## ステップ7: アプリを再起動（ローカル開発時）

### 7-1. Streamlitを再起動

```powershell
# Ctrl+C で停止
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
streamlit run app.py
```

### 7-2. ブラウザでハードリロード

- **Ctrl+Shift+R**

---

## ステップ8: Streamlit Cloudの設定（本番環境）

### 8-1. Streamlit CloudのSecretsを更新

1. Streamlit Cloudのダッシュボードを開く
2. アプリの **Settings → Secrets** を開く
3. 以下を追加：

```toml
ADDITIONAL_INVESTMENTS_READ_URL = "（ステップ3で取得したURL）"
OPTION_TRADES_READ_URL = "（ステップ4で取得したURL）"
```

4. **Save**をクリック
5. アプリが自動的に再起動されます

---

## 確認方法

### 1. 追加投資機能の確認

1. アプリのサイドバーで「追加資金の入金記録」から追加投資を記録
2. 「資産推移分析」画面で表示されることを確認
3. Google SheetsのAdditionalInvestmentsシートを開き、データが追加されていることを確認

### 2. オプション取引機能の確認

1. アプリのサイドバーで「オプション取引記録」から取引を記録
2. メニューから「オプション取引」を選択し、表示されることを確認
3. Google SheetsのOptionTradesシートを開き、データが追加されていることを確認

---

## トラブルシューティング

### URLが見つからないエラー

**症状**:
- `追加資金のURL（ADDITIONAL_INVESTMENTS_READ_URL）が設定されていません`
- `オプション取引のURL（OPTION_TRADES_READ_URL）が設定されていません`

**解決策**:
- `secrets.toml` に正しいURLが設定されているか確認
- URLの末尾が `output=csv` になっているか確認

### データが保存されない

**症状**: 記録処理は成功するが、Google Sheetsに反映されない

**解決策**:
1. Google Apps Scriptが正しく更新されているか確認
2. デプロイが最新バージョンになっているか確認
3. `SPREADSHEET_WRITE_URL` が正しく設定されているか確認
4. ブラウザの開発者ツールでエラーメッセージを確認

### 古いデータが表示される

**症状**: ローカルの古いデータが表示される

**解決策**:
1. `USE_GSHEETS = true` になっているか確認
2. アプリを完全に再起動
3. ブラウザのキャッシュをクリア（Ctrl+Shift+Delete）
4. ハードリロード（Ctrl+Shift+R）

---

## データの動作仕様

### データの保存順序

1. **ローカルJSON**: まずローカルに保存（即座にバックアップ）
2. **Google Sheets**: 次にクラウドに保存（同期）

### データの読み込み順序

1. **Google Sheets**: まずクラウドから読み込み（優先）
2. **ローカルJSON**: Google Sheetsが失敗した場合のフォールバック

### オフライン動作

- Google Sheetsが利用できない場合、自動的にローカルJSONを使用
- オンラインに戻ったら、手動でGoogle Sheetsに同期する必要があります

---

## セキュリティに関する注意

### 公開設定について

- シートは「ウェブに公開」設定になりますが、URLを知らなければアクセスできません
- アプリ側で `APP_PASSWORD` による認証があります
- 個人の投資記録は公開されても実害が少ないデータです

### より安全にしたい場合

- Googleアカウントでログイン機能を追加（OAuth）
- Google Cloud Platformのサービスアカウント認証を使用
- データを暗号化して保存

---

## 完了

これで、オプション取引と追加投資の記録がGoogle Sheetsで管理できるようになりました。
