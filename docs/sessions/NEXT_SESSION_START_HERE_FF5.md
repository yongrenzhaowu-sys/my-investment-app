# FF5ローリング分析 - 次回セッション開始ガイド

**最終更新**: 2026-03-19 10:30
**現在の状況**: データ取得完了 ✅、ローリング分析実行中

---

## 📊 現在の状況（2026-03-19 10:30時点）

### データ取得完了 ✅
- **株価データ**: 5,285,728レコード（4,986銘柄、2021-03～2026-03）
- **財務データ**: 91,734レコード（4,375銘柄、2021-03～2026-03）
- **ファイル**: `data/processed/jquants_historical_6years/`

### ローリング分析タスク（実行中）
- **タスクID**: `bf44930`
- **開始時刻**: 2026-03-19 10:25
- **推定完了時刻**: 2026-03-19 10:55（約30分）

### 途中保存状況（正常動作中）
```
✅ 100日目: 394,528レコード
✅ 200日目: 778,835レコード
✅ 300日目: 1,171,102レコード
✅ 400日目: 1,564,958レコード
✅ 500日目: 1,953,601レコード
✅ 600日目: 2,357,939レコード
```

**途中保存ファイル**: `data/processed/jquants_historical_6years/prices_partial_*.parquet`

---

## 🎯 次回セッション開始時にやること

### ステップ1: ローリング分析タスクの状態を確認

Claudeに以下のように伝えてください：
```
「タスク bf44930 の状態を確認してください」
```

**期待される結果**:
- ✅ 完了（completed） → ステップ2へ
- 🔄 実行中（running） → 完了まで待つ
- ❌ 失敗（failed） → エラー確認、必要なら再実行

---

### ステップ2: ローリング分析結果を確認

```bash
# ローリング分析の結果を確認
cd "C:\Users\yongr\claude project\workspace\analyses\20260318_1800_ff5_rolling_6years"
python -c "
import pandas as pd

# ローリングファクターデータを読み込み
df = pd.read_csv('results/ff5_rolling_factors.csv')

print(f'期間数: {len(df)}')
print(f'期間: {df[\"window_start\"].min()} ~ {df[\"window_end\"].max()}')
print()
print(df.head())
"
```

**期待される結果**:
```
期間数: 約50期間（12ヶ月ローリング）
期間: 2021-03 ~ 2026-03
ファクター: MKT, SMB, HML, RMW, CMA, WML
```

---

### ステップ3: フェーズ3（可視化）を実行

**Claudeに伝えるメッセージ**:
```
「フェーズ3の可視化を実行してください」
```

**実行内容**:
- スクリプト: `visualize_regime_change.py`
- 処理時間: 約5分
- 出力:
  - `results/ff5_rolling_timeseries.png` - 時系列グラフ
  - `results/ff5_rolling_heatmap.png` - ヒートマップ
  - `results/ff5_regime_summary.txt` - 統計サマリー

**Claudeが実行するコマンド**:
```bash
cd "C:\Users\yongr\claude project\workspace\analyses\20260318_1800_ff5_rolling_6years"
python visualize_regime_change.py
```


---

## 📁 重要ファイルパス

### データ
```
data/processed/jquants_historical_6years/
├── daily_bars_2021_2026.parquet          # 株価（5年間）
├── financials_2021_2026.parquet          # 財務（5年間）
├── fetch_progress.json                   # 進捗状態（完了後削除）
└── prices_partial_*.parquet              # 途中保存（完了後削除）
```

### スクリプト
```
analyses/20260318_1800_ff5_rolling_6years/
├── fetch_historical_ff5_data_resumable.py  # データ取得（完了）
├── calculate_ff5_rolling.py                # ローリング分析（次実行）
└── visualize_regime_change.py              # 可視化（最後実行）
```

### ドキュメント
```
docs/sessions/20260318_1800_ff5_rolling_start.md  # 今回のセッション記録
docs/plans/20260318_1800_ff5_rolling_6years/01_plan.md  # 計画書
```

---

## ⚠️ トラブルシューティング

### タスクが失敗している場合

**確認事項**:
1. エラーメッセージを確認
2. 途中保存ファイルが存在するか確認

**対処方法**:
```bash
# 途中保存ファイルを確認
ls "C:\Users\yongr\claude project\workspace\data\processed\jquants_historical_6years\prices_partial_*.parquet"

# 進捗状態を確認
cat "C:\Users\yongr\claude project\workspace\data\processed\jquants_historical_6years\fetch_progress.json"

# 再実行（途中から自動的に再開される）
cd "C:\Users\yongr\claude project\workspace\analyses\20260318_1800_ff5_rolling_6years"
python fetch_historical_ff5_data_resumable.py
```

---

### データが不完全な場合

**対処方法**:
```bash
# 進捗ファイルを削除して最初からやり直し
rm "C:\Users\yongr\claude project\workspace\data\processed\jquants_historical_6years\fetch_progress.json"
rm "C:\Users\yongr\claude project\workspace\data\processed\jquants_historical_6years\prices_partial_*.parquet"

# 再実行
cd "C:\Users\yongr\claude project\workspace\analyses\20260318_1800_ff5_rolling_6years"
python fetch_historical_ff5_data_resumable.py
```

---

## 💡 次回セッションの推奨開始メッセージ

```
「FF5ローリング分析の続きからお願いします。
タスク bf44930（ローリング分析）の状態を確認してください。」
```

これをClaude Codeに伝えれば、自動的に：
1. ローリング分析タスクの状態を確認
2. 完了していれば結果確認 → フェーズ3（可視化）を実行
3. 実行中なら完了を待つ

---

**準備完了！次回セッションでローリング分析を実行できます。**
