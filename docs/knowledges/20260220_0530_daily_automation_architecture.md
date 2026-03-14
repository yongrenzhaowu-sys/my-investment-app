# 知見: 日次自動化システムのアーキテクチャ

生成日時: 2026-02-20 05:30

---

## 概要

RSSフィードから投資アイデアを抽出し、J-Quants APIで日本株データを取得してバックテストを実行する
日次自動化システムの設計と実装に関する知見。

## システムの目的

1. **自動化**: 人手を介さず、RSSから投資アイデアを日次で抽出・分析
2. **知見蓄積**: 成功・失敗問わず、すべての分析結果をdocs/配下に保存
3. **再現性**: 設定ファイルとスクリプトで完全に再現可能
4. **安全性**: 秘密情報は環境変数のみ、危険な操作は禁止

## アーキテクチャの特徴

### 1. docs中心運用（作業の記憶を外部化）

**課題**: 
- 分析結果が散在すると、過去の知見を活用できない
- Plan mode標準保存に頼ると、ファイルの所在が不明確

**解決策**:
- すべての計画を `docs/plans/` に保存
- すべてのセッション要約を `docs/sessions/` に保存
- すべての知見を `docs/knowledges/` に保存
- すべての日次レポートを `docs/reports/` に保存

**効果**:
- 参照優先順位が明確（まず docs/knowledges → 直近 docs/reports）
- 広範囲スキャンが不要（必要時のみ、事前に範囲を宣言）

### 2. キャッシュ優先（APIコスト削減）

**課題**:
- J-Quants APIには利用制限がある
- 同日に複数回実行すると、同じデータを重複取得してしまう

**解決策**:
- `data/raw/jquants/{YYYYMMDD}/` にキャッシュ保存
- 同日再実行時はキャッシュから読み込み
- 30日経過したキャッシュは自動削除

**実装**:
```python
def get_cached_or_fetch(client, code, from_date, to_date, force_fetch=False):
    today = datetime.now().strftime("%Y%m%d")
    if not force_fetch:
        cached_df = load_from_cache(code, today)
        if cached_df is not None:
            return cached_df
    df = client.get_daily_quotes(code, from_date, to_date)
    save_to_cache(code, today, df)
    return df
```

**効果**:
- APIコール数を大幅削減
- デバッグ時の再実行が高速化

### 3. イベントスタディ型バックテスト

**課題**:
- 従来のポートフォリオ型バックテストは複雑で検証が難しい
- RSSニュースの短期的影響を測定したい

**解決策**:
- 公開日（t日）起点で、翌営業日（t+1日）の寄りで購入
- 1日、3日、5日後の累積リターンを計算
- ベンチマークとの比較（今後実装）

**実装のポイント**:
```python
# イベント日 = 公開日の翌営業日
event_date = pub_dt + timedelta(days=1)

# 保有期間リターンを計算
returns = df.loc[event_idx:event_idx + holding_days, "Returns"].values[1:]
cumulative_return = (1 + returns).prod() - 1
```

**効果**:
- シンプルで検証が容易
- 短期的なニュース効果を定量化

### 4. セキュリティ優先（環境変数のみ）

**課題**:
- .envファイルを誤ってコミットするリスク
- APIキーがログやレポートに混入するリスク

**解決策**:
- .envファイルは一切使用しない（.env.exampleのみ）
- Windows環境変数から `os.environ` で読み取る
- APIキーの値は絶対にprintしない

**実装**:
```python
def get_api_key() -> str:
    api_key = os.environ.get("JQUANTS_API_KEY")
    if not api_key:
        raise ValueError("JQUANTS_API_KEY environment variable is not set")
    logger.info("J-Quants API key loaded from environment variable")  # 値は出さない
    return api_key
```

**効果**:
- 誤コミットのリスクを完全に排除
- セキュリティインシデントの予防

## データフロー

```
[RSS Feeds (6件)]
    ↓ fetch_all_feeds()
[data/raw/rss/{YYYYMMDD}/*.json]
    ↓ extract_ideas_from_all_feeds()
[投資アイデア (証券コード + スコア)]
    ↓ add_ideas_to_queue()
[analyses/00_to_be_started/ideas.jsonl]
    ↓ select_top_ideas(max_count=1)
[選択されたアイデア (1件)]
    ↓ create_analysis_directory()
[analyses/{YYYYMMDD_HHMM}_{topic}/]
    ↓ get_cached_or_fetch() × 銘柄数
[価格データ (DataFrame)]
    ↓ run_event_study()
[バックテスト結果]
    ↓ save_backtest_results(), generate_knowledge_file(), generate_daily_report()
[成果物]
  - backtest_metrics.json
  - docs/knowledges/{timestamp}_{topic}.md
  - docs/reports/{YYYYMMDD}.md
```

## モジュール構成

### src/rss/
- **fetch.py**: RSSフィード取得、feedparserを使用

### src/ideas/
- **extract.py**: 証券コード抽出（正規表現）、スコアリング（キーワードベース）
- **queue.py**: JSONL形式のキュー管理、重複排除

### src/jquants/
- **auth.py**: 環境変数からAPIキー取得
- **client.py**: J-Quants API V2クライアント、リトライ・レート制限対策

### src/data/
- **cache.py**: JSONファイルによるキャッシュ管理

### src/backtest/
- **event_study.py**: イベントスタディ型バックテスト、リターン計算

### src/reporting/
- **daily_report.py**: Markdown形式の日次レポート生成

### src/knowledges/
- **write_knowledge.py**: 知見ファイル生成（必須項目テンプレート）

## 設定ファイル

### config/rss_feeds.yaml
- RSSフィードのリスト（6件固定）
- 将来拡張（TDnet）はTODOとして記載

### config/daily.yaml
- max_ideas_per_day: 1
- lookback_years: 3
- holding_days: [1, 3, 5]
- benchmark: "TOPIX"
- filters: min_score, exclude_keywords

## 学びと改善案

### 成功パターン

1. **docs中心運用が効果的**
   - ファイルの所在が明確で、参照が容易
   - Git管理により変更履歴も追跡可能

2. **キャッシュ優先でコスト削減**
   - APIコール数を大幅削減
   - 開発・デバッグが高速化

3. **イベントスタディがシンプル**
   - ポートフォリオ型より検証が容易
   - 短期的効果の測定に適している

### 課題と改善案

1. **証券コード抽出の精度**
   - 現在: 4桁数字を単純に抽出
   - 課題: 年号（2024等）や電話番号を誤検出
   - 改善案: 前後の文脈チェック（「コード」「銘柄」等）

2. **スコアリングロジック**
   - 現在: キーワード出現回数でスコアリング
   - 課題: 文脈を考慮していない
   - 改善案: 自然言語処理（感情分析、固有表現抽出）

3. **ベンチマーク比較**
   - 現在: 実装されていない
   - 改善案: TOPIXとの超過リターンを計算

4. **セクター分析**
   - 現在: 全銘柄を一律に扱う
   - 改善案: セクター別の傾向分析

## 再実行コマンド

```bash
# 日次実行
python scripts/daily_run.py

# 環境変数確認
echo %JQUANTS_API_KEY%

# ログ確認
type logs\daily_run.log

# キャッシュクリーンアップ（手動）
python -c "from src.data.cache import cleanup_old_cache; cleanup_old_cache(7)"
```

## 参考資料

- CLAUDE.md: リポジトリ規約
- docs/plans/20260220_0530_daily_automation/01_first_plan.md: 実装計画
- docs/sessions/20260220_0530_daily_automation_implementation.md: セッション要約
