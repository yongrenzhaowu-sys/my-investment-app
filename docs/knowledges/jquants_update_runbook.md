# J-Quants データ更新 実行マニュアル

**作成日**: 2026-02-18
**対象**: 日本株OHLCV・財務データの週次更新

---

## 1. 前提条件

### 1.1 環境
- Python 3.x
- 必須ライブラリ: `pandas`, `pyarrow`, `requests`

インストール:
```bash
pip install pandas pyarrow requests
```

### 1.2 認証情報
J-Quants.env にリフレッシュトークンを記載:

```
REFRESH_TOKEN=your_refresh_token_here
```

または環境変数:
```bash
export JQUANTS_REFRESH_TOKEN=your_refresh_token_here
```

### 1.3 ディレクトリ構成
```
workspace/
├── legacy/_inbox/
│   ├── jquants_daily_bars_10y_parquet/  （読み取り専用）
│   └── jquants_fins_summary_10y_parquet/ （読み取り専用）
├── data/
│   ├── raw/jquants/
│   │   ├── prices/
│   │   └── financials/
│   └── curated/jquants/
│       ├── prices/
│       └── financials/
└── scripts/
    ├── ingest/
    │   ├── consolidate_legacy.py
    │   ├── update_jquants_prices.py
    │   └── update_jquants_financials.py
    └── qc/
        └── qc_jquants.py
```

---

## 2. 初回セットアップ

### 2.1 Legacy データ統合（初回のみ）

**目的**: legacy の10年分データを curated に統合

#### Dry-Run（推奨）
```bash
cd "C:\Users\yongr\claude project\workspace"

# 価格データのみ dry-run（最新1ヶ月分）
py scripts/ingest/consolidate_legacy.py --dry-run --prices

# 財務データのみ dry-run
py scripts/ingest/consolidate_legacy.py --dry-run --financials

# 両方 dry-run
py scripts/ingest/consolidate_legacy.py --dry-run
```

#### 本番実行
```bash
# 全期間統合（10年分）
py scripts/ingest/consolidate_legacy.py

# または個別
py scripts/ingest/consolidate_legacy.py --prices
py scripts/ingest/consolidate_legacy.py --financials
```

**結果**:
- `data/curated/jquants/prices/daily_quotes_all.parquet` 作成
- `data/curated/jquants/financials/statements_all.parquet` 作成

**所要時間**: 約5-10分（10年分の場合）

---

### 2.2 差分取得（初回）

Legacy の最終日（2026-01-22）から今日までの差分を取得。

#### Dry-Run
```bash
# 価格データ（1銘柄×直近1週間のみ）
py scripts/ingest/update_jquants_prices.py --dry-run

# 財務データ（1銘柄×直近1ヶ月のみ）
py scripts/ingest/update_jquants_financials.py --dry-run
```

#### 本番実行
```bash
# 価格データ（全銘柄×差分期間）
py scripts/ingest/update_jquants_prices.py

# 財務データ
py scripts/ingest/update_jquants_financials.py
```

**API制限**: 1日5000リクエストまで（通常は十分）

---

### 2.3 QC実行

```bash
# Dry-run（本番と同じ）
py scripts/qc/qc_jquants.py --dry-run

# 本番
py scripts/qc/qc_jquants.py

# 個別
py scripts/qc/qc_jquants.py --prices
py scripts/qc/qc_jquants.py --financials
```

**QCチェック項目**:
- 重複（date, code）
- 欠損値（必須カラム）
- 異常値（close <= 0, volume < 0）
- 日付連続性（7日以上の空白）
- 未来参照（財務のみ）

**エラー時**: スクリプトは終了コード1で停止。ログを確認して修正。

---

## 3. 週次更新（2回目以降）

### 3.1 定期実行スクリプト

週次（例：毎週日曜21時）に以下を実行:

```bash
#!/bin/bash
# update_jquants_weekly.sh

cd "C:\Users\yongr\claude project\workspace"

echo "=== J-Quants 週次更新 ==="
date

# 1. 価格データ更新
echo "価格データ取得..."
py scripts/ingest/update_jquants_prices.py
if [ $? -ne 0 ]; then
    echo "❌ 価格データ取得失敗"
    exit 1
fi

# 2. 財務データ更新
echo "財務データ取得..."
py scripts/ingest/update_jquants_financials.py
if [ $? -ne 0 ]; then
    echo "❌ 財務データ取得失敗"
    exit 1
fi

# 3. QC実行
echo "QC実行..."
py scripts/qc/qc_jquants.py
if [ $? -ne 0 ]; then
    echo "❌ QC失敗"
    exit 1
fi

echo "✅ 週次更新完了"
date
```

### 3.2 手動実行

```bash
# 現在日まで更新
py scripts/ingest/update_jquants_prices.py
py scripts/ingest/update_jquants_financials.py
py scripts/qc/qc_jquants.py
```

### 3.3 特定期間の再取得

```bash
# 例: 2026-02-01 ～ 2026-02-10 を再取得
py scripts/ingest/update_jquants_prices.py \
    --start-date 2026-02-01 \
    --end-date 2026-02-10

py scripts/ingest/update_jquants_financials.py \
    --start-date 2026-02-01 \
    --end-date 2026-02-10
```

