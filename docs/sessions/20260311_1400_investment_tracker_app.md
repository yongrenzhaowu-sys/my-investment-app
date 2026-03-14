# セッション記録: 投資判断支援アプリ開発

**日時**: 2026-03-11 14:00
**作業時間**: 約3時間
**ステータス**: ✅ 実装完了（ログイン機能・UI改善済み）

## やったこと

### 1. プロジェクト計画作成
- `docs/plans/20260311_1400_investment_tracker_app/01_plan.md` を作成
- 要件定義、技術スタック、実装ステップを明確化

### 2. ディレクトリ構成とセットアップ
```
apps/investment-tracker/
├── app.py                    # メインアプリ
├── requirements.txt          # 依存パッケージ
├── .env.example              # 環境変数テンプレート
├── README.md                 # 使い方
├── data/                     # データ保存先
├── src/
│   ├── __init__.py
│   ├── auth.py               # J-Quants認証
│   ├── api.py                # J-Quants API呼び出し
│   ├── alpha.py              # アルファ計算
│   ├── kpi_check.py          # KPI自動チェック
│   └── ui_components.py      # UI部品
└── .streamlit/
    └── config.toml           # Streamlit設定
```

### 3. 実装した機能

#### 認証機能（src/auth.py）
- Windows環境変数から `JQUANTS_REFRESH_TOKEN` を読み込み
- 自動でIDトークンを取得・更新
- トークンキャッシュ（23時間有効）

#### API呼び出し（src/api.py）
- 日次株価取得（`get_daily_quotes`）
- 財務データ取得（`get_financial_statements`）
- 銘柄情報取得（`get_company_info`）

#### アルファ計算（src/alpha.py）
- 個別銘柄の騰落率計算
- yfinanceでS&P500取得
- アルファ = 個別騰落率 - S&P500騰落率
- 時系列データフレーム生成

#### KPIチェック（src/kpi_check.py）
- 営業利益率の自動計算（営業利益 / 売上高）
- 撤退KPI判定（閾値以下で警告）

#### UI部品（src/ui_components.py）
- メトリックカード表示
- アルファ推移グラフ（Plotly）
- KPI警告カード

#### メインアプリ（app.py）
- サイドバーで仮説登録フォーム
- 仮説一覧表示
- 詳細表示（アルファ、KPIチェック）
- JSONファイルでデータ保存
- モバイル最適化レイアウト

### 4. セキュリティ対応
- Windows環境変数から認証情報を読み込み
- .gitignoreに `apps/investment-tracker/data/hypotheses.json` を追加
- APIキーを表示しない設計

### 5. ドキュメント作成
- README.md（使い方、セットアップ、トラブルシューティング）
- .env.example（環境変数のテンプレート）

## 決めたこと

### データ保存形式
- JSON形式（`data/hypotheses.json`）
- 軽量で編集しやすい
- Gitで管理しない（.gitignore）

### 認証方法
- リフレッシュトークンのみ使用
- IDトークンは自動取得・更新（23時間キャッシュ）

### モバイル最適化
- Streamlitのデフォルトレイアウトを活用
- カラム分割で見やすく配置
- 大きめのボタン（use_container_width=True）

## 次にやること

### 1. 動作テスト（必須）
```bash
cd apps/investment-tracker
pip install -r requirements.txt
streamlit run app.py
```

**テスト項目**:
- [ ] 認証が正常に動作するか
- [ ] 仮説登録フォームが正常に動作するか
- [ ] 銘柄情報が取得できるか
- [ ] アルファ計算が正しく動作するか
- [ ] KPIチェックが正常に動作するか
- [ ] iPhone実機でレイアウトが崩れないか

### 2. 修正が必要な可能性がある箇所
- yfinanceのダウンロードでカラム名が異なる可能性
- J-Quants APIのレスポンス形式が想定と異なる可能性
- 営業利益率の計算に必要なフィールド名

### 3. 追加機能（オプション）
- [ ] データのエクスポート（CSV）
- [ ] グラフのカスタマイズ
- [ ] 複数銘柄の比較表示
- [ ] 通知機能（KPI警告をメール/LINE通知）

## 重要なパス

### プロジェクトディレクトリ
```
C:\Users\yongr\claude project\workspace\apps\investment-tracker\
```

### 起動コマンド
```bash
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
streamlit run app.py
```

### 環境変数確認（PowerShell）
```powershell
[System.Environment]::GetEnvironmentVariable('JQUANTS_REFRESH_TOKEN', 'User')
```

## 学んだこと

