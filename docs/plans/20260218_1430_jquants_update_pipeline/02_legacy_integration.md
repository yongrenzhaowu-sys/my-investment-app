# 計画更新：Legacy データ統合

**更新日**: 2026-02-18 14:45
**変更理由**: legacy/_inbox に既存10年分データを発見、これを活用する方向に修正

---

## 1. Legacy データ確認結果

### 1.1 既存データパス
```
legacy/_inbox/jquants_daily_bars_10y_parquet/daily_parquet/
├─ date=2016-01-15.parquet
├─ ...
└─ date=2026-01-22.parquet （最新）

legacy/_inbox/jquants_fins_summary_10y_parquet/daily_parquet/
├─ date=2016-01-15.parquet
├─ ...
└─ date=2026-01-09.parquet （最新）
```

### 1.2 現状ギャップ
| データ種別 | Legacy最終日 | 今日 | 差分日数 |
|-----------|-------------|------|---------|
| 価格（OHLCV） | 2026-01-22 | 2026-02-18 | 約27日 |
| 財務 | 2026-01-09 | 2026-02-18 | 約40日 |

### 1.3 データ形式
- **パーティション**: 日付別（`date=YYYY-MM-DD.parquet`）
- **フォーマット**: Parquet
- **特徴**: 各ファイルは1日分の全銘柄データを含む

---

## 2. 修正後のデータフロー

### 2.1 初回実行（data/curated未作成時）

```
[legacy/_inbox/jquants_daily_bars_10y_parquet] （読み取り専用）
    ↓ （全ファイルを読み込み統合）
[scripts/ingest/consolidate_legacy.py]
    ↓
data/curated/jquants/prices/daily_quotes_all.parquet （2016-01-15 ～ 2026-01-22）

同時に
[J-Quants API] （2026-01-23 ～ 2026-02-18）
    ↓
[scripts/ingest/update_jquants_prices.py]
    ↓
data/raw/jquants/prices/daily_quotes_20260218.parquet
    ↓
[scripts/qc/qc_jquants.py] （QC後、curatedに追記）
    ↓
data/curated/jquants/prices/daily_quotes_all.parquet （更新）
```

### 2.2 2回目以降（週次更新）

```
[data/curated/jquants/prices/daily_quotes_all.parquet]
    ↓ （最終日を取得： max(Date)）
[scripts/ingest/update_jquants_prices.py]
    ↓ （最終日+1 ～ 今日を取得）
[J-Quants API]
    ↓
data/raw/jquants/prices/daily_quotes_YYYYMMDD.parquet
    ↓
[scripts/qc/qc_jquants.py]
    ↓ （QC後、curatedに追記）
data/curated/jquants/prices/daily_quotes_all.parquet （更新）
```

---

## 3. 実装変更点

### 3.1 新規追加ファイル
- **scripts/ingest/consolidate_legacy.py**
  - legacy/_inbox のパーティションファイルを全読み込み
  - 統合して data/curated/jquants/ に保存
  - 初回のみ実行（curated存在時はスキップ）

### 3.2 修正ファイル
1. **scripts/ingest/update_jquants_prices.py**
   - 最終日の判定ロジック追加：
     - `data/curated/jquants/prices/daily_quotes_all.parquet` の max(Date) を取得
     - 存在しない場合はエラー（先に consolidate_legacy.py 実行を促す）

2. **scripts/ingest/update_jquants_financials.py**
   - 同様に最終日判定ロジック追加

3. **scripts/qc/qc_jquants.py**
   - QC後、curatedへの追記ロジック：
     - 既存curated読み込み
     - 新規raw追加
     - 重複削除（Date, Code でユニーク化）
     - 再保存

---

## 4. 差分更新ロジック詳細

### 4.1 最終日の取得
```python
import pandas as pd

curated_path = "data/curated/jquants/prices/daily_quotes_all.parquet"
if not os.path.exists(curated_path):
    raise FileNotFoundError(
        "Curated data not found. Run consolidate_legacy.py first."
    )

df = pd.read_parquet(curated_path)
last_date = df["Date"].max()  # 例: 2026-01-22
```

