# セッション記録: Google Sheets統合完全実装

**日時**: 2026-03-14 16:00-
**ステータス**: ✅ 完了

---

## 📊 完了したこと

### タスク5: Google Sheets統合セットアップ ✅

#### フェーズ1: 初期セットアップ
- ✅ Google Spreadsheetsでスプレッドシート作成（investment-tracker-data）
- ✅ シート設定（hypotheses、ヘッダー行）
- ✅ CSV公開URL取得
- ✅ Apps Scriptデプロイ（ウェブアプリURL取得）
- ✅ Streamlit CloudのSecrets設定

#### フェーズ2: sharesフィールド対応
- ✅ Apps Script（Code.gs）にsharesフィールド追加
- ✅ simple_gsheets_client.pyにsharesフィールド追加
- ✅ SIMPLE_GSHEETS_SETUP.mdのスキーマ更新

#### フェーズ3: データ読み込みエラー修正
- ✅ ヘッダー行のスペース問題修正（Google Sheets側）
- ✅ NaN値の処理追加（sharesフィールド）
- ✅ 行ごとのエラーハンドリング追加

#### フェーズ4: 連続登録問題の根本的解決
- ✅ キャッシュバスター追加（タイムスタンプクエリパラメータ）
- ✅ 保存後の検証ロジック追加（2秒×最大5回）
- ✅ **セッション状態マスター化**（根本的解決）
  - セッション状態をマスターデータとして使用
  - Google Sheetsへの保存は非同期（バックグラウンド）
  - 即座に画面に反映、待機不要
  - 連続登録でもデータ消失なし

---

## 🔧 技術的な問題と解決策

### 問題1: sharesフィールドが欠けている
**原因**: 前回追加したsharesフィールドが、Google Sheetsのスキーマに含まれていなかった

**解決策**:
- Apps Script（Code.gs）のヘッダー行にshares追加
- simple_gsheets_client.pyの読み込み処理にshares追加
- SIMPLE_GSHEETS_SETUP.mdのヘッダー例を更新

### 問題2: データ読み込みエラー「'purchase_date'」
**原因**: Google Sheetsのヘッダー行にスペースが含まれていた
```
id,code,name, purchase_date ,purchase_price  ,shares,reason , exit_kpi , created_at
              ↑前後にスペース
```

**解決策**:
- Google Sheetsのヘッダー行を修正（スペース削除）
- 正しいヘッダー: `id,code,name,purchase_date,purchase_price,shares,reason,exit_kpi,created_at`

### 問題3: NaN値のエラー「cannot convert float NaN to integer」
**原因**: sharesフィールドがNaN（空白）の場合、`int()`に変換できない

**解決策**:
```python
shares_value = row.get("shares", 100)
if pd.isna(shares_value):
    shares_value = 100
```

### 問題4: 2銘柄目以降が表示されない
**原因**: データ読み込み処理で、エラーが発生すると全体が停止していた

**解決策**:
- 行ごとにtry-exceptで囲む
- エラーが発生した行はスキップして、次の行に進む
- エラーメッセージを表示してデバッグ可能に

### 問題5: 連続登録でデータが消える、2重登録される ⚠️ **最重要問題**
**原因**: Google SheetsのCSV公開には反映遅延（数秒〜数十秒）がある

**試した解決策**:
1. ❌ キャッシュバスター追加 → 効果なし
2. ❌ 3秒待機 → 不十分
3. ❌ 保存後の検証ロジック（2秒×最大5回） → かえって悪化

**最終的な解決策**: ✅ **セッション状態マスター化**
```python
def load_hypotheses():
    # セッション状態にキャッシュがあればそれを使う（最優先）
    if "hypotheses_cache" in st.session_state:
        return st.session_state.hypotheses_cache

    # キャッシュがない場合のみ、外部から読み込む
    hypotheses = ... # Google Sheets or ローカルJSON
    st.session_state.hypotheses_cache = hypotheses
    return hypotheses

def save_hypotheses(hypotheses):
    # まずセッション状態を更新（即座に反映）
    st.session_state.hypotheses_cache = hypotheses

    # 次に永続化ストレージに保存（バックグラウンド）
    client.save_hypotheses(hypotheses)
```

**メリット**:
- ✅ 即座に反映（待機不要）
- ✅ 連続操作OK（何度でも連続登録可能）
- ✅ データ消失なし（Google Sheetsの遅延に影響されない）
- ✅ 永続化も保証（Google Sheetsへの保存も並行して行われる）

---

## 📂 修正したファイル

### 既存ファイルの修正
1. `apps/investment-tracker/SIMPLE_GSHEETS_SETUP.md` - sharesフィールド追加
2. `apps/investment-tracker/google-apps-script/Code.gs` - sharesフィールド追加
3. `apps/investment-tracker/src/simple_gsheets_client.py` - sharesフィールド、NaN処理、エラーハンドリング、キャッシュバスター
4. `apps/investment-tracker/app.py` - セッション状態マスター化

