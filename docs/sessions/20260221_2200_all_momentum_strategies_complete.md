# セッションサマリー: 全モメンタム戦略の検証完了

**日時**: 2026-02-21 22:00
**目的**: ユーザー提案の高度なモメンタム指標の実装・検証

---

## やったこと

### 1. R2補正モメンタム（オプション1：ユーザーの式）

**実装内容**:
- SLOPE（対数回帰）→ 単純リターンに変換: `daily_return = exp(SLOPE) - 1`
- 年率化: `(1 + daily_return)^250 - 1`
- R2補正: `momentum_score = annualized_return × R2`

**結果**: 年率-2.96%（大失敗）

**問題点**:
- R2フィルタが有効なモメンタムを除外
- 極端な値が発生（対策: SLOPE ±5%制限）

---

### 2. R2補正モメンタム（オプション2：数学的に正確）

**実装内容**:
- SLOPE（対数回帰）
- 年率化: `exp(SLOPE * 250) - 1`
- R2補正: `momentum_score = annualized_return × R2`

**結果**: 年率-2.96%（オプション1と同じ）

**理由**: SLOPEが小さい場合、両式は数学的にほぼ等価

---

### 3. tanh(slope/sigma)モメンタム

**参考**: https://overtheperiod.hatenablog.com/entry/2025/12/22/211113

**実装内容**:
- SLOPE / SIGMA（残差標準偏差）
- tanh変換: `score = tanh(SLOPE / SIGMA)`
- -1～+1に正規化、極端な値を抑制

**結果**: 年率+1.65%（失敗）

**問題点**:
- 日本株のslope/sigma比が低い（0.1～0.3）
- 推奨閾値0.95を満たす銘柄: 0銘柄
- 90日モメンタム × 年次リバランスのミスマッチ

---

## 決めたこと

### ✅ ベースライン戦略で確定

**最終成績**:

| 順位 | 戦略 | 年率 | シャープ | MDD |
|------|------|------|---------|-----|
| 🥇 1位 | **ベースライン** | **+25.61%** | **1.07** | **-16.60%** |
| 🥈 2位 | Simple 6M | +24.94% | 0.82 | -17.42% |
| 🥉 3位 | + 低PER | +25.34% | 0.87 | -18.84% |
| 4位 | tanh(slope/sigma) | +1.65% | -0.11 | -39.56% |
| 5位 | R2補正 | -2.96% | -0.42 | -62.02% |

**結論**:
- 全ての高度な指標は失敗
- シンプル イズ ベスト
- ベースライン単体で実運用推奨

---

## 重要な学び

### 1. 理論 ≠ 実践

- R2補正: 理論的に優れているが実際は有害
- tanh(slope/sigma): 外国株では有効だが日本株では失敗
- 推奨閾値が日本株に適用できない

### 2. 日本株の特性

- 中期モメンタムが弱い
- slope/sigma比が低い（0.1～0.3）
- バリュー戦略が最も有効

### 3. バックテストの罠

- 複雑な指標ほど過学習のリスク
- 理論的な優位性が実際のパフォーマンスを保証しない
- シンプルな指標の方が頑健

---

## 次にやること

### 推奨: 実運用開始

**ベースライン戦略**:
- 年率: +25.61%
- シャープ: 1.07
- MDD: -16.60%
- 実装: 完了 ✅

**実運用の進め方**:
1. 少額から開始（100-300万円）
2. 厳格にルールを守る
3. 1年間の実績監視
4. エッジ減衰が確認されたら対策検討

### オプション: さらなる改善

1. **小型株バリュー**（時価総額下位 × 低PBR）
2. **高配当戦略**（高配当利回り × 安定収益）
3. **月次リバランス**の検証

---

## 重要なパス

### バックテストスクリプト

```
analyses/20260221_1500_annual_backtest_improved/
├── backtest_annual_improved.py             # ✅ ベースライン（確定版）
├── backtest_strategy3_low_per.py           # 戦略3
├── backtest_momentum_strategy.py           # Simple 6M
├── backtest_momentum_r2_adjusted.py        # R2補正（オプション1）
├── backtest_momentum_r2_exp.py             # R2補正（オプション2）
└── backtest_momentum_tanh_sharpe.py        # tanh(slope/sigma)
```

### 最終レポート

```
docs/reports/
└── 20260221_all_strategies_final_comparison.md  # 全戦略の最終比較
```

---

## コマンド履歴

```bash
# R2補正（オプション1）実行
python analyses/20260221_1500_annual_backtest_improved/backtest_momentum_r2_adjusted.py

# R2補正（オプション2）実行
python analyses/20260221_1500_annual_backtest_improved/backtest_momentum_r2_exp.py

# tanh(slope/sigma)実行
python analyses/20260221_1500_annual_backtest_improved/backtest_momentum_tanh_sharpe.py
```

---

**ステータス**: ✅ 完了（全戦略検証完了、ベースライン確定）
**所要時間**: 約3時間（累計）
**次のアクション**: 実運用開始の判断
