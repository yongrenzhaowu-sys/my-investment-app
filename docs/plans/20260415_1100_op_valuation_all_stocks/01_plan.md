# 営業利益バリュエーション検証（上場全銘柄×時価総額別）

## 目的

日経225銘柄での検証結果を踏まえ、上場全銘柄（約4,000銘柄）を対象に、時価総額別でパフォーマンスを比較します。

## 検証仮説

「営業利益×10と時価総額の乖離が大きい銘柄は割安であり、その後のリターンが高い」

**追加仮説**:
- 小型株の方が、大型株よりも高いリターンを得られる可能性がある
- ただし、小型株の方がリスク（ボラティリティ）も高い

## 分析設計

### 1. 対象銘柄

- **全上場銘柄**: 約4,000銘柄（東証プライム、スタンダード、グロース）
- **除外**: REITs、ETF、上場廃止銘柄

### 2. 時価総額分類

各年のリバランス時点で、時価総額の分位数に基づいて分類：

- **大型株**: 時価総額上位30%（約1,200銘柄）
- **中型株**: 時価総額30-70%（約1,600銘柄）
- **小型株**: 時価総額下位30%（約1,200銘柄）

### 3. スクリーニング条件

日経225分析と同様：

1. **増益基調**: 直近3年連続増益（営業利益）
2. **割安度スコア**: `(営業利益 × 10 - 時価総額) / 時価総額`
3. **選定**: 各時価総額グループで割安度スコア上位N銘柄

**追加フィルタ**（リスク管理）:
- 自己資本比率 > 20%（財務安定性）
- 営業利益 > 0（直近決算）
- 時価総額 > 100億円（最低流動性）

### 4. ポートフォリオサイズ

各時価総額グループで以下の銘柄数を比較：
- 上位5銘柄
- 上位10銘柄
- 上位20銘柄

### 5. バックテスト設計

#### 期間
- 2022-2025年（4年間、年次リバランス）

#### タイミング（ルックアヘッドバイアス防止）
- **データ基準日**: 各年3月末時点で利用可能な財務データ
- **エントリー**: 4月第1営業日の始値
- **エグジット**: 翌年3月最終営業日の終値

#### ベンチマーク
- TOPIX（全市場）
- 各時価総額グループの市場平均

### 6. 評価指標

- 累積リターン
- 年率リターン（CAGR）
- シャープレシオ
- 最大ドローダウン
- 勝率（年次）

### 7. 時価総額別比較

各時価総額グループで以下を比較：

| グループ | 期待リターン | 期待リスク | シャープレシオ |
|---------|-------------|-----------|---------------|
| 大型株 | 低い | 低い | ? |
| 中型株 | 中程度 | 中程度 | ? |
| 小型株 | 高い | 高い | ? |

## データソース

### J-Quants API（既存データ）

- 株価データ: `data/processed/jquants_historical_6years/daily_bars_2021_2026.parquet`
- 財務データ: `data/processed/jquants_historical_6years/financials_2021_2026.parquet`

## 実装ステップ

### Step 1: 時価総額分類ロジック

```python
# 各年のリバランス時点で時価総額を計算
market_caps = calculate_market_cap(prices, base_date)

# 分位数で分類
large_cap_threshold = market_caps['MarketCap'].quantile(0.70)
small_cap_threshold = market_caps['MarketCap'].quantile(0.30)

market_caps['CapGroup'] = 'Mid'
market_caps.loc[market_caps['MarketCap'] >= large_cap_threshold, 'CapGroup'] = 'Large'
market_caps.loc[market_caps['MarketCap'] <= small_cap_threshold, 'CapGroup'] = 'Small'
```

### Step 2: グループ別スクリーニング

```python
for cap_group in ['Large', 'Mid', 'Small']:
    # 対象銘柄
    target_codes = market_caps[market_caps['CapGroup'] == cap_group]['Code'].tolist()

    # スクリーニング
    selected = screening(financials, prices, target_codes, base_date, top_n=10)

    # バックテスト
    results = backtest(prices, selected, entry_date, exit_date)
```

### Step 3: パフォーマンス比較

各時価総額グループのCAGR、シャープレシオ、最大DDを比較

## リスク管理強化

日経225分析で発見した株式併合リスクに対応：

### 1. 株式併合検出

```python
# AdjFactorの急激な変化を検出
adjfactor_changes = prices.groupby('Code')['AdjFactor'].apply(
    lambda x: (x.diff().abs() > 0.5).any()
)

# 株式併合銘柄を除外
exclude_codes = adjfactor_changes[adjfactor_changes].index.tolist()
```

### 2. 追加フィルタ

```python
# 自己資本比率チェック
financials['EquityRatio'] = financials['Eq'] / financials['TA']
df = df[df['EquityRatio'] > 0.20]

# 営業CFチェック（利用可能な場合）
if 'CFO' in financials.columns:
    df = df[df['CFO'] > 0]
```

### 3. ストップロス

バックテスト実装時に、個別銘柄で-30%の損失が出たら損切り

## 期待される発見

### 仮説1: 小型株で高リターン

小型株グループの方が、大型株よりも高いリターンを得られる可能性

### 仮説2: リスク調整後リターン

シャープレシオで見ると、中型株が最も効率的な可能性

### 仮説3: ポートフォリオサイズ

小型株では分散投資（20銘柄）が有効、大型株では集中投資（5銘柄）が有効な可能性

## 成果物

### コード

- `analyses/20260415_1100_op_valuation_all_stocks/screening_by_marketcap.py`
- `analyses/20260415_1100_op_valuation_all_stocks/backtest_by_marketcap.py`

### 結果ファイル

- `screening_results_{CapGroup}_20260331.csv`: 各グループの選定銘柄
- `backtest_yearly_{CapGroup}_{N}stocks.csv`: 年次リターン
- `backtest_comparison_by_marketcap.csv`: 時価総額別比較

### ドキュメント

- `analyses/20260415_1100_op_valuation_all_stocks/results.md`: 結果サマリー
- `docs/knowledges/20260415_1100_op_valuation_by_marketcap.md`: 時価総額別分析の知見

## スケジュール

1. **時価総額分類ロジック実装**: 10分
2. **スクリーニングスクリプト実装**: 15分
3. **バックテストスクリプト実装**: 15分
4. **実行・結果分析**: 20分
5. **ドキュメント作成**: 10分

**合計**: 約70分

## 参照

- **前回分析**: `analyses/20260415_1000_op_valuation_n225/`
- **日経225結果**: CAGR 14.01%（上位5銘柄）
