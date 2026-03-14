# Dockerセキュア環境構築・実行セッション

**作成日**: 2026-03-04 15:30
**目的**: Dockerコンテナを利用してより安全な環境で実行できるようにする

---

## ✅ 完了した作業

### 1. 既存のDocker環境確認
以下のファイルが既に準備されていることを確認：
- `Dockerfile`: マルチステージビルド、非rootユーザー、read-only FS
- `docker-compose.yml`: セキュア/ネットワークモード分離
- `scripts/run_secure.sh`: Docker/Podman対応起動スクリプト
- `.env.example`: 環境変数テンプレート
- `.dockerignore`: ビルド最適化・機密情報除外
- `CONTAINER_QUICKSTART.md`: クイックスタートガイド
- `docs/knowledges/20260304_1430_secure_container_setup.md`: 詳細セットアップガイド

### 2. Dockerイメージのビルド
```bash
bash scripts/run_secure.sh build
# または
docker build -t jquants-analysis:secure -f Dockerfile .
```
→ 成功（Python 3.11-slim-bookworm、非root `analyst` ユーザー）

### 3. 環境変数の設定
**問題**: バックテストがローカルデータ使用時でも `JQUANTS_API_KEY` を要求

**解決策**:
- `docker-compose.yml` にダミーAPIキー追加:
  ```yaml
  JQUANTS_API_KEY=dummy-key-for-local-data-only
  ```
- ローカルデータ使用時（`use_api=False`）はAPIを実際には叩かないため安全

### 4. 出力ディレクトリの修正
**問題**: `/workspace` が read-only のため、結果を保存できない

**解決策**:
1. `backtest_weekly.py` を修正:
   - `import os` を追加
   - 出力先を環境変数 `BACKTEST_OUTPUT_DIR` から取得:
     ```python
     reports_dir = Path(os.environ.get("BACKTEST_OUTPUT_DIR", "reports"))
     reports_dir.mkdir(parents=True, exist_ok=True)
     ```
2. `docker-compose.yml` に環境変数追加:
   ```yaml
   BACKTEST_OUTPUT_DIR=/out/reports
   ```
3. `/out` は read-write マウントされているため書き込み可能

### 5. バックテスト実行（成功）
```bash
docker compose run --rm analysis-secure sh -c \
  "cd jquants-sector-momo && python backtest_weekly.py --start 2025-12-02 --end 2026-03-02"
```

**結果**: `out/reports/` に以下が生成:
- `backtest_weekly_3months.json` (6.1KB)
- `backtest_weekly_3months.md` (963B)

---

## 📊 バックテスト結果（3ヶ月、週次リバランス）

| 指標 | 値 | 評価 |
|------|-----|------|
| 累積リターン | +11.58% | ✅ 優秀 |
| 年率換算リターン | +125.67% | ✅ 非常に高い |
| シャープレシオ | 3.55 | ✅ 優秀（1.0以上が良好） |
| 最大ドローダウン | -3.08% | ✅ 低リスク |
| 勝率 | 57.1% | ✅ 良好 |
| 平均週次リターン | +1.62% | ✅ 安定 |
| 週次ボラティリティ | 3.29% | ✅ 適度 |

**リバランス回数**: 7回（期間: 2025-12-02 〜 2026-03-02）
**初期資金**: 1,000,000円
**最終資産**: 1,115,794円

---

## 🛡️ セキュリティ機能（確認済み）

- ✅ **非rootユーザー実行**: `analyst` (UID 1000)
- ✅ **read-only ルートFS**: `/workspace` は読み取り専用
- ✅ **最小権限**: `cap-drop=ALL`, `no-new-privileges`
- ✅ **ネットワーク原則無効**: デフォルトは `network=none`
- ✅ **書き込み制限**: `/out`, `/tmp`, `/home/analyst/.cache` のみ書き込み可
- ✅ **tmpfs**: 一時ファイルはメモリ上（サイズ制限あり）

---

## 🔧 発生した問題と解決策

### 問題1: Git Bashでのパス変換エラー
**症状**:
```
invalid mount path: 'C:/Program Files/Git/tmp'
```

**原因**: Git BashがLinuxパス（`/tmp`）をWindowsパスに自動変換

**解決策**: `docker compose` を使用（推奨）

### 問題2: APIキー要求エラー
**症状**:
```
ValueError: 環境変数 JQUANTS_API_KEY が設定されていません。
```

**原因**: `JQuantsDataProvider()` 初期化時に必ずAPIキーを要求

**解決策**: ダミーAPIキーを環境変数に設定（`use_api=False` 時はAPIを叩かない）

### 問題3: Read-only file system エラー
**症状**:
```
OSError: [Errno 30] Read-only file system: 'reports/...'
```

**原因**: `/workspace` が read-only マウント

**解決策**: 出力先を `/out/reports` に変更（環境変数経由）

---

## 📁 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `docker-compose.yml` | `JQUANTS_API_KEY` と `BACKTEST_OUTPUT_DIR` 追加 |
| `jquants-sector-momo/backtest_weekly.py` | `import os` 追加、出力先を環境変数から取得 |

---

## 📚 次のステップ

### 1. ネットワーク有効モードでAPI呼び出しテスト
最新データを取得する場合：

```bash
# .env ファイルを作成
cp .env.example .env
# .env を編集して実際のAPIキーを入力

# コンテナ起動
docker compose run --rm analysis-network

# コンテナ内で実行
cd jquants-sector-momo
python run_pipeline.py --days 60 --top-sectors 3 --top-stocks 10
cat /out/recommended_stocks_*.csv
```

### 2. run_pipeline.py の出力先修正
`run_pipeline.py` も同様に、出力先を `/out/` に変更する必要がある可能性あり

### 3. FutureWarning の修正
```python
# 修正前
group["DailyRet"] = group["AdjC"].pct_change()

# 修正後
group["DailyRet"] = group["AdjC"].pct_change(fill_method=None)
```
場所: `jquants-sector-momo/src/momo/strategies/sector_momentum.py:100`

### 4. 定期実行の自動化
Docker Compose + タスクスケジューラーで週次リバランスを自動化

### 5. docker-compose.yml のバージョン警告修正
```yaml
# 削除
version: '3.8'
```
最新のDocker Composeでは `version` は不要

---

## 🔗 関連ドキュメント

- **クイックスタート**: `CONTAINER_QUICKSTART.md`
- **詳細ガイド**: `docs/knowledges/20260304_1430_secure_container_setup.md`
- **セッション記録**: `docs/sessions/20260304_1430_secure_container_complete.md`（前回）
- **プロジェクト規約**: `CLAUDE.md`

---

## 💡 重要な教訓

1. **コンテナ設計の原則**: read-only ルートFS + 限定的な書き込み領域で安全性を確保
2. **環境変数の活用**: ダミー値でも、オフライン時のエラー回避に有効
3. **出力先の設計**: コンテナ環境では出力先を環境変数で制御可能にする
4. **Git Bash vs Docker Compose**: Windowsでは `docker compose` が推奨（パス変換問題を回避）

---

**セッション完了**: 2026-03-04 15:30
**成果**: Dockerコンテナ環境でのバックテスト実行に成功、セキュアな分析環境を確立