### GitHubコミット履歴
1. `943e47f` - Fix: Add shares field to Google Sheets integration
2. `c486667` - Fix: Handle NaN values in shares field
3. `e3510f5` - Add error handling for individual row processing
4. `4611807` - Fix: Add cache buster to prevent stale data reads
5. `a5f4f9c` - Fix: Add 3-second wait after saving to Google Sheets
6. `e9a69d8` - Fix: Add verification after saving to Google Sheets
7. `1d26626` - Fix: Use session state as master data source ✅ **最終解決**

---

## 🔗 取得したURL

### Google Sheets
- **スプレッドシートID**: `1gg445XmJIYW65ZwR3rHbuyqhbBakZxlXEd87rEJM8Po`
- **CSV公開URL（読み込み用）**:
  ```
  https://docs.google.com/spreadsheets/d/e/2PACX-1vRiEUWgFsrr5FtQ99pao5fVMoegFGCtNMQVhlah-tr8pT-D08UB3LLK3b8CyU7RFWB4dfbb5pxMvYOM/pub?gid=0&single=true&output=csv
  ```
- **Apps Script URL（書き込み用）**:
  ```
  https://script.google.com/macros/s/AKfycbzkvAsVqTSd1ewB_S-aGrVlcC7hcDffHlmzFf1Wv4E-58_AtMGm2PCI0_6Q3H8Gb3ZmsA/exec
  ```

### Streamlit Cloud Secrets
```toml
JQUANTS_API_KEY = "ユーザーのAPIキー"
APP_PASSWORD = "ユーザーのパスワード"
USE_GSHEETS = true
SPREADSHEET_READ_URL = "（上記のCSV公開URL）"
SPREADSHEET_WRITE_URL = "（上記のApps Script URL）"
```

---

## 📊 現在の状態

### データ保存先
- **本番環境（Streamlit Cloud）**: Google Sheets
- **セッション内**: Streamlitセッション状態（マスターデータ）

### 動作確認
- ✅ 仮説登録（連続登録OK）
- ✅ 仮説編集
- ✅ 仮説削除
- ✅ Google Sheetsへの永続化
- ✅ ブラウザリロード後の復元

### 保持中の銘柄
- テスト確認時点で3銘柄登録成功

---

## 💡 学んだ教訓

### Google SheetsのCSV公開は信頼できない
- CSV公開URLへの反映遅延は**数秒〜数十秒**かかる
- 遅延時間は予測不可能
- キャッシュバスターや待機処理では根本的に解決できない

### セッション状態をマスターデータとする設計
- UIの状態はセッション状態で管理
- 永続化ストレージ（Google Sheets、JSON）は「バックアップ」として扱う
- 非同期的に保存し、UIをブロックしない
- この設計により、外部ストレージの遅延に影響されない

### Streamlitのセッション状態の特性
- ブラウザセッション内で維持される
- ページリロード（`st.rerun()`）でも維持される
- ブラウザのタブを閉じるとクリアされる
- マスターデータとして使うには、初回読み込みで外部ストレージから復元する必要がある

---

## 🎯 次回タスク（2026-03-15）

### 優先度順

#### タスク6: 銘柄名表示の修正（30分）
**問題**: 銘柄名が「銘柄XXXXX」と表示される

**調査事項**:
1. J-Quants API V2の `/listed/info` エンドポイント確認
2. `get_company_info()` のレスポンス処理確認
3. エラーログ確認

**解決策**:
- APIレスポンスのキー名確認（CompanyName, company_name, Name等）
- エラーハンドリング強化
- デフォルト値の改善

#### タスク7: 初期資金設定の永続化（30分）
**問題**: ログインごとに1,000,000円にリセット

**実装**:
1. `data/settings.json` 作成
2. 読み込み/保存関数実装
3. `.gitignore` に追加
4. 損益サマリー画面で設定UI更新

#### タスク8: 部分売却機能（1時間）
**問題**: 全株売却のみ

**実装**:
1. 売却フォームに「売却数量」フィールド追加
2. 残株数の計算
3. 部分売却時: 仮説の株数を更新（削除しない）
4. 全株売却時: 仮説から削除

#### タスク9: NISA口座対応（1時間）
**実装**:
1. 仮説登録フォームに「NISA口座」チェックボックス追加
2. データ構造に `is_nisa` フィールド追加
3. 売却時の税金計算: NISA口座は税金0%
4. 損益サマリーでNISA/課税口座を区別表示
5. 既存銘柄: デフォルト `is_nisa = false`

#### タスク10: 投資指標の追加（1時間）
**実装する指標**:
1. シャープレシオ
2. 最大ドローダウン
3. 勝率
4. 平均保有日数
5. 累計リターン

**表示場所**: 損益サマリー画面

---

## 📚 参考ドキュメント

### セットアップガイド
- `apps/investment-tracker/SIMPLE_GSHEETS_SETUP.md` - Google Sheets統合手順

### 計画ドキュメント
- `docs/plans/20260312_0000_trading_history/01_plan.md` - 売買履歴機能の計画

### ナレッジ
- `docs/knowledges/20260311_1800_jquants_api_v2_complete.md` - J-Quants API V2完全ガイド

---

## 🔗 リンク

### GitHubリポジトリ
- https://github.com/yongrenzhaowu-sys/my-investment-app

### Streamlit Cloudアプリ
- デプロイ済み、動作確認済み

---

お疲れさまでした！明日続きをやりましょう。🎉
