# 日次自動化システム 実装計画

## 作成日
2026-02-20 05:00

## 概要
RSSフィードから投資アイデアを自動抽出し、J-Quants APIで日本株データを取得し、バックテストまでを日次で自動実行するシステム。

結果と知見は `docs/` 中心で蓄積し、作業の記憶を外部化する。

## デフォルト設定（決定事項）

### RSS
- ダミーURLで初期設定完了
- 実際のRSSフィードは `config/rss_feeds.yaml` を編集して追加

### 1日の処理数
- **2件**（負荷を考慮した推奨値）

### バックテスト期間
- **過去3年**

### ベンチマーク
- **TOPIX**

### レポート
- 言語: **日本語**
- 粒度: **詳細**（分析過程も記録）

### 保有期間
- **1日、3日、5日**（営業日）

## システム構成

### ディレクトリ構造

```
.
├── analyses/
│   ├── 00_to_be_started/       # アイデアキュー（ideas.jsonl）
│   └── {YYYYMMDD_HHMM}_{topic}/  # 個別分析プロジェクト
│       ├── idea_01.md
│       ├── backtest_metrics.json
│       └── backtest_summary.md
│
├── data/
│   ├── raw/
│   │   ├── rss/{YYYYMMDD}/     # RSS取得結果（JSON）
│   │   └── jquants/{YYYYMMDD}/ # J-Quants APIキャッシュ（Parquet）
│   └── processed/              # 前処理済みデータ
│
├── docs/
│   ├── knowledges/             # 知見蓄積（必須）
│   ├── plans/                  # 作業計画
│   ├── sessions/               # セッションサマリー
│   └── reports/                # 日次レポート（必須）
│
├── scripts/
│   └── daily_run.py            # メイン実行スクリプト
│
├── src/
│   ├── rss/                    # RSS取得
│   ├── ideas/                  # アイデア抽出・重複排除・キュー管理
│   ├── jquants/                # J-Quants API認証・クライアント
│   ├── data/                   # データキャッシュ
│   └── backtest/               # イベントスタディバックテスト
│
└── config/
    ├── rss_feeds.yaml          # RSSフィード設定
    └── daily.yaml              # 日次運用設定
```

## 実行手順

### 1. Windows環境変数の設定

**必須**: J-Quantsのリフレッシュトークン

PowerShellで設定（ユーザー環境変数、永続化）:
```powershell
[System.Environment]::SetEnvironmentVariable('JQUANTS_REFRESH_TOKEN', 'your_token_here', 'User')
```

確認:
```powershell
$env:JQUANTS_REFRESH_TOKEN
```

**任意**: ユニバース設定
```powershell
[System.Environment]::SetEnvironmentVariable('JQUANTS_UNIVERSE', 'TSEPrime', 'User')
```

### 2. Pythonパッケージのインストール

```bash
pip install feedparser pyyaml pandas numpy requests
```

または requirements.txtを作成している場合:
```bash
pip install -r requirements.txt
```

### 3. RSSフィードの設定

`config/rss_feeds.yaml` を編集:

```yaml
feeds:
  - name: "実際のフィード名"
    url: "https://example.com/actual-feed.rss"
    enabled: true
    category: "news"
```

### 4. 日次実行

```bash
python scripts/daily_run.py
```

### 5. 結果の確認

- **日次レポート**: `docs/reports/{YYYYMMDD}.md`
- **知見**: `docs/knowledges/{YYYYMMDD_HHMM}_{topic}.md`
- **個別分析**: `analyses/{YYYYMMDD_HHMM}_{topic}/`

## cronで自動実行（Windows タスクスケジューラ）

### タスクスケジューラで設定

1. タスクスケジューラを開く（`taskschd.msc`）
2. 「基本タスクの作成」
3. トリガー: 毎日 9:00 AM
4. 操作: プログラムの開始
   - プログラム: `python`
   - 引数: `C:\Users\{user}\claude project\workspace\scripts\daily_run.py`
   - 開始: `C:\Users\{user}\claude project\workspace`

### 確認

タスクスケジューラの履歴で実行ログを確認。

## トラブルシュート

### 1. JQUANTS_REFRESH_TOKEN not found

**原因**: 環境変数が設定されていない

**解決策**:
```powershell
[System.Environment]::SetEnvironmentVariable('JQUANTS_REFRESH_TOKEN', 'your_token', 'User')
```

その後、新しいPowerShellウィンドウで確認:
```powershell
$env:JQUANTS_REFRESH_TOKEN
```

### 2. RSS取得失敗

**原因**:
- ネットワークエラー
- RSSフィードURLが無効
- タイムアウト

**解決策**:
- `config/rss_feeds.yaml` のURLを確認
- `enabled: false` で一時的に無効化
- ログファイル `logs/{YYYYMMDD}.log` を確認

### 3. J-Quants API エラー

**原因**:
- リフレッシュトークンの有効期限切れ
- API制限（レート制限）
- ネットワークエラー

**解決策**:
- J-Quantsダッシュボードでトークンを再発行
- `data/.jquants_token_cache.json` を削除してリトライ
- レート制限: 自動的に待機するが、過度なリクエストは避ける

### 4. 銘柄コードが解決できない

**原因**:
- RSSに銘柄コード（4桁数字）が含まれていない
- 銘柄名のみで銘柄コード変換ロジックが未実装

**対応**:
- `require_tickers: true` の場合はスキップされる
- キューに残り、手動で処理可能

### 5. データキャッシュが肥大化

**解決策**:
```python
from src.data.cache import DataCache
cache = DataCache()
cache.clear_old_cache(max_age_days=7)
```

または `data/raw/jquants/` の古いディレクトリを手動削除。

## セキュリティ注意事項

### 絶対に守ること

1. **秘密情報をファイルに書かない**
   - `.env` ファイルは作らない（.gitignoreで除外済み）
   - 環境変数のみ使用

2. **ログに秘密情報を出さない**
   - トークン、APIキーは絶対にprintしない
   - ログレベルをDEBUGにしても漏れないこと

3. **危険フラグを使わない**
   - `--dangerously-skip-permissions` 等は原則禁止

## 拡張と改善

### 今後の課題

1. **銘柄名から銘柄コードへの変換**
   - 企業名→銘柄コードのマッピング実装
   - J-Quants APIの銘柄一覧を活用

2. **より高度なアイデア抽出**
   - LLMを使った要約とアクション抽出
   - スコアリングロジックの改善

3. **バックテストの拡張**
   - リスク調整後リターン（Sharpe, Sortino）
   - 最大ドローダウン
   - ポートフォリオ最適化

4. **通知機能**
   - 成功/失敗をメール通知
   - Slack/Discord連携

## 参考リンク

- [J-Quants API ドキュメント](https://jpx-jquants.com/)
- [feedparser ドキュメント](https://feedparser.readthedocs.io/)

## 作業ログ

### 2026-02-20 05:00 - 初期実装完了

**実装項目**:
- ✅ リポジトリ骨格（docs中心運用）
- ✅ 設定ファイル（RSS, daily.yaml, .env.example）
- ✅ RSSフェッチャー
- ✅ アイデア抽出・重複排除・キュー管理
- ✅ J-Quants認証・クライアント
- ✅ データキャッシュ
- ✅ イベントスタディバックテスト
- ✅ メイン実行スクリプト（daily_run.py）
- ✅ ドキュメント（knowledges, reports）
- ✅ この計画書

**次のステップ**:
1. E2Eテスト（RSS空でも動作確認）
2. 実際のRSSフィード追加
3. 初回実行
4. 結果レビューと改善

---

**ステータス**: 実装完了、テスト待ち
