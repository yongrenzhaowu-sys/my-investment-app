# 戦略1: バリュエーション水準と資本効率性指標の有効性モデル

**作成日**: 2026-02-21
**分析ID**: 20260221_0915_quants_model_valuation_efficiency

## 仮説

P/B（株価純資産倍率）の水準によって、ROE（自己資本利益率）とROA（総資産利益率）の有効性が異なる。

### 背景

- 低PBR銘柄は「割安」とされるが、単純に低PBRだけで選ぶと「低収益性」の銘柄が混入する
- 高PBR銘柄は「成長期待」が織り込まれているが、実際の収益性（ROE/ROA）が伴わない場合がある
- PBR水準ごとに、ROEとROAの有効性を比較することで、最適な組み合わせを特定する

## 検証内容

### データ
- 価格データ: `data/curated/jquants/prices/daily_quotes_all.parquet`（2017年以降）
- 財務データ: `data/curated/jquants/financials/statements_all.parquet`（年次決算のみ）

### 指標
- PBR = adjusted_close / bps
- ROE = (net_profit / equity) × 100
- ROA = (net_profit / total_assets) × 100

### 戦略設計

1. **月次リバランス**（月末営業日）
2. **各リバランス日で**:
   - 全銘柄をPBRで四分位に分割
     - Q1: 最低PBR（第1四分位）
     - Q2: 低-中PBR（第2四分位）
     - Q3: 中-高PBR（第3四分位）
     - Q4: 最高PBR（第4四分位）
   - 各四分位で2つのポートフォリオを構築:
     - **ポートフォリオA**: 高ROE（上位25%、20銘柄）
     - **ポートフォリオB**: 高ROA（上位25%、20銘柄）
   - 合計8ポートフォリオ（4四分位 × 2指標）

3. **バックテスト条件**:
   - 初期資本: 10,000,000円
   - 保有銘柄数: 各ポートフォリオ20銘柄
   - リバランス頻度: 月次（月末）
   - 税率: 20.315%
   - 期間: 2017-01-01 ~ 2026-02-17

### 未来参照防止
- 財務データは `disclosed_date` 以降のみ使用
- 年次決算のみ（`fiscal_quarter == 'FY'`）

### 評価指標
各ポートフォリオについて:
- 総リターン、年率リターン
- 年率ボラティリティ
- 最大ドローダウン（MDD）
- シャープレシオ
- カルマー比

### 期待される結果

1. **低PBR領域**:
   - ROE/ROAの高い銘柄が強いパフォーマンスを示す
   - 「割安×高収益性」の組み合わせが有効

2. **高PBR領域**:
   - ROE/ROAの効果が弱まる可能性
   - 成長期待が既に株価に織り込まれている

3. **ROE vs ROA**:
   - PBR水準によってどちらが有効かが異なる可能性
   - 低PBRでは負債活用（ROE）が有効、高PBRでは資産効率（ROA）が有効など

## 成果物

1. `analysis_01.ipynb`: バックテスト実装
2. `backtest_results.csv`: 日次パフォーマンス
3. `backtest_metrics.json`: 評価指標（JSON形式）
4. `performance_summary.txt`: サマリ（テキスト）

## 参考

- 既存実装: `analyses/20260218_1630_weekly_long_only/analysis_01_optimized.ipynb`
- 実装計画: `docs/plans/20260221_0900_quants_models_verification/01_first_plan.md`
