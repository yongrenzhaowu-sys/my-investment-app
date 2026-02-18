# データ更新手順（How-to）

**作成日**: 2026-02-18 18:00
**更新日**: 2026-02-18 18:30
**対象**: J-Quants API V2から日足データと財務データを定期的に更新
**スクリプト**: `scripts/fetch_jquants_data.py`（V2 APIキー方式）

---

## 🎯 概要

- **目的**: J-Quants API V2から最新の日足データと財務データを取得
- **保存先**: `data/fetched/`（legacy/_inboxは原本として保持）
- **更新頻度**: 週次または必要な時に手動実行（推奨）
- **認証方式**: APIキー（V2形式）

---

## 📋 前提条件

### 1. 必須パッケージ
以下のPythonパッケージがインストールされていることを確認：

```bash
pip install pandas pyarrow requests python-dotenv
```

### 2. .env ファイル
`legacy/_inbox/.env` に以下が設定されていること：

```
JQUANTS_API_KEY=your_api_key_here
```

**APIキーの取得方法**:
1. J-Quantsの管理画面にログイン: https://application.jpx-jquants.com/
2. 「API設定」→「API V2」→「APIキー」を確認
3. APIキーをコピーして `.env` に追加

### 3. Python環境
Python 3.8以降が必要。

---

## 🚀 基本的な使い方

### 最も簡単な方法（過去7日分の両方を取得）

```bash
cd "C:\Users\yongr\claude project\workspace"
python scripts/fetch_jquants_data.py
```

これで以下が実行されます：
- 過去7日分の日足データを取得
- 過去7日分の財務データを取得
- `data/fetched/daily_bars/` と `data/fetched/fins_summary/` に保存

---

## 📚 詳細な使い方

### コマンドライン引数

| 引数 | 説明 | デフォルト値 |
|------|------|------------|
| `--data-type` | 取得するデータ種別（`daily`, `fins`, `all`） | `all` |
| `--days` | 過去何日分取得するか | `7` |
| `--start-date` | 開始日（YYYY-MM-DD形式） | 過去7日前 |
| `--end-date` | 終了日（YYYY-MM-DD形式） | 今日 |
| `--plan` | J-Quantsプラン（`Free`, `Light`, `Standard`, `Premium`） | `Standard` |

### 使用例

#### 1. 過去1週間分の日足データのみ取得
```bash
python scripts/fetch_jquants_data.py --data-type daily --days 7
```

#### 2. 過去1ヶ月分の財務データのみ取得
```bash
python scripts/fetch_jquants_data.py --data-type fins --days 30
```

#### 3. 特定期間を指定（2026年1月1日～2月18日）
```bash
python scripts/fetch_jquants_data.py --start-date 2026-01-01 --end-date 2026-02-18
```

#### 4. 最新1日分のみ（毎日実行する場合）
```bash
python scripts/fetch_jquants_data.py --days 1
```

#### 5. Freeプランでレート制限を考慮して実行
```bash
python scripts/fetch_jquants_data.py --plan Free --days 7
```

---

## 📁 保存先とファイル構造

### ディレクトリ構造
```
data/fetched/
├── daily_bars/                  # 日足データ
│   ├── date=2026-02-11.parquet
│   ├── date=2026-02-12.parquet
│   └── ...
├── fins_summary/                # 財務データ
│   ├── disclosed_date=2026-02-11.parquet
│   ├── disclosed_date=2026-02-12.parquet
│   └── ...
└── logs/                        # 実行ログ
    ├── fetch_20260218_180000.log
    └── ...
```

### データ形式
- **parquet形式**: 圧縮効率とクエリ性能に優れる
- **日付ごとに分割**: legacy/_inboxと同じ形式
- **列名互換**: 既存の分析コードがそのまま使える

---

## 🔍 データ確認方法

### Pythonで確認

```python
import pandas as pd
from pathlib import Path

# 日足データ読み込み
daily_file = Path("data/fetched/daily_bars/date=2026-02-18.parquet")
if daily_file.exists():
    df = pd.read_parquet(daily_file)
    print(f"日足データ: {len(df)}銘柄")
    print(df.head())
else:
    print("ファイルが見つかりません")

# 財務データ読み込み
fins_file = Path("data/fetched/fins_summary/disclosed_date=2026-02-18.parquet")
if fins_file.exists():
    df = pd.read_parquet(fins_file)
    print(f"財務データ: {len(df)}件")
    print(df.head())
```

