# 日次自動化システム実装計画

## 概要

RSSフィードから投資アイデアを抽出し、J-Quants APIで日本株データを取得してバックテストを実行、
結果と知見をdocs/配下に蓄積する日次自動化システム。

## 実装日

2026-02-20

## システム構成

### ディレクトリ構造

```
workspace/
├── analyses/
│   ├── 00_to_be_started/          # アイデアキュー
│   │   └── ideas.jsonl             # 処理待ちアイデア
│   └── {YYYYMMDD_HHMM}_{topic}/    # 個別分析プロジェクト
│       ├── idea_01.md              # アイデア計画
│       └── backtest_metrics.json   # バックテスト結果
├── config/
│   ├── rss_feeds.yaml              # RSSフィード設定
│   └── daily.yaml                  # 日次実行設定
├── data/
│   ├── raw/
│   │   ├── rss/{YYYYMMDD}/         # RSS生データ
│   │   └── jquants/{YYYYMMDD}/     # J-Quants APIキャッシュ
│   └── processed/                  # 前処理済みデータ
├── docs/
│   ├── knowledges/                 # 知見蓄積（必須）
│   ├── plans/                      # 実装計画
│   ├── reports/                    # 日次レポート
│   └── sessions/                   # セッションサマリー
├── scripts/
│   └── daily_run.py                # 日次実行スクリプト（エントリーポイント）
└── src/
    ├── rss/                        # RSS取得
    ├── ideas/                      # アイデア抽出・キュー管理
    ├── jquants/                    # J-Quants API
    ├── data/                       # キャッシュ管理
    ├── backtest/                   # イベントスタディ
    ├── reporting/                  # レポート生成
    └── knowledges/                 # 知見ファイル生成
```

## 日次実行フロー

### 1. RSS取得
- config/rss_feeds.yaml に定義されたフィードを取得
- data/raw/rss/{YYYYMMDD}/ にJSON形式で保存

### 2. アイデア抽出
- RSS記事から証券コード（4桁）を抽出
- ポジティブ/ネガティブキーワードでスコアリング
- analyses/00_to_be_started/ideas.jsonl にキュー投入

### 3. 上位N件を選択
- スコア順に上位N件（デフォルト: 1件）を選択
- 各アイデアに対して analyses/{YYYYMMDD_HHMM}_{topic}/ を作成

### 4. 価格データ取得
- J-Quants API V2 で株価データ取得
- キャッシュ優先（同日再実行でAPIを叩かない）
- data/raw/jquants/{YYYYMMDD}/ にキャッシュ保存

### 5. バックテスト実行
- イベントスタディ型（公開日起点の超過リターン計算）
- 保有期間: 1日、3日、5日（営業日）
- backtest_metrics.json に結果を保存

### 6. 知見・レポート生成
- docs/knowledges/{YYYYMMDD_HHMM}_{topic}.md（必須）
- docs/reports/{YYYYMMDD}.md（日次レポート）

## Windows環境変数設定

### 必須

```cmd
JQUANTS_API_KEY=<J-Quants V2 APIキー>
```

### 設定方法

1. **一時的（現在のコマンドプロンプトのみ）**:
   ```cmd
   set JQUANTS_API_KEY=your_api_key_here
   ```

2. **永続的（推奨）**:
   - Windowsキー押下 → "環境変数" で検索
   - "システム環境変数の編集" を選択
   - "環境変数" ボタンをクリック
   - "新規" で `JQUANTS_API_KEY` を追加
   - 値に実際のAPIキーを貼り付け
   - OK で閉じる
   - コマンドプロンプトを再起動

3. **確認**:
   ```cmd
   echo %JQUANTS_API_KEY%
   ```

## 実行方法

### 日次実行（cronで自動化）

```bash
python scripts/daily_run.py
```

### 初回セットアップ

1. **依存関係インストール**:
   ```bash
   pip install -r requirements.txt
   ```

2. **環境変数設定**:
   上記「Windows環境変数設定」を参照

3. **初回実行**:
   ```bash
   python scripts/daily_run.py
   ```