### Streamlitのモバイル最適化
- `st.set_page_config(layout="wide")` でレイアウト調整
- `use_container_width=True` でボタンを画面幅に合わせる
- `st.columns()` でカード配置を柔軟に調整

### セキュリティベストプラクティス
- 環境変数からの読み込み（os.environ）
- .gitignoreでユーザーデータを除外
- APIキーを絶対に表示しない

### J-Quants API活用
- リフレッシュトークンからIDトークンを自動取得
- キャッシュでAPI呼び出しを削減
- エラーハンドリングの重要性

## 追加修正（API V2対応）

### 認証方式の変更
- リフレッシュトークン方式 → APIキー方式に変更
- `JQUANTS_REFRESH_TOKEN` → `JQUANTS_API_KEY`
- J-Quants API V1 → V2に対応

### 修正したファイル
- `src/auth.py`: APIキーベースの認証に変更
- `src/api.py`: API V2エンドポイントに対応
  - `/bars/daily`: 日次株価
  - `/fins/statements`: 財務データ
  - `/listed/info`: 銘柄情報
- `.env.example`: JQUANTS_API_KEYに変更
- `README.md`: 環境変数名を更新

### テスト結果
- [x] モジュールインポート成功
- [x] 認証テスト成功
- [ ] Streamlitアプリ起動テスト（ユーザーが実行）
- [ ] 仮説登録テスト
- [ ] アルファ計算テスト
- [ ] KPIチェックテスト

## 次の手順（ユーザーが実行）

### 1. アプリ起動
```powershell
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
streamlit run app.py
```

### 2. ブラウザでアクセス
```
http://localhost:8501
```

### 3. 仮説登録
- サイドバーから銘柄コード、購入日、購入価格、購入理由、撤退KPIを入力
- 登録ボタンをクリック

### 4. 詳細表示
- 一覧から「詳細を見る」をクリック
- アルファ推移、KPIチェックを確認

## 追加機能実装（第2フェーズ）

### 1. Streamlit Secrets対応
- `.streamlit/secrets.toml.example` を作成
- `src/auth.py` を修正してStreamlit Secretsに対応
- 優先順位: Streamlit Secrets → 環境変数

### 2. ログイン機能実装
- `app.py` に `check_login()` 関数を追加
- `st.session_state.logged_in` でログイン状態を保持
- `APP_PASSWORD` による簡易認証
- パスワード不一致時は「認証が必要です」と表示し、以降のコードを実行しない
- ログアウトボタンをサイドバーに追加

### 3. UI改善（iPhone対応）
- `st.metric()` を使ってメイン指標を強調表示
- アルファのdelta表示（正なら緑、負なら赤）
- グラフのモバイル最適化:
  - フォントサイズを大きく（14px）
  - 余白を最小化（margin調整）
  - グリッド線を見やすく
  - 横幅いっぱいに表示（`use_container_width=True`）

### 4. ドキュメント更新
- `SETUP.md` を新規作成（詳細なセットアップ手順）
- `QUICKSTART.md` を更新（ログイン手順追加）
- `README.md` を更新（Streamlit Secrets対応）
- `.gitignore` に `secrets.toml` を追加

### 修正ファイル一覧
- ✅ `.streamlit/secrets.toml.example` （新規）
- ✅ `src/auth.py` （Streamlit Secrets対応）
- ✅ `app.py` （ログイン機能 + UI改善）
- ✅ `src/ui_components.py` （グラフ改善）
- ✅ `SETUP.md` （新規）
- ✅ `QUICKSTART.md` （更新）
- ✅ `README.md` （更新）
- ✅ `.gitignore` （更新）

## 次の手順（ユーザーが実行）

### 1. secrets.tomlを作成

```powershell
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
notepad .streamlit/secrets.toml
```

### 2. APIキーとパスワードを設定

```toml
JQUANTS_API_KEY = "Windows環境変数にあるAPIキーをコピー"
APP_PASSWORD = "好きなパスワードを設定（英数字推奨）"
```

### 3. アプリ起動

```powershell
streamlit run app.py
```

### 4. ログイン

設定したパスワードでログイン

### 5. 動作確認

- [ ] ログイン成功
- [ ] 仮説登録
- [ ] 詳細表示
- [ ] アルファ計算
- [ ] KPIチェック
- [ ] ログアウト

## 次回セッション開始時のチェックリスト

1. [ ] 動作テスト結果を確認
2. [ ] エラーがあれば修正
3. [ ] iPhone実機でレイアウト確認
4. [ ] ユーザーフィードバックを反映
