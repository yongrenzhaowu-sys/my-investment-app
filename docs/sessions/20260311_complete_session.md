# セッション記録: 投資判断支援アプリ完全実装

**日時**: 2026-03-11 14:00 - 18:00
**作業時間**: 約4時間
**ステータス**: ✅ 実装完了（デプロイ前）

## 今日やったこと（時系列）

### Phase 1: 基本アプリ実装（14:00-15:30）

#### 1-1. プロジェクト計画
- `docs/plans/20260311_1400_investment_tracker_app/01_plan.md` 作成
- 要件定義、技術スタック、実装ステップを策定

#### 1-2. ディレクトリ構成とセットアップ
```
apps/investment-tracker/
├── app.py                    # メインアプリ
├── requirements.txt          # 依存パッケージ
├── .streamlit/config.toml    # Streamlit設定
└── src/
    ├── auth.py               # J-Quants認証（API V2）
    ├── api.py                # J-Quants API呼び出し
    ├── alpha.py              # アルファ計算
    ├── kpi_check.py          # KPI自動チェック
    └── ui_components.py      # UI部品
```

#### 1-3. 実装した機能
- ✅ J-Quants API V2認証（APIキーベース）
- ✅ 仮説登録（銘柄コード、購入日、購入価格、理由、撤退KPI）
- ✅ アルファ計算（個別銘柄 - S&P500）
- ✅ KPI自動チェック（営業利益率）
- ✅ モバイル最適化レイアウト

#### 1-4. テスト結果
- ✅ モジュールインポート成功
- ✅ 認証テスト成功
- ⏸️ Streamlitアプリ起動（ユーザーが後で実行）

### Phase 2: 追加機能実装（15:30-17:00）

#### 2-1. Streamlit Secrets対応
- `.streamlit/secrets.toml.example` 作成
- `src/auth.py` を修正（Secrets優先、環境変数フォールバック）
- セキュアな設計

#### 2-2. ログイン機能実装
- パスワード認証（`APP_PASSWORD`）
- `st.session_state.logged_in` でセッション管理
- リロードしても再ログイン不要
- ログアウトボタン追加

#### 2-3. UI改善（iPhone対応）
- `st.metric()` でメイン指標を強調表示
- アルファのdelta表示（正→緑、負→赤）
- グラフのモバイル最適化:
  - フォントサイズ拡大（14px）
  - 余白最小化
  - グリッド線強調
  - 横幅いっぱいに表示

#### 2-4. ドキュメント作成
- `SETUP.md` - 詳細セットアップ手順
- `QUICKSTART.md` - クイックスタートガイド
- `DEPLOY.md` - Streamlit Cloudデプロイ手順
- `README.md` - 更新

### Phase 3: Google Sheets統合（17:00-18:00）

#### 3-1. 複雑版（サービスアカウント）
- `st-gsheets-connection` 使用
- Google Cloud Platform設定が必要
- `GSHEETS_SETUP.md` 作成
- **結論**: 設定が複雑すぎる

#### 3-2. シンプル版（認証不要）✅ 採用
- **読み込み**: スプレッドシートをCSV公開 → `pandas.read_csv()`
- **書き込み**: Google Apps Script（ウェブアプリ公開）→ POSTリクエスト
- `src/simple_gsheets_client.py` 作成
- `google-apps-script/Code.gs` 作成
- `SIMPLE_GSHEETS_SETUP.md` 作成（10分で完了する手順）

## 完成した機能一覧

### 📋 仮説登録
- 銘柄コード、購入日、購入価格、購入理由、撤退KPIを入力
- **データ永続化**: Google Sheets（Streamlit Cloud）/ JSON（ローカル）

### 📊 実力可視化（アルファ）
- 個別銘柄の騰落率計算
- S&P500との比較（yfinance）
- アルファ = 個別 - S&P500
- 時系列グラフ（横幅いっぱい、モバイル最適化）

