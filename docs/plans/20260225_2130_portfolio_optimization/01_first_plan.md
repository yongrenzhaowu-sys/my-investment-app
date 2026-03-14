# 実装計画: ポートフォリオ最適化（MDD削減）

**作成日**: 2026-02-25 21:30
**ステータス**: 実装中

---

## 目的

ベース戦略とレバレッジ戦略を組み合わせ、MDDを-30%以下に抑えつつ高リターンを実現する。

**現在の状況**:
- ベース戦略: 年率+28.52%, MDD -2.41%, Sharpe 1.48
- レバレッジ戦略（Target25_LB3）: 年率+31.92%, MDD -40.62%, Sharpe 1.138

**目標**:
- 年率リターン: +28% ~ +30%以上
- **MDD: -30%以下**（必須）
- シャープレシオ: 1.2以上

---

## ポートフォリオ最適化の考え方

### 基本コンセプト

**2つの戦略の組み合わせ**:
```
ポートフォリオリターン = ベース戦略 × w1 + レバレッジ戦略 × w2
（w1 + w2 = 1.0）
```

**期待効果**:
1. **リスク分散**: 異なる戦略の組み合わせでリスク削減
2. **MDD削減**: ベース戦略の低MDDが全体を引き下げる
3. **リターン維持**: レバレッジ戦略の高リターンを活用

### テストする配分比率

| 配分 | ベース | レバレッジ | 期待リターン | 期待MDD |
|------|--------|-----------|------------|---------|
| 1 | 30% | 70% | +30.7% | -30%前後 |
| 2 | 40% | 60% | +30.4% | -26%前後 |
| 3 | 50% | 50% | +30.2% | -22%前後 |
| 4 | 60% | 40% | +30.0% | -18%前後 |
| 5 | 70% | 30% | +29.7% | -14%前後 |

**推奨**: 30/70または40/60でMDD -30%以下を達成

---

## 実装ステップ

### Step 1: ベース戦略のリターンを取得

**データソース**: 既存のベース戦略の月次リターン

**注意点**:
- ベース戦略は年次リバランス（10月1日）
- レバレッジ戦略は月次リバランス
- 時間軸を合わせる必要がある

**アプローチ**:
```python
# ベース戦略: 10月〜翌年9月の1年間保有
# 月次リターンに分解（等分または実際の月次パフォーマンス）

# 簡易版: ベース戦略の年次リターンを12ヶ月で等分
annual_returns = [0.5211, 0.0979, 0.2799, ...]  # 各年のリターン
monthly_base = annual_return / 12  # 月次に分解

# または、ベース戦略の月次パフォーマンスを実際に計算
```

### Step 2: レバレッジ戦略のリターンを取得

**データソース**: backtest_07_leverage.pyの結果

```python
# Target25_LB3の月次リターン
leverage_monthly_returns = [...]  # 既に計算済み
```

### Step 3: ポートフォリオリターンを計算

```python
# 各配分比率でテスト
for weight_base in [0.3, 0.4, 0.5, 0.6, 0.7]:
    weight_leverage = 1.0 - weight_base

    # 月次ポートフォリオリターン
    portfolio_returns = []
    for i in range(len(monthly_returns)):
        base_ret = base_monthly_returns[i]
        leverage_ret = leverage_monthly_returns[i]

        portfolio_ret = base_ret * weight_base + leverage_ret * weight_leverage
        portfolio_returns.append(portfolio_ret)

    # パフォーマンス計算
    cagr = calculate_cagr(portfolio_returns)
    mdd = calculate_mdd(portfolio_returns)
    sharpe = calculate_sharpe(portfolio_returns)
```

### Step 4: MDD -30%以下の設定を特定

```python
# MDD -30%以下をフィルター
optimal_configs = [
    config for config in results
    if config['mdd'] >= -0.30
]

# リターンが最も高い設定を推奨
best_config = max(optimal_configs, key=lambda x: x['cagr'])
```

---

## 期待される結果

### シナリオ1: ベース30% + レバレッジ70%

**期待パフォーマンス**:
- 年率リターン: +30.7%
- MDD: -29% ~ -31%（境界線）
- シャープレシオ: 1.15 ~ 1.25

**評価**: MDDギリギリ、高リターン

### シナリオ2: ベース40% + レバレッジ60%

**期待パフォーマンス**:
- 年率リターン: +30.4%
- MDD: -24% ~ -28%（目標達成）
- シャープレシオ: 1.20 ~ 1.30

