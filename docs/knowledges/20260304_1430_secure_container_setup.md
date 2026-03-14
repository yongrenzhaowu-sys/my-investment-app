# セキュアなコンテナ環境セットアップガイド

**作成日**: 2026-03-04 14:30
**目的**: J-Quantsプロジェクトを安全に扱うためのコンテナ雛形とセキュリティベストプラクティス

---

## 概要

このプロジェクトでは、以下のセキュリティ原則に基づいたコンテナ環境を提供します：

1. **非rootユーザー実行**: UID/GID 1000 の `analyst` ユーザー
2. **ルートFS read-only**: 可能な限りファイルシステムを読み取り専用に
3. **最小権限**: `cap-drop=ALL` でLinux capabilitiesを全削除
4. **ネットワーク原則無効**: デフォルトは `network=none`、API呼び出し時のみ有効化
5. **依存関係の固定**: `requirements.lock` で再現性を確保

---

## ファイル構成

```
workspace/
├── Dockerfile                      # セキュアなイメージ定義
├── docker-compose.yml              # 簡易起動設定
├── .env.example                    # 環境変数テンプレート
├── scripts/
│   └── run_secure.sh              # 安全な起動スクリプト
└── docs/knowledges/
    └── 20260304_1430_secure_container_setup.md  # 本ガイド
```

---

## クイックスタート

### 1. イメージのビルド

```bash
# Docker の場合
docker build -t jquants-analysis:secure -f Dockerfile .

# または、スクリプト経由
bash scripts/run_secure.sh build
```

### 2. セキュア実行（ネットワーク無効）

バックテスト・分析など、外部通信が不要な作業：

```bash
# スクリプト経由（推奨）
bash scripts/run_secure.sh secure

# または、直接実行
docker run --rm -it \
  --read-only \
  --network none \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  --mount type=bind,source="$(pwd)",target=/workspace,readonly \
  --mount type=bind,source="$(pwd)/out",target=/out \
  --mount type=tmpfs,target=/tmp,tmpfs-size=512M \
  --mount type=tmpfs,target=/home/analyst/.cache,tmpfs-size=256M \
  jquants-analysis:secure
```

### 3. ネットワーク有効実行（API呼び出し用）

J-Quants APIからデータ取得が必要な場合：

```bash
# .env ファイルを作成
cp .env.example .env
# .env を編集して認証情報を入力

# スクリプト経由（推奨）
bash scripts/run_secure.sh network

# または、docker-compose経由
docker compose run --rm analysis-network
```

---

## セキュリティ検証

### セキュリティ設定の確認

```bash
bash scripts/run_secure.sh verify
```

検証項目：
- 非rootユーザーで実行されているか
- 書き込み可能なディレクトリが限定されているか
- Linux capabilitiesが削除されているか

### 手動検証

コンテナ内で以下を実行：

```bash
# ユーザー確認
whoami  # → analyst
id      # → uid=1000(analyst) gid=1000(analyst)

# 書き込み可能ディレクトリの確認
find / -type d -writable 2>/dev/null
# → /tmp, /out, /home/analyst/.cache のみであるべき

# ルートFSへの書き込み試行（失敗するはず）
touch /test.txt  # → Read-only file system

# ネットワーク確認（secure モード）
ping 8.8.8.8  # → Network is unreachable
```

---

## よくある落とし穴と対処法

### 1. ❌ `.env` ファイルをコミットしてしまう

**リスク**: 認証情報がGitHub等に漏洩

**対処**:
- `.gitignore` で `.env` を除外済み（再確認）
- `.env.example` のみをコミット（値は空）
- コミット前に `git status` で確認

### 2. ❌ ルートFSへの書き込みエラー

**症状**:
```
OSError: [Errno 30] Read-only file system: '/workspace/output.csv'
```

**原因**: `/workspace` は read-only マウント

**対処**:
```python
# ❌ 間違い
df.to_csv('/workspace/output.csv')

# ✅ 正しい
df.to_csv('/out/output.csv')  # /out は書き込み可能
```

### 3. ❌ ネットワークが必要なのに `network=none`

**症状**:
```
ConnectionError: Failed to establish a new connection
```

**原因**: デフォルトはネットワーク無効

**対処**:
```bash
# ネットワーク有効モードで起動
bash scripts/run_secure.sh network
```

### 4. ❌ 一時ファイルが `/tmp` に書き込めない

**症状**:
```
OSError: [Errno 28] No space left on device: '/tmp/...'
```

**原因**: tmpfs のサイズ制限（デフォルト512MB）

**対処**:
```bash
# tmpfs サイズを増やして起動
docker run ... --mount type=tmpfs,target=/tmp,tmpfs-size=2G ...
```

