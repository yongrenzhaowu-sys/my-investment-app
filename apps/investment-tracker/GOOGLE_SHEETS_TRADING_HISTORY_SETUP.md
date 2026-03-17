# 売買履歴のGoogle Sheets連携設定手順

## 📋 概要

売買履歴をGoogle Sheetsで管理できるようにする設定手順です。

---

## ステップ1: TradingHistoryシートを作成

### 1-1. スプレッドシートを開く

既存のスプレッドシート（保有銘柄を管理しているもの）を開きます。

### 1-2. 新しいシートを作成

1. 左下の「**+**」をクリック
2. シート名を「**TradingHistory**」に変更

### 1-3. ヘッダー行を追加

1行目（A1セル）から以下の列名を入力：

```
id
code
name
purchase_date
purchase_price
shares
purchase_reason
sell_date
sell_price
sell_reason
realized_profit
realized_profit_rate
holding_days
tax_amount
after_tax_profit
original_hypothesis_id
created_at
sold_at
kpi_threshold
is_nisa
```

**簡単な方法**: 以下をコピーして、A1セルに貼り付け（タブ区切り）

```
id	code	name	purchase_date	purchase_price	shares	purchase_reason	sell_date	sell_price	sell_reason	realized_profit	realized_profit_rate	holding_days	tax_amount	after_tax_profit	original_hypothesis_id	created_at	sold_at	kpi_threshold	is_nisa
```

---

## ステップ2: TradingHistoryシートをCSVとして公開

### 2-1. 公開設定

1. **TradingHistoryシートを選択**（重要！）
2. **ファイル → 共有 → ウェブに公開**
3. **「リンク」タブを選択**
4. **公開するシート**: 「**TradingHistory**」を選択
5. **形式**: 「**カンマ区切りの値（.csv）**」を選択
6. **公開**をクリック

### 2-2. URLをコピー

表示されるURLをコピーしてください。

例: `https://docs.google.com/spreadsheets/d/e/2PACX-1vS.../pub?gid=123456&single=true&output=csv`

---

## ステップ3: secrets.tomlに追加

### 3-1. ファイルを開く

`.streamlit/secrets.toml` を開きます。

### 3-2. URLを追加

以下の行を見つけて、コピーしたURLを貼り付けます：

```toml
# 売買履歴シート（TradingHistory）のCSV公開URL
TRADING_HISTORY_READ_URL = "ここに貼り付け"
```

**例**:
```toml
TRADING_HISTORY_READ_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS.../pub?gid=123456&single=true&output=csv"
```

---

## ステップ4: Google Apps Scriptを更新

### 4-1. スクリプトエディタを開く

1. スプレッドシートで **拡張機能 → Apps Script**
2. 既存のスクリプトが表示されます

### 4-2. スクリプトを更新

既存のコードを、`google_apps_script_updated.js` の内容に**置き換え**てください。

**重要な変更点**:
- `doPost` 関数に `save_trading_history` アクションを追加
- `saveTradingHistory` 関数を追加

### 4-3. 保存してデプロイ

1. **保存**アイコンをクリック
2. **デプロイ → 新しいデプロイ**
3. **種類**: ウェブアプリ
4. **アクセスできるユーザー**: 全員
5. **デプロイ**をクリック

**注意**: 既にデプロイ済みの場合は、**デプロイを管理 → 編集**で更新してください。

---

## ステップ5: アプリを再起動

### 5-1. Streamlitを再起動

```powershell
# Ctrl+C で停止
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
streamlit run app.py
```

### 5-2. ブラウザでハードリロード

- **Ctrl+Shift+R**

---

## ✅ 確認方法

### 1. 売却処理を実行

1. 適当な銘柄を売却してみる
2. 「売買履歴」画面で表示されることを確認

### 2. Google Sheetsを確認

1. TradingHistoryシートを開く
2. 売却データが追加されていることを確認

---

## 🔧 トラブルシューティング

### URLが見つからないエラー

**症状**: `TRADING_HISTORY_READ_URL が設定されていません`

**解決策**: `secrets.toml` に正しいURLが設定されているか確認

### データが保存されない

**症状**: 売却処理は成功するが、Google Sheetsに反映されない

**解決策**:
1. Google Apps Scriptが正しく更新されているか確認
2. デプロイURLが `secrets.toml` の `SPREADSHEET_WRITE_URL` に設定されているか確認
3. ターミナルにエラーメッセージが表示されていないか確認

### 古いデータが表示される

**症状**: ローカルの古いデータが表示される

**解決策**:
1. `USE_GSHEETS = true` になっているか確認
2. アプリを完全に再起動
3. ブラウザでハードリロード（Ctrl+Shift+R）

---

## 📝 備考

- **ローカルバックアップ**: Google Sheetsに保存すると同時に、ローカルJSONにもバックアップされます
- **オフライン**: Google Sheetsが使えない場合、自動的にローカルJSONにフォールバックします
- **データ移行**: 既存のローカルデータは手動でGoogle Sheetsに移行する必要があります

---

## 🎯 完了

これで、売買履歴がGoogle Sheetsで管理できるようになりました！