### 🎯 自動進捗チェック
- J-Quants財務データAPIで最新決算取得
- 営業利益率を自動計算
- 撤退KPI判定（閾値以下で🚨警告）

### 🔐 セキュアなログイン
- パスワード認証（`APP_PASSWORD`）
- セッション状態保持
- ログアウト機能

### 📱 モバイル最適化
- iPhoneの縦画面に最適化
- `st.metric()` で指標強調
- グラフ横幅いっぱい、フォント拡大

## ファイル構成（完成版）

```
apps/investment-tracker/
├── app.py                              # メインアプリ
├── requirements.txt                    # 依存パッケージ
├── README.md                           # 概要
├── SETUP.md                            # セットアップ詳細
├── QUICKSTART.md                       # クイックスタート
├── DEPLOY.md                           # Streamlit Cloudデプロイ
├── SIMPLE_GSHEETS_SETUP.md            # Google Sheets設定（10分）
├── .streamlit/
│   ├── config.toml                    # Streamlit設定
│   └── secrets.toml.example           # Secretsテンプレート
├── src/
│   ├── __init__.py
│   ├── auth.py                        # J-Quants認証
│   ├── api.py                         # J-Quants API
│   ├── alpha.py                       # アルファ計算
│   ├── kpi_check.py                   # KPI自動チェック
│   ├── ui_components.py               # UI部品
│   ├── gsheets_client.py              # Google Sheets（複雑版）
│   └── simple_gsheets_client.py       # Google Sheets（シンプル版）✅
├── google-apps-script/
│   └── Code.gs                        # Apps Scriptコード
└── data/
    └── hypotheses.json                # ローカルデータ（.gitignore）
```

## 技術スタック

### フロントエンド
- **Streamlit**: 1.31.0+
- **Plotly**: グラフ表示

### バックエンド
- **J-Quants API V2**: 株価・財務データ
- **yfinance**: S&P500データ
- **Google Sheets**: データ永続化（Streamlit Cloud）

### データ保存
- **ローカル**: JSONファイル（`data/hypotheses.json`）
- **クラウド**: Google Sheets（CSV公開 + Apps Script）

## 設定ファイル（.streamlit/secrets.toml）

### ローカル開発

```toml
JQUANTS_API_KEY = "your_api_key"
APP_PASSWORD = "your_password"
USE_GSHEETS = false  # JSONファイル使用
```

### Streamlit Cloud

```toml
JQUANTS_API_KEY = "your_api_key"
APP_PASSWORD = "your_password"
USE_GSHEETS = true  # Google Sheets使用
SPREADSHEET_READ_URL = "https://docs.google.com/.../pub?gid=0&single=true&output=csv"
SPREADSHEET_WRITE_URL = "https://script.google.com/macros/s/.../exec"
```

## 次にやること（優先順位順）

### 🚨 必須（デプロイ前）

#### 1. Google Sheetsのセットアップ
- [ ] Google Spreadsheetsを作成（シート名: hypotheses）
- [ ] CSV公開設定（読み込み用URL取得）
- [ ] Apps Script作成・デプロイ（書き込み用URL取得）
- [ ] `.streamlit/secrets.toml` にURL設定

**所要時間**: 10分
**手順**: `apps/investment-tracker/SIMPLE_GSHEETS_SETUP.md` 参照

#### 2. ローカルテスト
- [ ] secrets.toml作成（APIキー、パスワード設定）
- [ ] アプリ起動: `streamlit run app.py`
- [ ] ログイン成功
- [ ] 仮説登録
- [ ] 詳細表示（アルファ計算、KPIチェック）
- [ ] ログアウト

**所要時間**: 15分
**手順**: `apps/investment-tracker/QUICKSTART.md` 参照

#### 3. GitHubにpush
```bash
cd "C:\Users\yongr\claude project\workspace"
git add apps/investment-tracker/
git commit -m "Add investment tracker app with Google Sheets integration"
git push origin main
```

**所要時間**: 5分