### 5. ❌ 依存関係のバージョン不一致

**症状**:
```
ImportError: cannot import name 'xxx' from 'yyy'
```

**原因**: requirements.txt のバージョン指定が緩い（`>=`）

**対処**:
```bash
# コンテナ内で固定バージョンを確認
cat /opt/venv/requirements.lock

# 必要に応じて requirements.txt を厳密に
pandas==2.1.4  # >= ではなく ==
```

### 6. ❌ Windows環境でのパス問題

**症状**:
```
Error: invalid mount config for type "bind": invalid mount path
```

**原因**: Windows パス（`C:\...`）がそのまま使用されている

**対処**:
```bash
# WSL2 内から実行
cd /mnt/c/Users/yongr/claude\ project/workspace
bash scripts/run_secure.sh secure

# または、Git Bash で実行
# パスは自動変換される
```

---

## 使用例

### バックテスト実行（ネットワーク不要）

```bash
# セキュアモードで起動
bash scripts/run_secure.sh secure

# コンテナ内で実行
cd jquants-sector-momo
python backtest_weekly.py --start 2025-12-02 --end 2026-03-02

# 結果は /out に保存
ls /out/
```

### 最新データ取得（ネットワーク必要）

```bash
# ネットワーク有効モードで起動
bash scripts/run_secure.sh network

# コンテナ内で実行
cd jquants-sector-momo
python run_pipeline.py --days 60 --top-sectors 3 --top-stocks 10

# 結果は /out に保存
cat /out/recommended_stocks_*.csv
```

### 依存関係の更新

```bash
# ネットワーク有効モードで起動
bash scripts/run_secure.sh network

# コンテナ内で依存関係を更新（read-only なので pip install は不可）
# 代わりに、ホスト側で requirements.txt を更新してイメージを再ビルド

# ホスト側で：
echo "new-package==1.2.3" >> requirements.txt
docker build -t jquants-analysis:secure -f Dockerfile .
```

---

## Docker Compose の使用

### 基本的な使い方

```bash
# セキュアモード（ネットワーク無効）
docker compose run --rm analysis-secure

# ネットワーク有効モード
docker compose run --rm analysis-network

# バックグラウンド実行
docker compose up -d analysis-secure
docker compose logs -f analysis-secure
docker compose down
```

### カスタマイズ

`docker-compose.yml` を編集してリソース制限を調整：

```yaml
deploy:
  resources:
    limits:
      cpus: '8.0'      # CPU制限を緩和
      memory: 8G       # メモリ制限を緩和
```

---

## トラブルシューティング

### イメージがビルドできない

```bash
# キャッシュをクリアして再ビルド
docker build --no-cache -t jquants-analysis:secure -f Dockerfile .

# ビルドログを詳細表示
docker build --progress=plain -t jquants-analysis:secure -f Dockerfile .
```

### コンテナが起動しない

```bash
# イメージの検証
docker image inspect jquants-analysis:secure

# コンテナログの確認
docker logs jquants-analysis
```

### パフォーマンスが悪い

```bash
# リソース使用状況を確認
docker stats jquants-analysis

# CPU/メモリ制限を緩和
docker run ... --cpus 8.0 --memory 8g ...
```

---

## セキュリティチェックリスト

コンテナ実行前に以下を確認：

- [ ] `.env` ファイルが `.gitignore` に含まれている
- [ ] `.env` ファイルに実際の認証情報が入力されている（network モード時）
- [ ] イメージが最新（`docker build` 済み）
- [ ] ネットワークモードが適切（secure または network）
- [ ] 出力ディレクトリ `/out` がホストにマウントされている
- [ ] 一時ファイル用 tmpfs が設定されている
- [ ] セキュリティオプションが有効（`no-new-privileges`, `cap-drop=ALL`）

---

## 参考資料

### Docker セキュリティベストプラクティス
- [Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)

### 関連ドキュメント
- `CLAUDE.md`: プロジェクト全体の規約
- `.gitignore`: 機密情報の除外設定
- `requirements.txt`: 依存関係の定義

---

## 次のステップ

1. **イメージのビルド**: `bash scripts/run_secure.sh build`
2. **セキュリティ検証**: `bash scripts/run_secure.sh verify`
3. **バックテスト実行**: セキュアモードで過去データを分析
4. **最新データ取得**: ネットワークモードでAPI呼び出し

---

## 更新履歴

- **2026-03-04 14:30**: 初版作成
  - Dockerfile（マルチステージビルド、非root、read-only）
  - docker-compose.yml（セキュア/ネットワークモード分離）
  - run_secure.sh（Docker/Podman対応スクリプト）
  - .env.example（認証情報テンプレート）
  - 本ガイド（セットアップ手順、落とし穴、トラブルシューティング）
