# FF5ファクターモデル バックテスト

**プロジェクト作成日**: 2026-02-18 16:00
**移植元**: legacy/projects/FF5モデル（1月20日、23日、25日作業中）
**カテゴリ**: FF5系（Fama-French 5ファクターモデル）

---

## 🎯 目的

Fama-French 5ファクター（市場、サイズ、バリュー、収益性、投資）を使った日本株式ポートフォリオ戦略のバックテスト検証。

### 具体的な検証内容
1. FF5ファクター（BM_Ratio, ROE, INV_Growth）によるスコアリングロジックの有効性検証
2. リスクオフロジック（市場DD、3Mトレンド、3Mボラティリティ）の効果検証
3. 出来高フィルター（上位70%）の影響分析
4. 日次バックテストによるパフォーマンス評価（年率リターン、Sharpe、MDD等）

---

## 📥 入力データ

### 必須データ
1. **月次スナップショットデータ** (`month_end_snapshot.parquet`)
   - パス: `C:\Users\yongr\Project\merged_data_all_stocks\factors\month_end_snapshot.parquet`
   - 内容: 月末時点の株価、財務指標、ファクター値
   - カラム:
     - `Code`: 銘柄コード
     - `MonthEnd`: 月末日付
     - `AdjustedClose`: 調整後終値
     - `Vo`: 出来高回転率
     - `MarketCap`: 時価総額
     - `BM_Ratio`: 簿価時価比率（Book-to-Market）
     - `ROE`: 自己資本利益率
     - `INV_Growth`: 投資成長率

2. **日次株価データ** (`merged_parts/*.parquet`)
   - パス: `C:\Users\yongr\Project\merged_data_all_stocks\merged_parts\merged-part-*.parquet`
   - 内容: 全銘柄の日次4本値（調整後）
   - カラム: `Date`, `Code`, `AdjustedClose`

### データ期間
- バックテスト期間: 2016年3月 ～ 2026年1月（約9.86年）
- 月次リバランス

---

## 📤 出力

### 1. バックテスト結果ファイル
- **日次ポートフォリオリターン**: `C:\Users\yongr\Project\merged_data_all_stocks\analysis_daily\daily_portfolio_returns_final.parquet`
  - カラム: `Date`, `RealizedMonthKey`, `port_ret`, `risk_off`, `n_hold`, `cash_ratio`, `cum_ret`, `cum_wealth`, `peak`, `dd`
- **サマリ統計**: `C:\Users\yongr\Project\merged_data_all_stocks\analysis_daily\daily_mdd_summary_final.csv`
- **最新月推奨ポートフォリオ**: `C:\Users\yongr\Project\merged_data_all_stocks\analysis_daily\latest_portfolio_recommendation.csv`

### 2. パフォーマンス指標（analysis_01.ipynb実行結果）
- 累積リターン: **930.16%**
- 年率リターン: **26.69%**
- 年率ボラティリティ: **13.43%**
- Sharpe Ratio (Rf=0): **1.9880**
- 最大ドローダウン（日次）: **-14.28%**（2018-02-14）
- 平均CASH比率: **38.93%**
- リスクオフ発動日数: 839日 / 2410日

---

## 🔧 戦略ロジック

### ステップ1: 月次ポートフォリオ形成（t月末時点）
1. **出来高フィルター**: Vo（出来高回転率）上位70%の銘柄を抽出
2. **ファクターZスコア計算**:
   - `z_BM = zscore(BM_Ratio)`: バリューファクター
   - `z_ROE = zscore(ROE)`: 収益性ファクター
   - `z_INV = zscore(INV_Growth)`: 投資ファクター（逆張り）
3. **総合スコアリング**: `score = z_BM + z_ROE - z_INV`
4. **銘柄選定**: スコア上位20銘柄を選定

### ステップ2: リスクオフ判定（t+1月実現時）
市場環境指標を計算し、以下のいずれかが閾値を超えた場合、全額CASH（リスクオフ）:
- 市場ドローダウン: `mkt_dd <= -13.5%`
- 3ヶ月トレンド: `trend3 <= -2%`
- 3ヶ月ボラティリティ: `vol3 >= 90%ile`

### ステップ3: ポートフォリオ構築
- **リスクオフ**: 100% CASH
- **リスクオン**: 選定20銘柄を等ウェイト（各5%）で保有
  - 単位株制約: 100株単位で購入（端数切り捨て）
  - スリッページ: 0.3%考慮

### ステップ4: 日次パフォーマンス計算
- 月内の日次リターンを計算
- 累積リターン、ドローダウン、Sharpe等を集計

---