4. **出力確認**:
   - `docs/reports/{YYYYMMDD}.md` が生成されているか
   - `docs/knowledges/` に知見ファイルが生成されているか
   - `analyses/` に分析ディレクトリが作成されているか

### cron設定（Windows Task Scheduler）

1. タスクスケジューラを起動
2. "基本タスクの作成"
3. トリガー: 毎日、実行時刻を指定（例: 06:00）
4. 操作: プログラムの開始
   - プログラム/スクリプト: `python`
   - 引数の追加: `scripts\daily_run.py`
   - 開始: `C:\Users\yongr\claude project\workspace`

## トラブルシューティング

### RSS取得失敗

**症状**: 特定のフィードが取得できない

**対処**:
- ログで該当フィードのエラーを確認
- RSSフィードURLが変更されていないか確認
- 一時的な障害の可能性あり → 次回実行を待つ

### J-Quants API認証エラー

**症状**: `JQUANTS_API_KEY environment variable is not set`

**対処**:
1. 環境変数が設定されているか確認:
   ```cmd
   echo %JQUANTS_API_KEY%
   ```
2. 設定されていない場合は上記「Windows環境変数設定」を実施
3. コマンドプロンプトを再起動

### データ取得失敗

**症状**: 特定の銘柄のデータが取得できない

**対処**:
- 証券コードが正しいか確認
- 上場廃止銘柄の可能性あり
- J-Quants APIのレート制限に引っかかっている可能性
  → `config/daily.yaml` の `delay` を増やす

### アイデアが抽出されない

**症状**: `ideas.jsonl` が空

**対処**:
- RSS記事に証券コード（4桁数字）が含まれているか確認
- `config/daily.yaml` の `min_score` が高すぎないか確認
- ネガティブキーワードで除外されていないか確認

### 処理が遅い

**対処**:
- キャッシュが正しく機能しているか確認
- `config/daily.yaml` の `max_ideas_per_day` を減らす
- `lookback_years` を短くする（例: 3年 → 1年）

## 設定ファイル

### config/rss_feeds.yaml

RSSフィードのリスト。追加・削除可能。

### config/daily.yaml

主要設定:
- `max_ideas_per_day`: 1日に処理するアイデア数（推奨: 1〜3）
- `backtest.lookback_years`: バックテスト期間（年数）
- `backtest.holding_days`: 保有期間のリスト（営業日）
- `filters.min_score`: アイデアの最低スコア（0〜1）

## セキュリティ注意事項

1. **絶対に.envファイルを作成しない**（.gitignoreで除外済み）
2. **APIキーをコミットしない**
3. **ログやレポートにAPIキーを出力しない**
4. **スクリプト内では os.environ から読み取る**
5. **危険フラグ（--dangerously-*）は使わない**

## 出力要件

### 必須ファイル

- **docs/knowledges/{YYYYMMDD_HHMM}_{topic}.md**: 成功・失敗問わず必ず生成
- **docs/reports/{YYYYMMDD}.md**: 日次レポート（処理0件でも必ず生成）
- **analyses/{YYYYMMDD_HHMM}_{topic}/backtest_metrics.json**: 機械可読な結果

### 任意ファイル

- グラフ（初期は軽量化のため無効）
- Jupyter Notebook（手動分析用）

## データソース

### RSS（6フィード固定）

1. 日経ビジネス
2. PR TIMES
3. JPX ニュースリリース
4. JPX マーケット情報
5. JPX 障害・アラート
6. METI Journal

### J-Quants API

- V2 APIキー方式
- キャッシュ優先（同日再実行でAPIを叩かない）
- レート制限対策あり（リトライ、待機時間）

## 将来拡張

### TODO（現時点では実装しない）

- TDnet（適時開示）連携 → 公式RSSが未確認のため保留
- ベンチマーク（TOPIX）との比較
- セクター別分析
- より長期（10日、20日）の保有期間
- グラフ生成
- Slackへの自動投稿

## 関連ファイル

- `.env.example`: 環境変数のテンプレート
- `requirements.txt`: Python依存関係
- `CLAUDE.md`: リポジトリ規約
