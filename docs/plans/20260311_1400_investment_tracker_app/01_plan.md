# 投資判断支援アプリ（Streamlit）実装計画

## 概要
J-Quants API（スタンダードプラン）を活用し、iPhoneで動作する投資判断支援アプリをStreamlitで構築する。

## 要件

### 1. 認証
- J-Quantsのリフレッシュトークンを使用
- 自動でIDトークンを取得・更新
- 環境変数から読み込み（セキュリティ）

### 2. 仮説登録
- 銘柄コード（例: 7203）
- 購入日
- 購入価格
- 購入理由（中計の注目点など）
- 撤退KPI（例: 営業利益率10%未満）
- データ保存: JSON形式（`data/hypotheses.json`）

### 3. 実力可視化（アルファ）
- **個別銘柄の騰落率**: (現在価格 - 購入価格) / 購入価格
- **S&P500の騰落率**: yfinanceで同期間の^GSPCデータ取得
- **アルファ**: 個別銘柄騰落率 - S&P500騰落率
- 表示: グラフ（時系列）とカード（現在値）

### 4. 自動進捗チェック
- J-Quants財務データAPI（`/fins/statements`）で最新決算を取得
- 営業利益率を計算: 営業利益 / 売上高
- 進捗率: 実績 / 計画（通期予想に対する進捗）
- 撤退KPI判定: 営業利益率 < 設定値 → 🚨赤字警告表示

### 5. モバイル最適化
- iPhone縦画面レイアウト
- シンプルなカードデザイン
- タップしやすいボタンサイズ
- レスポンシブ対応（st.columnsで調整）

## 技術スタック

### フロントエンド
- **Streamlit**: Pythonベースのダッシュボード
- **Streamlit-Aggrid**: テーブル表示（オプション）
- **Plotly**: インタラクティブグラフ

### バックエンド
- **J-Quants API**:
  - `/token/auth_refresh`: トークン更新
  - `/prices/daily_quotes`: 日次株価
  - `/fins/statements`: 財務データ
- **yfinance**: S&P500データ取得
- **データ保存**: JSON（`data/hypotheses.json`）

### デプロイ
- ローカル: `streamlit run app.py`
- クラウド: Streamlit Cloud（GitHub連携）

## ディレクトリ構成

```
apps/investment-tracker/
├── app.py                    # メインアプリ
├── requirements.txt          # 依存パッケージ
├── .env.example              # 環境変数テンプレート
├── README.md                 # 使い方
├── data/
│   └── hypotheses.json       # 仮説データ（gitignore）
├── src/
│   ├── auth.py               # J-Quants認証
│   ├── api.py                # J-Quants API呼び出し
│   ├── alpha.py              # アルファ計算
│   ├── kpi_check.py          # KPI自動チェック
│   └── ui_components.py      # UI部品
└── .streamlit/
    └── config.toml           # Streamlit設定（モバイル最適化）
```

## 実装ステップ

### Phase 1: セットアップ（30分）
- [x] ディレクトリ作成
- [ ] requirements.txt作成
- [ ] .env.example作成
- [ ] .gitignore更新

### Phase 2: 認証機能（30分）
- [ ] `src/auth.py`: リフレッシュトークン → IDトークン取得
- [ ] トークンキャッシュ（st.session_state）
- [ ] エラーハンドリング

### Phase 3: 仮説登録UI（45分）
- [ ] `app.py`: サイドバーで仮説入力フォーム
- [ ] JSON保存・読み込み
- [ ] 一覧表示（st.dataframe）

### Phase 4: アルファ計算（1時間）
- [ ] `src/alpha.py`:
  - J-Quants APIで個別銘柄価格取得
  - yfinanceでS&P500取得
  - アルファ計算
- [ ] `src/ui_components.py`: グラフ表示（Plotly）

### Phase 5: KPI自動チェック（1時間）
- [ ] `src/kpi_check.py`:
  - 財務データAPI呼び出し
  - 営業利益率計算
  - 撤退KPI判定
- [ ] UI: 警告カード（st.error）

### Phase 6: モバイル最適化（30分）
- [ ] `.streamlit/config.toml`: 幅・フォント調整
- [ ] レスポンシブレイアウト
- [ ] iPhone実機テスト

### Phase 7: ドキュメント（15分）
- [ ] README.md作成
- [ ] セッション記録保存
- [ ] ナレッジ保存

## データ構造

### hypotheses.json
```json
[
  {
    "id": "uuid",
    "code": "7203",
    "name": "トヨタ自動車",
    "purchase_date": "2026-01-15",
    "purchase_price": 2500,
    "reason": "中計で電動化投資20%増、営業利益率10%目標",
    "exit_kpi": {
      "metric": "operating_margin",
      "threshold": 10.0,
      "operator": "less_than"
    },
    "created_at": "2026-03-11T14:00:00"
  }
]
```

## API使用量の考慮

### J-Quants API制限（スタンダードプラン）
- 月間100,000リクエスト
- 1秒あたり10リクエスト

### 最適化戦略
- キャッシュ: st.cache_data（24時間）
- バッチ取得: 複数銘柄を1リクエストで取得
- 差分更新: 前回取得日以降のデータのみ取得

## セキュリティ

### 環境変数
```bash
JQUANTS_REFRESH_TOKEN=your_refresh_token_here
```

### .gitignore追加
```
apps/investment-tracker/.env
apps/investment-tracker/data/hypotheses.json
```

## 次のステップ
1. ディレクトリ構成を作成
2. Phase 1から順次実装
3. iPhone実機でテスト