### 4.2 差分期間の決定
```python
from datetime import datetime, timedelta

start_date = last_date + timedelta(days=1)  # 2026-01-23
end_date = datetime.now().date()  # 2026-02-18
```

### 4.3 API取得（3ヶ月制約対応）
```python
# 今回は差分1ヶ月程度なので1リクエストで済む
# 将来3ヶ月超の場合はループ分割
response = jquants_client.get_daily_quotes(
    date_from=start_date.strftime("%Y-%m-%d"),
    date_to=end_date.strftime("%Y-%m-%d")
)
```

---

## 5. Legacy データのスキーマ確認（TODO）

**次のステップ**:
- legacy の1ファイル（例: date=2026-01-22.parquet）を読んで、カラム構造を確認
- J-Quants API仕様と比較し、マッピングが必要か判定

**想定カラム（価格）**:
- Date, Code, Open, High, Low, Close, Volume
- AdjustmentFactor, AdjustmentOpen, ..., AdjustmentVolume

**想定カラム（財務）**:
- Date（発表日）, Code, FiscalYear, FiscalQuarter
- NetSales, OperatingProfit, OrdinaryProfit, Profit
- TotalAssets, Equity, EPS, DPS, etc.

---

## 6. 修正後の作成ファイル一覧

### 新規追加
1. **scripts/ingest/consolidate_legacy.py**
   legacy パーティションデータを統合（初回のみ）

### 変更なし（01_first_plan.md から）
2. **scripts/ingest/update_jquants_prices.py**
3. **scripts/ingest/update_jquants_financials.py**
4. **scripts/qc/qc_jquants.py**
5. **docs/knowledges/jquants_update_runbook.md**

---

## 7. 実行手順（修正版）

### 7.1 初回セットアップ
```bash
# 1. Legacy統合（初回のみ）
python scripts/ingest/consolidate_legacy.py --dry-run

# 確認後、本番実行
python scripts/ingest/consolidate_legacy.py

# 2. 差分取得（2026-01-23 ～ 2026-02-18）
python scripts/ingest/update_jquants_prices.py --dry-run
python scripts/ingest/update_jquants_financials.py --dry-run

# 3. QC & 統合
python scripts/qc/qc_jquants.py --dry-run
```

### 7.2 週次更新（2回目以降）
```bash
# consolidate_legacy.py は不要（curated存在時は自動スキップ）
python scripts/ingest/update_jquants_prices.py
python scripts/ingest/update_jquants_financials.py
python scripts/qc/qc_jquants.py
```

---

## 8. 安全制約の再確認

✅ **legacy/_inbox** は**読み取り専用**
  - consolidate_legacy.py は読み込みのみ
  - 編集・移動・削除は一切しない

✅ **data/curated** を新マスターとする
  - legacy は初回統合のソースとしてのみ使用
  - 以降は curated を正として運用

---

## 9. リスク追加

| リスク | 対策 |
|--------|------|
| legacy と API のスキーマ不一致 | consolidate_legacy.py でカラムマッピング実装 |
| legacy に重複データがある | 統合時に (Date, Code) でユニーク化 |
| legacy の日付欠損 | QCで検出、ログ出力（エラーにはしない） |

---

## 10. Next Steps（更新版）

1. ✅ 計画更新（本ドキュメント）
2. ⬜ Legacy データのスキーマ確認
   - date=2026-01-22.parquet を読んでカラム一覧取得
3. ⬜ 修正後のファイル一覧提示 → ユーザー承認
4. ⬜ Dry-Run実装
   - **scripts/ingest/consolidate_legacy.py** （新規）
   - scripts/ingest/update_jquants_prices.py
   - scripts/ingest/update_jquants_financials.py
   - scripts/qc/qc_jquants.py
   - docs/knowledges/jquants_update_runbook.md
5. ⬜ Dry-Run実行・検証
6. ⬜ 本番実行
7. ⬜ docs/sessions/ にサマリ保存

---

**更新者**: Claude Code
**次の作業**: Legacy データのスキーマ確認後、ユーザー承認を取って実装開始
