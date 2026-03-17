# 次回セッション開始ガイド（2026-03-18）

**前回完了日**: 2026-03-17
**前回の作業**: 売買履歴のGoogle Sheets連携設定

---

## ✅ 前回完了した作業

### 1. 余力計算の修正
- 累計売却額の二重計算を修正
- 正しい計算式に変更

### 2. 投資成績表示の改善
- わかりやすい成績サマリー表示に変更
- 総資産、損益、損益率が一目でわかる

### 3. Google Sheets連携（売買履歴）
- コード実装完了
- secrets.toml設定完了
- Google Apps Script更新完了

---

## 🔍 次回最初に確認すること

### 1. アプリを起動

```powershell
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
streamlit run app.py
```

### 2. 売買履歴のGoogle Sheets連携を確認

#### テスト手順
1. **適当な銘柄を売却**してみる
2. **「📜 売買履歴」画面**で表示されることを確認
3. **Google SheetsのTradingHistoryシート**を開いて、データが保存されているか確認

#### 期待される結果
- ✅ 売却処理が成功する
- ✅ 売買履歴画面に表示される
- ✅ Google SheetsのTradingHistoryシートにデータが保存される

#### もし動作しない場合
1. **ターミナルのエラーメッセージ**を確認
2. **secrets.tomlの設定**を確認
   - `TRADING_HISTORY_READ_URL` が正しく設定されているか
   - URLがダブルクォーテーションで囲まれているか
3. **Google Apps Script**が正しく更新されているか確認
4. **デプロイURL**が `SPREADSHEET_WRITE_URL` に設定されているか確認

---

## 📚 関連ドキュメント

### セッション記録
- `docs/sessions/20260317_fix_cash_after_sell.md` - 余力計算の修正
- `docs/sessions/20260317_investment_performance_display.md` - 投資成績表示の改善

### 設定手順
- `apps/investment-tracker/GOOGLE_SHEETS_TRADING_HISTORY_SETUP.md` - 詳細な設定手順

### コード
- `apps/investment-tracker/google_apps_script_updated.js` - Google Apps Scriptコード
- `src/simple_gsheets_client.py` - Google Sheets連携クライアント
- `src/trading_history.py` - 売買履歴管理（Google Sheets対応）
- `src/profit_calculator.py` - 余力計算（修正済み）

---

## 🎯 今後の改善候補

### 優先度: 高
- [ ] 売買履歴のGoogle Sheets連携の動作確認
- [ ] 既存のローカルデータ（もしあれば）をGoogle Sheetsに移行

### 優先度: 中
- [ ] グラフ表示（総資産の推移）
- [ ] ベンチマーク比較（S&P500など）
- [ ] 目標設定機能

### 優先度: 低
- [ ] デバッグログの削除（profit_calculator.pyのprintデバッグ文）
- [ ] モジュール強制リロードコードの削除（本番環境では不要）

---

## 🔧 トラブルシューティング

### 問題: 売買履歴がGoogle Sheetsに保存されない

**確認事項**:
1. `USE_GSHEETS = true` になっているか
2. `TRADING_HISTORY_READ_URL` が設定されているか
3. Google Apps Scriptが更新されているか
4. デプロイが更新されているか

**解決策**:
- ターミナルのエラーメッセージを確認
- `GOOGLE_SHEETS_TRADING_HISTORY_SETUP.md` を参照

### 問題: 累計売却額がマイナス値

**原因**: 古いコードがキャッシュされている

**解決策**:
1. アプリを完全に停止（Ctrl+C）
2. ターミナルを閉じる
3. 新しいターミナルで起動

### 問題: 保有銘柄が表示されない

**原因**: データソースの不一致

**解決策**:
1. `USE_GSHEETS = true` になっているか確認
2. Google SheetsのURL（SPREADSHEET_READ_URL）が正しいか確認

---

## 📊 現在の設定状況

### データソース
- **保有銘柄**: Google Sheets（13銘柄）
- **売買履歴**: Google Sheets（設定完了、動作未確認）
- **初期資金**: 6,711,800円

### 計算式
- **総資産** = 保有証券 + 現金
- **損益** = 総資産 - 初期資金
- **余力** = 初期資金 - 現在保有額 - 売却済み購入額 + 累計売却額

---

## 🚀 次回の作業開始

1. **アプリを起動**
2. **売買履歴のGoogle Sheets連携を確認**（テスト売却）
3. **問題があれば修正**
4. **問題なければ、次の機能改善へ**

---

**次回も頑張りましょう！** 🎯