### ファイル数確認（Bash）

```bash
# 日足データのファイル数
ls data/fetched/daily_bars/*.parquet | wc -l

# 財務データのファイル数
ls data/fetched/fins_summary/*.parquet | wc -l

# 最新ファイル確認
ls -lt data/fetched/daily_bars/*.parquet | head -5
```

---

## 📊 データ列名（参考）

### 日足データ（daily_bars）
主要な列（J-Quants APIの仕様により変動する可能性あり）：

| 列名 | 型 | 説明 |
|------|-----|------|
| Code | str | 銘柄コード（4桁） |
| Date | str | 取引日（YYYY-MM-DD） |
| Open | float | 始値 |
| High | float | 高値 |
| Low | float | 安値 |
| Close | float | 終値 |
| Volume | int | 出来高 |
| AdjustmentOpen | float | 調整後始値 |
| AdjustmentHigh | float | 調整後高値 |
| AdjustmentLow | float | 調整後安値 |
| AdjustmentClose | float | 調整後終値 |
| AdjustmentVolume | int | 調整後出来高 |

### 財務データ（fins_summary）
主要な列：

| 列名 | 型 | 説明 |
|------|-----|------|
| Code | str | 銘柄コード（4桁） |
| DisclosedDate | str | 開示日（YYYY-MM-DD） |
| TypeOfDocument | str | 書類種別 |
| TypeOfCurrentPeriod | str | 期間種別（四半期/通期） |
| CurrentPeriodEndDate | str | 決算期末日 |
| NetSales | float | 売上高（百万円） |
| OperatingProfit | float | 営業利益（百万円） |
| OrdinaryProfit | float | 経常利益（百万円） |
| Profit | float | 純利益（百万円） |
| TotalAssets | float | 総資産（百万円） |
| Equity | float | 純資産（百万円） |

---

## ⚠️ トラブルシューティング

### エラー1: `.env ファイルが見つかりません`

**原因**: .env ファイルのパスが間違っている

**解決策**:
```bash
# .env ファイルの存在確認
ls "legacy/_inbox/.env"

# .env が別の場所にある場合、スクリプトの env_path を修正
```

### エラー2: `JQUANTS_API_KEY が .env に設定されていません`

**原因**: .env にAPIキーが設定されていない

**解決策**:
```bash
# .env ファイルを開いて確認
cat "legacy/_inbox/.env"

# JQUANTS_API_KEY=... の行があることを確認
```

### エラー3: `認証エラー（401 Unauthorized）`

**原因**: APIキーが無効または期限切れ

**解決策**:
1. J-Quantsの管理画面（https://application.jpx-jquants.com/）にログイン
2. 「API設定」→「API V2」→「APIキー」で新しいキーを取得
3. .env ファイルを更新

### エラー4: `データなし`（特定日）

**原因**: 該当日が休日または取引停止日

**解決策**:
- 土日・祝日はデータが取得できない（正常動作）
- 営業日のみデータが存在する

### エラー5: `ModuleNotFoundError: No module named 'pandas'`

**原因**: 必須パッケージがインストールされていない

**解決策**:
```bash
pip install pandas pyarrow requests python-dotenv
```

### エラー6: APIレート制限エラー

**原因**: J-Quants APIのレート制限に達した

**解決策**:
- 一度に大量のデータを取得しない
- 日付範囲を小さく分割して実行
- 数時間待ってから再実行

---

## 🔄 定期実行の設定（任意）

### Windows（Task Scheduler）

1. **タスクスケジューラを起動**
   - `taskschd.msc` を実行

2. **新しいタスクを作成**
   - アクション: プログラムの開始
   - プログラム: `python`
   - 引数: `scripts/fetch_jquants_data.py --days 1`
   - 開始: `C:\Users\yongr\claude project\workspace`

3. **トリガー設定**
   - 毎日 夜21時（市場終了後）等

### Linux/Mac（cron）

```bash
# crontabを編集
crontab -e

# 毎日21時に実行（例）
0 21 * * * cd /path/to/workspace && python scripts/fetch_jquants_data.py --days 1
```