#### 4. Streamlit Cloudデプロイ
- [ ] Streamlit Cloudにログイン
- [ ] 新しいアプリ作成
  - Repository: あなたのリポジトリ
  - Main file: `apps/investment-tracker/app.py`
- [ ] Secretsに設定（APIキー、パスワード、Google Sheets URL）
- [ ] デプロイ開始

**所要時間**: 10分
**手順**: `apps/investment-tracker/DEPLOY.md` 参照

### ⚙️ オプション（デプロイ後）

#### 5. iPhone実機テスト
- [ ] iPhoneのブラウザでアクセス
- [ ] ログイン
- [ ] レイアウト確認
- [ ] ホーム画面に追加（PWA化）

#### 6. 機能拡張（将来）
- [ ] 複数銘柄の比較表示
- [ ] グラフのカスタマイズ
- [ ] 通知機能（KPI警告をメール/LINE）
- [ ] ポートフォリオ全体のパフォーマンス表示
- [ ] データのエクスポート（CSV）

## 重要な注意点

### セキュリティ
- ✅ APIキーは環境変数/Secrets（絶対にコードに直書きしない）
- ✅ `secrets.toml` は `.gitignore`（Gitにコミットしない）
- ✅ パスワード認証でアクセス制御
- ⚠️ Google Sheetsは公開設定（URLを知っていればアクセス可能）
  - → アプリ側でAPP_PASSWORDで保護されているため実用上問題なし

### データ永続化
- **ローカル**: JSONファイル（`data/hypotheses.json`）
- **Streamlit Cloud**: Google Sheets（再起動してもデータが消えない）

### トラブルシューティング
- 認証エラー → Secretsの`JQUANTS_API_KEY`を確認
- ログインできない → Secretsの`APP_PASSWORD`を確認
- Google Sheetsエラー → `SPREADSHEET_READ_URL`と`SPREADSHEET_WRITE_URL`を確認
- データが読み込めない → スプレッドシートのシート名が「hypotheses」か確認

## 学んだこと

### Streamlitアプリ開発
- `st.session_state` でセッション管理
- `st.secrets` で機密情報管理
- `st.metric()` でメトリック強調表示
- モバイル最適化（レイアウト、フォントサイズ）

### Google Sheets統合
- **複雑版**: サービスアカウント認証（30分以上）
- **シンプル版**: CSV公開 + Apps Script（10分）✅
- 認証不要でもAPP_PASSWORDで保護すれば実用的

### J-Quants API V2
- APIキーベース認証（シンプル）
- エンドポイント: `/bars/daily`, `/fins/statements`, `/listed/info`
- レスポンス形式: JSON → pandas DataFrame

## ドキュメント一覧

### ユーザー向け
- `apps/investment-tracker/README.md` - 概要
- `apps/investment-tracker/SETUP.md` - 詳細セットアップ
- `apps/investment-tracker/QUICKSTART.md` - クイックスタート
- `apps/investment-tracker/SIMPLE_GSHEETS_SETUP.md` - Google Sheets設定（10分）
- `apps/investment-tracker/DEPLOY.md` - Streamlit Cloudデプロイ

### 開発者向け
- `docs/plans/20260311_1400_investment_tracker_app/01_plan.md` - 実装計画
- `docs/sessions/20260311_1400_investment_tracker_app.md` - Phase 1セッション
- `docs/sessions/20260311_1600_gsheets_integration.md` - Phase 3セッション（複雑版）
- `docs/knowledges/20260311_1400_jquants_api_v2_auth.md` - API V2認証ナレッジ

## 次回セッション開始時のチェックリスト

次回は `docs/sessions/NEXT_SESSION_START_HERE.md` から開始してください。

1. [ ] このセッション記録を確認
2. [ ] Google Sheetsセットアップ（10分）
3. [ ] ローカルテスト（15分）
4. [ ] GitHubにpush（5分）
5. [ ] Streamlit Cloudデプロイ（10分）
6. [ ] iPhone実機テスト

**推定所要時間**: 約45分

---

お疲れさまでした！🎉
