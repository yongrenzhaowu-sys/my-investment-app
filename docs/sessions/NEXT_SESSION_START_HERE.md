# 次回セッション開始ガイド

**前回セッション**: 2026-03-11 15:10 （投資判断支援アプリ完全実装）
**次回タスク**: デプロイ準備 → GitHubにpush → Streamlit Cloudデプロイ

---

## 📍 現在の状態

### ✅ 完成したもの

- **投資判断支援アプリ**（`apps/investment-tracker/`）
  - ログイン機能（パスワード認証）✅
  - 仮説登録（銘柄コード、購入日、購入価格、理由、撤退KPI）✅
  - アルファ計算（個別 vs S&P500）✅ **+15.98%**
  - グラフ表示（Plotly）✅
  - **KPIチェック（営業利益率）✅ 10.05%**
  - 削除機能（一覧・詳細画面）✅
  - Google Sheets統合（シンプル版）✅
  - **J-Quants API V2完全対応**✅

### 🔧 動作確認済み
- ローカルテスト成功（2026-03-11 15:05）
- テスト銘柄: 72030（トヨタ自動車）
- すべての機能が正常動作

---

## 🚀 次回タスク（優先順位順）

### タスク1: デプロイ準備（10分）

#### 1-1. デバッグログを削除

不要なデバッグログを削除します：

**ファイル**: `apps/investment-tracker/src/api.py`

削除する行：
```python
print(f"[DEBUG] レスポンスのキー: ...")
print(f"[DEBUG] data: X件")
print(f"[DEBUG] 列名: ...")
# など、すべての print("[DEBUG] ...") を削除
```

#### 1-2. Streamlit警告を修正

**ファイル**: `apps/investment-tracker/app.py`

修正箇所：
```python
# ❌ 修正前
st.button("text", use_container_width=True)

# ✅ 修正後
st.button("text", width="stretch")
```

該当箇所（検索: `use_container_width`）:
- 116行目: ログインボタン
- 155行目: 登録ボタン
- 197行目: ログアウトボタン
- 226行目: 詳細ボタン
- 232行目: 削除ボタン
- 243行目: 戻るボタン
- 319行目: 削除ボタン（詳細画面）

#### 1-3. .gitignore確認

以下が含まれているか確認：
```
apps/investment-tracker/.streamlit/secrets.toml
apps/investment-tracker/data/hypotheses.json
```

→ 既に含まれています（確認済み）✅

---

### タスク2: GitHubにpush（5分）

```bash
cd "C:\Users\yongr\claude project\workspace"

# ステータス確認
git status

# ステージング
git add apps/investment-tracker/
git add docs/sessions/20260311_1800_app_complete.md
git add docs/knowledges/20260311_1800_jquants_api_v2_complete.md
git add docs/sessions/NEXT_SESSION_START_HERE.md

# コミット
git commit -m "$(cat <<'EOF'
Add investment tracker app with J-Quants API V2 integration

Features:
- Login authentication
- Hypothesis registration (stock code, date, price, reason, exit KPI)
- Alpha calculation (stock vs S&P500)
- KPI auto-check (operating margin from J-Quants API V2)
- Google Sheets integration (simple version)
- Mobile-optimized UI

Technical highlights:
- J-Quants API V2 complete support
- Fixed endpoint names (/fins/summary, /equities/bars/daily)
- Type conversion for financial data (str to numeric)
- Error handling for missing data

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"

# プッシュ
git push origin main
```

---

### タスク3: Streamlit Cloudデプロイ（10分）

#### 3-1. Streamlit Cloudにログイン

https://streamlit.io/cloud にアクセス

#### 3-2. 新しいアプリ作成

1. 「New app」をクリック
2. 設定：
   - **Repository**: あなたのGitHubリポジトリを選択
   - **Branch**: `main`
   - **Main file path**: `apps/investment-tracker/app.py`
3. 「Advanced settings」をクリック

#### 3-3. Secretsを設定

以下をコピー＆ペースト：

```toml
# J-Quants API
JQUANTS_API_KEY = "あなたのAPIキー"

# アプリログイン用パスワード
APP_PASSWORD = "あなたのパスワード"

# Google Sheetsを使用
USE_GSHEETS = true

# Google Sheets URL
SPREADSHEET_READ_URL = "ステップ2で取得したCSV公開URL"
SPREADSHEET_WRITE_URL = "ステップ3で取得したApps Script URL"
```

**注意**:
- `JQUANTS_API_KEY`: PowerShellで確認 `[System.Environment]::GetEnvironmentVariable('JQUANTS_API_KEY', 'User')`
- `APP_PASSWORD`: ローカルの `.streamlit/secrets.toml` と同じもの
- Google Sheets URLは前回セットアップしたもの

#### 3-4. デプロイ開始