**評価**: バランス良好、推奨

### シナリオ3: ベース50% + レバレッジ50%

**期待パフォーマンス**:
- 年率リターン: +30.2%
- MDD: -20% ~ -24%（十分に余裕）
- シャープレシオ: 1.25 ~ 1.35

**評価**: 保守的、安定

---

## 実装の詳細

### ファイル構成

```
analyses/20260225_1800_event_driven_strategy/
├── backtest_08_portfolio_mix.py        # 実装
└── results_portfolio_mix/              # 結果
    ├── performance_summary.csv
    ├── allocation_comparison.txt
    └── optimal_portfolio.txt
```

### コード構造

```python
# 1. ベース戦略のリターンを準備
base_returns = prepare_base_strategy_returns()

# 2. レバレッジ戦略のリターンを準備
leverage_returns = prepare_leverage_strategy_returns()

# 3. 複数の配分比率でテスト
allocations = [
    (0.3, 0.7),
    (0.4, 0.6),
    (0.5, 0.5),
    (0.6, 0.4),
    (0.7, 0.3),
]

results = []
for weight_base, weight_leverage in allocations:
    portfolio_returns = (
        base_returns * weight_base +
        leverage_returns * weight_leverage
    )

    # パフォーマンス計算
    perf = calculate_performance(portfolio_returns)
    results.append(perf)

# 4. MDD -30%以下の最適設定を特定
optimal = find_optimal_allocation(results, max_mdd=-0.30)
```

---

## 検証ポイント

### 1. 時間軸の整合性

**問題**:
- ベース戦略: 年次リバランス（2017-10-01開始）
- レバレッジ戦略: 月次リバランス（2017-08開始）

**対応**:
- 共通期間を使用（2017-10-01 ~ 2025-12-31）
- ベース戦略の月次パフォーマンスを計算または近似

### 2. MDDの計算

**重要**: ポートフォリオのMDDは単純な加重平均ではない

```python
# 正しい計算
cumulative = (1 + portfolio_returns).cumprod()
peak = cumulative.expanding().max()
drawdown = (cumulative - peak) / peak
mdd = drawdown.min()
```

### 3. 相関の影響

**期待**:
- ベース戦略とレバレッジ戦略の相関が低い場合、分散効果大
- 相関が高い場合、分散効果小

**確認**:
```python
correlation = base_returns.corr(leverage_returns)
print(f"相関: {correlation:.3f}")
```

### 4. リバランス頻度

**現実的な運用**:
- ベース戦略: 年次リバランス
- レバレッジ戦略: 月次リバランス
- ポートフォリオ: 月次で配分を維持（リバランス）

---

## リスクと制約

### 1. ベース戦略の月次データ

**問題**: ベース戦略は年次リバランスのため、月次データがない

**対応案**:
1. **簡易版**: 年次リターンを12ヶ月で等分
2. **精緻版**: ベース戦略の月次パフォーマンスを実際に計算
3. **代替案**: 日次リターンから月次を集計

**推奨**: まず簡易版でテスト、必要なら精緻版

### 2. リバランスコスト

**問題**: 配分維持のためのリバランスコスト

**対応**:
- 月次リバランス時に配分を調整
- コストは小さい（既に月次リバランス中）

### 3. 実装の複雑さ

**問題**: 2つの戦略を同時に運用する複雑さ

**対応**:
- 各戦略は独立して運用
- 月次で配分を確認・調整

---

## 次のステップ

1. ✅ 計画完成
2. ⏳ ベース戦略の月次リターンを準備
3. ⏳ ポートフォリオ最適化を実装
4. ⏳ 結果評価（MDD -30%以下を確認）
5. ⏳ ドキュメント化

---

## 期待される最終成果

**推奨ポートフォリオ**:
- **配分**: ベース40% + レバレッジ60%
- **年率リターン**: +30.4%前後
- **MDD**: -26%前後（目標-30%以下達成）
- **シャープレシオ**: 1.25前後

**成功条件**:
- MDD -30%以下を達成
- 年率リターン +30%以上を維持
- シャープレシオ 1.2以上

**期待**:
- リスクとリターンの最適バランス
- 実用的なポートフォリオの完成
- クオンツ運用3ヶ月の集大成

---

**作成者**: Claude Code
**計画日**: 2026-02-25 21:30