## 🔄 再現手順

### 前提条件
1. Python環境（3.13以降推奨）
2. 必須パッケージ:
   ```bash
   pip install pandas numpy pyarrow
   ```
3. データディレクトリが存在すること:
   - `C:\Users\yongr\Project\merged_data_all_stocks\factors\month_end_snapshot.parquet`
   - `C:\Users\yongr\Project\merged_data_all_stocks\merged_parts\*.parquet`

### 実行手順
1. **Jupyter起動**:
   ```bash
   cd "C:\Users\yongr\claude project\workspace\analyses\20260218_1600_ff5_model"
   jupyter notebook
   ```

2. **ノートブック選択**:
   - `analysis_01.ipynb`: 最新版（1月23日、FutureWarning修正済み、最終検証版）
   - `analysis_02.ipynb`: 1月20日版（開発途中）
   - `analysis_03.ipynb`: 1月25日版（中間版）

3. **セル実行**: 上から順に全セル実行（Run All）

4. **出力確認**:
   - コンソール出力: サマリ統計、ワースト5日、最新月推奨ポート
   - ファイル出力: `C:\Users\yongr\Project\merged_data_all_stocks\analysis_daily\`

### 推奨実行順
- 初回: `analysis_01.ipynb`（最新版）で全体像を把握
- 詳細分析: 必要に応じて `analysis_02.ipynb`, `analysis_03.ipynb` で開発履歴を確認

---

## ⚠️ 注意点

### 1. データパス依存
- ハードコードされたパス: `C:\Users\yongr\Project\merged_data_all_stocks`
- 他環境で実行する場合は `OUTPUT_DIR` を修正すること

### 2. 未来参照の禁止（lookahead bias）
- t月末のファクター値は t+1月の売買に使用
- t+1月の市場指標（DD、Trend、Vol）は t+1月初の判定に使用
- 日次リターンは当日終値ベース（翌日寄り約定を想定）

### 3. バックテスト仮定
- **約定タイミング**: t日引け確定 → t+1日寄り約定
- **スリッページ**: 0.3%（買い売り両方）
- **税金**: 20.315%（利確時、損失繰越なし版と繰越あり版が混在）
- **取引単位**: 100株単位（端数は現金残高に）

### 4. リスクオフロジックの妥当性
- 閾値（DD -13.5%、Trend -2%、Vol 90%ile）はカーブフィッティングの可能性あり
- 実運用前に頑健性検証（期間外テスト、パラメータ感度分析）を推奨

### 5. FutureWarning対応
- `analysis_01.ipynb`（1月23日版）でpandas 2.x系のFutureWarningを修正済み
- `groupby().apply()` に `include_groups=False` を追加
- `pct_change(fill_method=None)` でfill_methodを明示的に無効化

### 6. 計算時間
- 初回実行: 約5～10分（全銘柄日次データ読み込みに時間）
- 2回目以降: キャッシュにより高速化（環境依存）

---

## 📊 分析ファイル対応

| ファイル名 | 作成日 | 内容 | 推奨度 |
|-----------|--------|------|--------|
| `analysis_01.ipynb` | 2026-02-08 | 最終検証版（FutureWarning修正、ワースト5日、最新月推奨ポート） | ⭐⭐⭐ |
| `analysis_02.ipynb` | 2026-01-23 | 開発途中版（基本ロジック実装） | ⭐ |
| `analysis_03.ipynb` | 2026-01-29 | 中間版（改良検討中） | ⭐⭐ |

---

## 🚀 次のステップ

### 優先度1（実運用検討）
1. **頑健性検証**:
   - パラメータ感度分析（TOP_N, VO_TOP_PCT, リスクオフ閾値）
   - 期間外テスト（2014-2015年等）
   - モンテカルロシミュレーション

2. **実装準備**:
   - リアルタイムデータ取得モジュール化
   - 自動リバランススクリプト作成

### 優先度2（戦略改善）
3. **ファクター拡張**:
   - Momentum（モメンタム）ファクター追加
   - Quality（質）ファクター追加
   - Sentiment（センチメント）ファクター検討

4. **リスク管理強化**:
   - ポジションサイズ調整（Kelly基準等）
   - セクター分散制約
   - 個別銘柄ウェイト上限

### 優先度3（モジュール化）
5. **再利用可能化**:
   - ファクターZスコア計算 → `src/features/factor_scoring.py`
   - リスクオフロジック → `src/risk/market_regime.py`
   - バックテストフレームワーク → `src/backtest/daily_portfolio.py`

---

**最終更新**: 2026-02-18 16:00
**作成者**: legacy/projects からの移植