---

## 4. トラブルシューティング

### 4.1 認証エラー

**症状**:
```
❌ エラー: 401 Unauthorized
```

**対処**:
1. J-Quants.env のトークンが正しいか確認
2. トークンの有効期限を確認（J-Quantsサイトで再発行）
3. 環境変数 `JQUANTS_REFRESH_TOKEN` を確認

---

### 4.2 API制限エラー

**症状**:
```
❌ エラー: 429 Too Many Requests
```

**対処**:
1. 1日のリクエスト数が5000を超えていないか確認
2. 時間をおいて再実行（翌日まで待つ）
3. dry-runで小規模テスト後、本番実行

---

### 4.3 QC失敗

**症状**:
```
❌ QC失敗: エラーを修正してください
[DUPLICATE] 100 行の重複 (date, code)
```

**対処**:
1. レポートを確認し、エラー内容を特定
2. **重複**: 通常は後勝ちで自動解決。手動削除が必要な場合は curated を編集
3. **欠損**: データソース（API）の問題。J-Quantsサポートに問い合わせ
4. **異常値**: 警告のみなら無視可。エラーなら調査

---

### 4.4 curated が見つからない

**症状**:
```
❌ エラー: Curated data not found
先に consolidate_legacy.py を実行してください。
```

**対処**:
1. `consolidate_legacy.py` を実行（初回のみ）
2. `data/curated/jquants/prices/daily_quotes_all.parquet` が存在することを確認

---

### 4.5 パーティションファイルが見つからない

**症状**:
```
⚠️  パーティションファイルが見つかりません
```

**対処**:
1. legacy ディレクトリが正しいか確認:
   - `legacy/_inbox/jquants_daily_bars_10y_parquet/daily_parquet/`
   - `legacy/_inbox/jquants_fins_summary_10y_parquet/daily_parquet/`
2. パスが存在するか確認:
   ```bash
   ls "C:\Users\yongr\claude project\workspace\legacy\_inbox\jquants_daily_bars_10y_parquet\daily_parquet" | head
   ```

---

### 4.6 3ヶ月超の差分取得

**症状**:
最終更新から3ヶ月以上経過している場合、1リクエストで取得できない。

**対処**:
スクリプトは自動的に3ヶ月ごとに分割して取得。特別な対処不要。

ログ例:
```
API呼び出し: 2025-11-01 ～ 2026-01-30 (全銘柄)
取得: 250,000 行
API呼び出し: 2026-01-31 ～ 2026-02-18 (全銘柄)
取得: 50,000 行
```

---

## 5. データ確認方法

### 5.1 curated データの確認

```python
import pandas as pd

# 価格データ
df_price = pd.read_parquet("data/curated/jquants/prices/daily_quotes_all.parquet")
print(df_price.info())
print(df_price.head())

# 期間確認
print(f"期間: {df_price['date'].min()} ～ {df_price['date'].max()}")
print(f"銘柄数: {df_price['code'].nunique()}")

# 財務データ
df_fin = pd.read_parquet("data/curated/jquants/financials/statements_all.parquet")
print(df_fin.info())
```

### 5.2 raw データの確認

```bash
# 最新の raw ファイル
ls -lth data/raw/jquants/prices/ | head
ls -lth data/raw/jquants/financials/ | head
```

---

## 6. メンテナンス

### 6.1 ディスク容量管理

- **raw**: 週次で古いファイルを削除（1ヶ月以上前）
- **curated**: 削除しない（マスターデータ）

```bash
# raw の1ヶ月以上前のファイルを削除
find data/raw/jquants/ -name "*.parquet" -mtime +30 -delete
```

### 6.2 バックアップ

curated を定期的にバックアップ:

```bash
# 例: 月次バックアップ
cp data/curated/jquants/prices/daily_quotes_all.parquet \
   backups/daily_quotes_all_$(date +%Y%m).parquet
```

---

## 7. コマンド早見表

| 操作 | コマンド |
|------|----------|
| 初回統合（dry-run） | `py scripts/ingest/consolidate_legacy.py --dry-run` |
| 初回統合（本番） | `py scripts/ingest/consolidate_legacy.py` |
| 価格更新（dry-run） | `py scripts/ingest/update_jquants_prices.py --dry-run` |
| 価格更新（本番） | `py scripts/ingest/update_jquants_prices.py` |
| 財務更新（dry-run） | `py scripts/ingest/update_jquants_financials.py --dry-run` |
| 財務更新（本番） | `py scripts/ingest/update_jquants_financials.py` |
| QC実行 | `py scripts/qc/qc_jquants.py` |
| 特定期間再取得 | `py scripts/ingest/update_jquants_prices.py --start-date 2026-01-01 --end-date 2026-01-31` |

---

**問い合わせ先**: docs/sessions/ のサマリを参照

**関連ドキュメント**:
- [計画書](../plans/20260218_1430_jquants_update_pipeline/01_first_plan.md)
- [スキーマ定義](./jquants_legacy_schema.md)
