# 計画: 財務データの完全取得（CMAファクター計算のため）

**作成日**: 2026-03-18 16:00
**推定工数**: 1時間
**優先度**: 高（FF5分析の完全性のため）

---

## 🎯 目標

2025-08-01 ~ 2026-03-15の財務データを取得し、CMAファクター（投資ファクター）を計算する。

---

## 📊 現状分析

### 既存データの状況
- **ファイル**: `data/processed/jquants_latest_full/financials_full.parquet`
- **件数**: 5,879件
- **期間**: 2025-03-03 ~ 2025-07-25
- **不足期間**: 2025-07-26 ~ 2026-03-15（約7.5ヶ月）

### 問題点
- CMAファクター（投資ファクター）が計算できない（0%のまま）
- RMW、HMLファクターの精度が不十分

---

## 🔧 実装方針

### ステップ1: データ取得スクリプト作成

**ファイル**: `analyses/20260315_1600_jquants_latest_ff5/fetch_financials_completion.py`

**仕様**:
- J-Quants API V2の `/v2/fins/summary` を使用
- 期間: 2025-07-26 ~ 2026-03-15
- レート制限対策: 1日あたり100リクエスト程度で429エラー
- 実装: 日付ごとに順次取得、エラー時はスリープして再試行

**擬似コード**:
```python
import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# 既存データを読み込み
existing_df = pd.read_parquet('data/processed/jquants_latest_full/financials_full.parquet')

# 取得期間
start_date = '2025-07-26'
end_date = '2026-03-15'

# 日付リストを生成
date_range = pd.date_range(start=start_date, end=end_date, freq='D')

new_records = []
request_count = 0

for date in date_range:
    date_str = date.strftime('%Y-%m-%d')

    # APIリクエスト
    url = f'https://api.jquants.com/v2/fins/summary'
    params = {'date': date_str}
    headers = {'x-api-key': API_KEY}

    response = requests.get(url, params=params, headers=headers)
    request_count += 1

    if response.status_code == 200:
        data = response.json().get('data', [])
        new_records.extend(data)
        print(f'{date_str}: {len(data)}件取得')
    elif response.status_code == 429:
        print(f'レート制限に到達。60秒待機...')
        time.sleep(60)
    else:
        print(f'{date_str}: エラー {response.status_code}')

    # レート制限対策: 100リクエストごとに休憩
    if request_count % 100 == 0:
        print(f'{request_count}リクエスト完了。60秒休憩...')
        time.sleep(60)
    else:
        time.sleep(1)  # 通常は1秒待機

# 新規データをDataFrameに変換
new_df = pd.DataFrame(new_records)

# 既存データと結合
combined_df = pd.concat([existing_df, new_df], ignore_index=True)

# 重複削除
combined_df = combined_df.drop_duplicates(subset=['Code', 'DiscDate', 'CurPerEn'])

# 保存
combined_df.to_parquet('data/processed/jquants_latest_full/financials_full.parquet')
print(f'完了: {len(combined_df)}件（+{len(new_df)}件）')
```

---

### ステップ2: データ取得の実行

**注意点**:
- J-Quants APIのレート制限に注意
- 100リクエストごとに60秒休憩
- 取得期間: 約250日分 → 約2.5時間の実行時間
- 途中でエラーが出た場合は、進捗を保存して再開できるようにする

**実行コマンド**:
```bash
cd "C:\Users\yongr\claude project\workspace\analyses\20260315_1600_jquants_latest_ff5"
python fetch_financials_completion.py
```

---

### ステップ3: FF5ファクターの再計算

**ファイル**: `analyses/20260315_1600_jquants_latest_ff5/calculate_ff5_momentum_full.py`（既存）

**実行**:
```bash
python calculate_ff5_momentum_full.py
```

**期待される変化**:
- CMAファクターが0% → 実際の値に変化
- RMW、HMLファクターの精度向上

---

## 📈 期待される成果

### Before（現在）
```
Factor  AnnualReturn  SharpeRatio
WML      0.329394     1.982799
MKT      0.229083     1.431460
CMA      0.000000     0.000000  ← 計算不可
RMW     -0.027789    -0.545616
HML     -0.056500    -1.024611
SMB     -0.165519    -1.540717
```

### After（期待）
```
Factor  AnnualReturn  SharpeRatio
WML      0.329394     1.982799  （変化なし）
MKT      0.229083     1.431460  （変化なし）
CMA      ???          ???       ← 計算可能に
RMW      ???          ???       （精度向上）
HML      ???          ???       （精度向上）
SMB     -0.165519    -1.540717  （変化なし）
```

---

## ⚠️ リスクと対策

### リスク1: レート制限エラー（429）
**対策**: 100リクエストごとに60秒休憩

### リスク2: 実行時間が長い
**対策**:
- バックグラウンドで実行
- 進捗を定期的にログ出力
- 途中保存機能を実装

### リスク3: データ品質の問題
**対策**:
- 取得後にデータを検証（欠損値、異常値チェック）
- 既存データとの整合性確認

---

## 📁 成果物

### スクリプト
- `analyses/20260315_1600_jquants_latest_ff5/fetch_financials_completion.py`

### データ
- `data/processed/jquants_latest_full/financials_full.parquet`（更新）
  - 件数: 5,879件 → 約10,000件（予想）
  - 期間: 2025-03-03 ~ 2026-03-15

### 分析結果
- `analyses/20260315_1600_jquants_latest_ff5/ff5_momentum_factors_full.csv`（更新）
- `analyses/20260315_1600_jquants_latest_ff5/ff5_momentum_ranking_full.csv`（更新）

---

## 🎓 学び

### J-Quants API V2のレート制限
- 実測値: 100リクエスト/日程度で429エラー
- 推奨: 1リクエスト/秒、100リクエストごとに60秒休憩

### 財務データの取得
- エンドポイント: `/v2/fins/summary`
- パラメータ: `date=YYYY-MM-DD`（開示日）
- レスポンス: `{"data": [...]}`形式

---

## 📚 参考資料

- `docs/knowledges/20260311_1800_jquants_api_v2_complete.md` - J-Quants API V2完全ガイド
- `docs/sessions/20260315_1600_jquants_ff5_momentum_full.md` - 前回のFF5分析
- `docs/sessions/NEXT_FF5_ANALYSIS_SESSION.md` - 次回タスク一覧

---

計画作成完了！次はスクリプト実装に進みます。