---

## 📝 推奨ワークフロー

### 週次更新（推奨）

**毎週月曜日に実行**（前週分のデータを取得）

```bash
cd "C:\Users\yongr\claude project\workspace"
python scripts/fetch_jquants_data.py --days 7
```

**メリット**:
- APIレート制限に余裕
- 手動実行で制御しやすい
- エラー発生時に気づきやすい

### 月次更新

**毎月初に実行**（前月分のデータを取得）

```bash
python scripts/fetch_jquants_data.py --days 30
```

### 日次更新（上級者向け）

**毎日夜21時に自動実行**（Task Scheduler / cron）

```bash
python scripts/fetch_jquants_data.py --days 1
```

---

## 🔗 既存データとの統合

### パターン1: data/fetched/ を単独利用

```python
import pandas as pd
import glob

# data/fetched/ の日足データを読み込み
files = glob.glob("data/fetched/daily_bars/*.parquet")
df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

print(f"総レコード数: {len(df):,}")
```

### パターン2: legacy/_inbox と data/fetched/ を結合

```python
import pandas as pd
import glob

# legacy/_inbox の日足データ
legacy_files = glob.glob("legacy/_inbox/jquants_daily_bars_10y_parquet/daily_parquet/*.parquet")
df_legacy = pd.concat([pd.read_parquet(f) for f in legacy_files], ignore_index=True)

# data/fetched/ の日足データ
fetched_files = glob.glob("data/fetched/daily_bars/*.parquet")
df_fetched = pd.concat([pd.read_parquet(f) for f in fetched_files], ignore_index=True)

# 結合（重複除去）
df_all = pd.concat([df_legacy, df_fetched], ignore_index=True)
df_all = df_all.drop_duplicates(subset=['Code', 'Date'], keep='last')

print(f"統合後: {len(df_all):,}行")
```

### パターン3: data/curated/ に統合データを保存

```python
import pandas as pd
import glob

# legacy/_inbox と data/fetched/ を結合
legacy_files = glob.glob("legacy/_inbox/jquants_daily_bars_10y_parquet/daily_parquet/*.parquet")
fetched_files = glob.glob("data/fetched/daily_bars/*.parquet")

df_all = pd.concat(
    [pd.read_parquet(f) for f in legacy_files + fetched_files],
    ignore_index=True
)

# 重複除去
df_all = df_all.drop_duplicates(subset=['Code', 'Date'], keep='last')

# 日付でソート
df_all = df_all.sort_values(['Code', 'Date']).reset_index(drop=True)

# data/curated/ に保存
df_all.to_parquet("data/curated/daily_bars_all.parquet", engine="pyarrow", index=False)

print(f"統合完了: {len(df_all):,}行")
print(f"保存先: data/curated/daily_bars_all.parquet")
```

---

## ❓ FAQ

### Q1: どのくらいの頻度で更新すべきか？

**A**: **週次更新（推奨）**

- 毎週月曜日に前週分（7日分）を取得
- APIレート制限に余裕があり、安定
- 手動実行で制御しやすい

### Q2: data/fetched/ と legacy/_inbox の違いは？

**A**:

| 項目 | legacy/_inbox | data/fetched/ |
|------|--------------|--------------|
| 役割 | 原本（2016-2026/01） | 最新データ（2026/02～） |
| 更新 | なし（読み取り専用） | 定期的に更新 |
| 削除 | 禁止 | 必要に応じて削除可 |

### Q3: データが重複した場合は？

**A**: `drop_duplicates()` で重複除去

```python
df = df.drop_duplicates(subset=['Code', 'Date'], keep='last')
```

### Q4: 過去10年分を再取得したい場合は？

**A**: 時間がかかるため、分割実行を推奨

```bash
# 2016年分
python scripts/fetch_jquants_data.py --start-date 2016-01-01 --end-date 2016-12-31

# 2017年分
python scripts/fetch_jquants_data.py --start-date 2017-01-01 --end-date 2017-12-31

# ...
```

または、legacy/_inbox のデータを利用（既にある）。

---

**最終更新**: 2026-02-18 18:00
**次回更新**: スクリプト改善時、またはユーザーからのフィードバック反映時
