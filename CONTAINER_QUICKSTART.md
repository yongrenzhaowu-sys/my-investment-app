# 🐋 コンテナクイックスタートガイド

セキュアなコンテナ環境で J-Quants 分析を実行するためのクイックリファレンス。

---

## 🚀 最速スタート（3ステップ）

### 1️⃣ イメージをビルド

```bash
bash scripts/run_secure.sh build
```

### 2️⃣ セキュア実行（ネットワーク無効）

```bash
bash scripts/run_secure.sh secure
```

コンテナ内で：
```bash
cd jquants-sector-momo
python backtest_weekly.py --start 2025-12-02 --end 2026-03-02
ls /out/  # 結果を確認
```

### 3️⃣ API呼び出し（ネットワーク有効）

```bash
# .env ファイルを作成
cp .env.example .env
# .env を編集して JQUANTS_API_KEY を入力

# コンテナ起動
bash scripts/run_secure.sh network
```

コンテナ内で：
```bash
cd jquants-sector-momo
python run_pipeline.py --days 60 --top-sectors 3 --top-stocks 10
cat /out/recommended_stocks_*.csv
```

---

## 📋 コマンド一覧

| コマンド | 説明 | ネットワーク |
|---------|------|------------|
| `bash scripts/run_secure.sh build` | イメージをビルド | - |
| `bash scripts/run_secure.sh secure` | セキュア実行 | ❌ 無効 |
| `bash scripts/run_secure.sh network` | API呼び出し可能 | ✅ 有効 |
| `bash scripts/run_secure.sh verify` | セキュリティ検証 | - |

---

## 🛡️ セキュリティ機能

- ✅ **非rootユーザー**: `analyst` (UID 1000)
- ✅ **read-only ルートFS**: `/workspace` は読み取り専用
- ✅ **最小権限**: `cap-drop=ALL`, `no-new-privileges`
- ✅ **ネットワーク原則無効**: デフォルトは `network=none`
- ✅ **tmpfs**: `/tmp` と `/home/analyst/.cache` は tmpfs

---

## 📂 ディレクトリマッピング

| ホスト | コンテナ | 権限 | 用途 |
|-------|---------|------|------|
| `./` | `/workspace` | 🔒 read-only | リポジトリ全体 |
| `./out` | `/out` | ✏️ read-write | 成果物出力 |
| - | `/tmp` | ✏️ tmpfs | 一時ファイル |
| - | `/home/analyst/.cache` | ✏️ tmpfs | Pythonキャッシュ |

---

## ⚠️ よくある落とし穴

### 1. ファイル書き込みエラー

```
OSError: Read-only file system: '/workspace/output.csv'
```

**解決**: `/out` に書き込む
```python
df.to_csv('/out/output.csv')  # ✅ OK
```

### 2. ネットワークエラー

```
ConnectionError: Failed to establish a new connection
```

**解決**: ネットワーク有効モードで起動
```bash
bash scripts/run_secure.sh network
```

### 3. 環境変数が読めない

```
KeyError: 'JQUANTS_API_KEY'
```

**解決**: `.env` ファイルを作成
```bash
cp .env.example .env
# .env を編集して実際のAPIキーを入力
```

---

## 🔍 トラブルシューティング

### イメージサイズが大きい

```bash
# キャッシュなしで再ビルド
docker build --no-cache -t jquants-analysis:secure .
```

### コンテナが起動しない

```bash
# ログを確認
docker logs jquants-analysis

# イメージを検証
docker image inspect jquants-analysis:secure
```

### パフォーマンスが悪い

CPU/メモリ制限を調整（`docker-compose.yml`）：
```yaml
deploy:
  resources:
    limits:
      cpus: '8.0'
      memory: 8G
```

---

## 📚 詳細ドキュメント

完全なガイドは以下を参照：
- **セットアップガイド**: `docs/knowledges/20260304_1430_secure_container_setup.md`
- **Dockerfile**: マルチステージビルド、セキュリティ設定
- **docker-compose.yml**: 簡易起動設定

---

## 🎯 次のステップ

1. ✅ イメージのビルド
2. ✅ セキュリティ検証
3. ✅ バックテスト実行（ネットワーク無効）
4. ✅ 最新データ取得（ネットワーク有効）
5. ✅ 週次リバランスの自動化

---

**セキュリティ注意**: `.env` ファイルは絶対にコミットしない！
