# FF5ファクターモデル：現時点の相場での有効性分析

**作成日時**: 2026-03-15 15:00
**ステータス**: 計画中
**目的**: Fama-French 5ファクターモデルを用いて、現時点（2026-03時点）の相場で有効なファクターを特定

---

## 📋 背景

### 既存データ確認結果
- **FF5ファクターデータ**: `legacy/_inbox/merged_data_all_stocks/factors/ff5_mom_factors_monthly.parquet`
- **最新データ期間**: 2025-12-31まで（約3ヶ月前）
- **最新分析**: 2025-12-31時点でHML（バリュー効果）が最も有効（Confidence 1.0）

### 直近3ヶ月のファクター傾向（2025年10月-12月）
1. **HML（バリュー効果）**: 平均+3.58%/月（非常に強い）
2. **MKT（市場リターン）**: 全てプラス（強気相場継続）
3. **CMA（投資効果）**: 平均+1.97%/月（プラス）
4. **WML（モメンタム）**: 12月+2.60%（強い）
5. **SMB（小型株効果）**: 全てマイナス（大型株優位）
6. **RMW（収益性）**: マイナス傾向

---

## 🎯 分析目標

### 1. ファクター効果の時系列分析
- [ ] 全期間（2016-03 ～ 2025-12）のファクターリターン推移
- [ ] 直近12ヶ月、6ヶ月、3ヶ月の平均リターン比較
- [ ] ローリング相関分析（ファクター間の関係変化）

### 2. 統計的有意性の検証
- [ ] 各ファクターのt統計量（有意性テスト）
- [ ] シャープレシオ（リスク調整後リターン）
- [ ] 情報比率（Information Ratio）

### 3. レジーム分析
- [ ] 強気相場 vs 弱気相場でのファクター効果比較
- [ ] ボラティリティ環境別のファクター効果
- [ ] 現在のレジーム（2026-03時点）の推定

### 4. ポートフォリオ構築への示唆
- [ ] 有効ファクターの組み合わせ最適化
- [ ] リスク寄与度分析
- [ ] 実践的な銘柄選択基準の提案

---

## 📊 データソース

### 主要データ
1. **FF5月次ファクター**: `legacy/_inbox/merged_data_all_stocks/factors/ff5_mom_factors_monthly.parquet`
2. **月次スナップショット**: `legacy/_inbox/merged_data_all_stocks/factors/month_end_snapshot.parquet`
3. **ファクターサマリー**: `legacy/_inbox/merged_data_all_stocks/factors/market_factor_summary_ff5_mom.csv`

### 必要な列
- **ファクターリターン**: MKT, SMB, HML, RMW, CMA, WML
- **銘柄データ**: Code, MonthEnd, AdjustedClose, MarketCap, BM_Ratio, ROE, INV_Growth

---

## 🔬 分析手法

### 1. ファクタープレミアム計算
```python
# 各月のロングショートポートフォリオリターン
SMB = Small株平均リターン - Big株平均リターン
HML = High BM株平均リターン - Low BM株平均リターン
RMW = Robust株平均リターン - Weak株平均リターン
CMA = Conservative株平均リターン - Aggressive株平均リターン
```

### 2. 統計分析
```python
# t統計量
t_stat = (mean_return / std_return) * sqrt(n_months)

# シャープレシオ（リスクフリーレート = 0と仮定）
sharpe_ratio = mean_return / std_return

# 情報比率
IR = (factor_return - benchmark_return) / tracking_error
```

### 3. ローリング分析
- **ウィンドウ**: 12ヶ月
- **ステップ**: 1ヶ月
- **計算**: 平均リターン、標準偏差、シャープレシオ

---

## 📁 出力ファイル

### 分析ノートブック
- `analyses/20260315_1500_ff5_current_effectiveness/analysis_01.ipynb`

### 出力データ
- `analyses/20260315_1500_ff5_current_effectiveness/factor_performance_summary.csv`
- `analyses/20260315_1500_ff5_current_effectiveness/factor_rolling_stats.csv`
- `analyses/20260315_1500_ff5_current_effectiveness/factor_correlation_matrix.csv`

### グラフ
- `analyses/20260315_1500_ff5_current_effectiveness/factor_returns_cumulative.png`
- `analyses/20260315_1500_ff5_current_effectiveness/factor_rolling_sharpe.png`
- `analyses/20260315_1500_ff5_current_effectiveness/factor_correlation_heatmap.png`

### ドキュメント
- `docs/sessions/20260315_1500_ff5_current_effectiveness.md`
- `docs/knowledges/20260315_1500_ff5_current_effectiveness.md`

---

## ⚠️ 注意事項

### 未来参照バイアス防止
- ✅ t月末のファクター値 → t+1月のリターン予測に使用
- ✅ 月次リバランス想定（月末引けでシグナル → 翌月初寄りで売買）

### データ期間の制約
- **最新データ**: 2025-12-31（約3ヶ月前）
- **現在**: 2026-03-15
- **注意**: 2026年1月-3月のデータは未取得のため、推定・外挿が必要

### リスクフリーレート
- **仮定**: 日本国債10年利回り ≈ 0%（簡略化）
- **代替案**: より精緻な分析では実際の金利データを使用

---

## 📅 実装スケジュール

### Phase 1: データ読み込み・確認（15分）
- [ ] FF5ファクターデータ読み込み
- [ ] 月次スナップショットデータ読み込み
- [ ] データ期間・欠損値確認

### Phase 2: 基本統計分析（20分）
- [ ] 全期間の平均リターン・標準偏差
- [ ] t統計量・シャープレシオ計算
- [ ] 直近期間別（3ヶ月、6ヶ月、12ヶ月）の比較

### Phase 3: ローリング分析（20分）
- [ ] ローリング平均リターン
- [ ] ローリングシャープレシオ
- [ ] 可視化（時系列グラフ）

### Phase 4: レジーム分析（20分）
- [ ] 市場環境（強気/弱気）の分類
- [ ] 環境別ファクター効果
- [ ] 現在のレジーム推定

### Phase 5: 結果まとめ（15分）
- [ ] 有効ファクターランキング
- [ ] ポートフォリオ構築への示唆
- [ ] セッション・ナレッジドキュメント作成

**推定所要時間**: 90分

---

## 🎯 期待される成果物

### 定量的結果
1. **ファクター有効性ランキング**（現時点）
   - 統計的有意性順
   - シャープレシオ順
   - 直近12ヶ月パフォーマンス順

2. **レジーム判定**（2026-03時点）
   - 強気/弱気
   - ボラティリティ水準
   - 推奨ファクター

3. **ポートフォリオ推奨**
   - 有効ファクターの組み合わせ
   - リスク寄与度
   - 期待リターン推定

### 定性的知見
- 日本株市場におけるFF5ファクターの長期有効性
- 時間変動特性（レジーム依存性）
- 実務への適用上の注意点

---

**作成者**: Claude Code
**承認**: 未承認
**次のアクション**: データ読み込み・基本統計分析の開始