1. 「Deploy!」をクリック
2. ビルド完了まで待つ（約3〜5分）
3. URLが表示されたらアクセス

#### 3-5. 動作確認

- [ ] ログイン成功
- [ ] 仮説登録（銘柄コード: 72030）
- [ ] 詳細表示（アルファ、グラフ、KPI）
- [ ] Google Sheetsでデータ確認

---

### タスク4: iPhone実機テスト（5分）

#### 4-1. ローカルテスト（オプション）

1. PCのIPアドレス確認:
   ```powershell
   ipconfig
   ```
   → IPv4アドレスをメモ（例: `192.168.11.28`）

2. iPhoneで `http://192.168.11.28:8501` にアクセス
3. レイアウト確認

#### 4-2. Streamlit Cloud テスト

1. iPhoneでStreamlit CloudのURLにアクセス
2. ログイン
3. レイアウト確認
4. Safari → 共有 → ホーム画面に追加

---

## 📋 機能拡張計画（次回以降）

ユーザーからの要望：

### 機能1: 売買履歴管理

**目的**: 利益確定/損失確定時の理由を記録

**実装内容**:
- 売却機能追加（売却日、売却価格、売却理由）
- `trading_history.json` 新規作成
- 保持中の銘柄（`hypotheses.json`）とは別管理

**データ構造**:
```json
{
  "id": "uuid",
  "code": "72030",
  "name": "トヨタ自動車",
  "purchase_date": "2026-03-09",
  "purchase_price": 3000,
  "sell_date": "2026-03-15",
  "sell_price": 3500,
  "sell_reason": "目標価格到達",
  "realized_profit": 500,
  "holding_days": 6,
  "purchase_reason": "元の購入理由",
  "original_hypothesis_id": "uuid"
}
```

### 機能2: 損益サマリー画面

**表示項目**:
1. **実現損益（損益通算）**
   - 売却済み銘柄の損益合計
   - 税金考慮（譲渡所得税 約20.315%）
   - 税引き後利益

2. **含み損益**
   - 保持中銘柄の現在価値 - 購入価格
   - 銘柄別の含み損益

3. **合計損益**
   - 実現損益 + 含み損益

4. **年間損益（損益通算用）**
   - 年ごとの実現損益
   - 確定申告用データ

### 機能3: 余力表示

**計算式**:
```
余力 = 初期資金 + Σ(売却額 - 購入額) - Σ(税金) - Σ(現在保有額)

税金 = (売却益 > 0) ? 売却益 * 0.20315 : 0
```

**表示項目**:
- 現在の余力（投資可能額）
- 初期資金
- 累計売却額
- 累計税金
- 現在保有額

---

## 📚 参考ドキュメント

### セットアップ
- `apps/investment-tracker/SIMPLE_GSHEETS_SETUP.md` - Google Sheets設定（10分）
- `apps/investment-tracker/QUICKSTART.md` - クイックスタート
- `apps/investment-tracker/SETUP.md` - 詳細セットアップ

### デプロイ
- `apps/investment-tracker/DEPLOY.md` - Streamlit Cloudデプロイ手順

### 開発
- `apps/investment-tracker/README.md` - 概要
- `apps/investment-tracker/google-apps-script/Code.gs` - Apps Scriptコード

### セッション記録
- `docs/sessions/20260311_1800_app_complete.md` - 前回の完全記録

### ナレッジベース
- `docs/knowledges/20260311_1800_jquants_api_v2_complete.md` - V2 API完全ガイド

---

## 🔧 トラブルシューティング

### secrets.tomlが見つからない
```bash
cp apps/investment-tracker/.streamlit/secrets.toml.example apps/investment-tracker/.streamlit/secrets.toml
```

### APIキーがわからない
```powershell
[System.Environment]::GetEnvironmentVariable('JQUANTS_API_KEY', 'User')
```

### デプロイエラー
- `requirements.txt` の依存関係を確認
- Secretsの設定を再確認
- ログを確認（Streamlit Cloudの管理画面）

### Google Sheets接続エラー
1. CSV公開URLが正しいか確認
2. Apps ScriptのURLが正しいか確認
3. Apps Scriptが「全員」アクセス可能になっているか確認

---

## ✅ 推定所要時間

- タスク1（デプロイ準備）: 10分
- タスク2（GitHubにpush）: 5分
- タスク3（Streamlit Cloudデプロイ）: 10分
- タスク4（iPhone実機テスト）: 5分

**合計**: 約30分

---

## 💡 次回セッション開始時のコマンド

Claudeに以下のように伝えてください:

```
前回のセッションの続きから始めたいです。
docs/sessions/NEXT_SESSION_START_HERE.md を確認してください。

デプロイ準備（デバッグログ削除）から始めます。
```

---

お疲れさまでした！次回はデプロイまで完了させましょう。🎉
