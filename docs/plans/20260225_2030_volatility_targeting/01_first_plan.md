# 実装計画: ボラティリティターゲティング戦略

**作成日**: 2026-02-25 20:30
**ステータス**: 実装中

---

## 目的

月次リバランス戦略（小型株×高成長率）にボラティリティターゲティングを適用し、MDDを削減しつつリターンを維持する。

**現在の問題**:
- MDD -31.32%が大きすぎる
- 市況フィルターは効果薄い（シャープレシオが悪化）
- より効果的なリスク管理手法が必要

**期待効果**:
- MDD削減: -31.32% → -20%未満（目標）
- リターン維持: +21.21% → +15%以上（目標）
- シャープレシオ改善: 1.122 → 1.2以上（目標）

---

## ボラティリティターゲティングの仕組み

### 基本概念

**ポジションサイズの動的調整**:
```
ポジションサイズ = ターゲットボラティリティ / 実現ボラティリティ
```

- **ボラティリティ高い時期**: ポジションサイズを縮小（リスク抑制）
- **ボラティリティ低い時期**: ポジションサイズを拡大（リターン追求）

### 設計パラメータ

#### 1. ターゲットボラティリティ
- **候補**: 年率12%, 15%, 18%
- **基準**: 現在の戦略ボラティリティは年率18.91%
- **推奨**: まず15%でテスト（現在の80%程度）

#### 2. ルックバック期間
- **候補**: 過去1ヶ月、3ヶ月、6ヶ月、12ヶ月
- **推奨**: 過去3ヶ月（63営業日）
  - 短すぎると不安定
  - 長すぎると反応が遅い

#### 3. ポジションサイズの上限・下限
- **下限**: 20%（最低限のエクスポージャー）
- **上限**: 100%（レバレッジなし）
- **理由**: 極端なポジション変動を防ぐ

#### 4. リバランス頻度
- **現在**: 月次
- **維持**: 月次（毎月初にポジションサイズを再計算）

---

## 実装ステップ

### Step 1: 過去ボラティリティの計算

```python
# 月次リターンの履歴を使用
past_returns = monthly_returns[-lookback_months:]

# 実現ボラティリティ（年率換算）
realized_volatility = past_returns.std() * np.sqrt(12)
```

### Step 2: ポジションサイズの計算

```python
# ターゲットボラティリティ
target_volatility = 0.15  # 年率15%

# ポジションサイズ
position_size = target_volatility / realized_volatility

# 上限・下限を適用
position_size = np.clip(position_size, 0.20, 1.00)
```

### Step 3: リターンの調整

```python
# 戦略リターンにポジションサイズを乗算
adjusted_return = strategy_return * position_size

# 残りは現金（リターン0%）
cash_return = 0.0 * (1 - position_size)

# 月次ポートフォリオリターン
portfolio_return = adjusted_return + cash_return
```

### Step 4: 複数パラメータのテスト

**ターゲットボラティリティ**:
- 12%, 15%, 18%

**ルックバック期間**:
- 3ヶ月、6ヶ月

**組み合わせ**: 3 × 2 = 6パターン

---

## 期待される結果

### シナリオ1: 保守的（ターゲット12%）
- **MDD**: -15% ~ -20%（大幅改善）
- **年率リターン**: +12% ~ +15%（やや低下）
- **シャープレシオ**: 1.0 ~ 1.2（維持または改善）

### シナリオ2: バランス（ターゲット15%）
- **MDD**: -20% ~ -25%（改善）
- **年率リターン**: +15% ~ +18%（適度に維持）
- **シャープレシオ**: 1.2 ~ 1.4（改善）

### シナリオ3: 攻撃的（ターゲット18%）
- **MDD**: -25% ~ -30%（小幅改善）
- **年率リターン**: +18% ~ +20%（ほぼ維持）
- **シャープレシオ**: 1.1 ~ 1.3（小幅改善）

---

## 実装の詳細

### ファイル構成

```
analyses/20260225_1800_event_driven_strategy/
├── backtest_06_volatility_targeting.py  # 実装
└── results_volatility_targeting/        # 結果
    ├── monthly_returns.csv
    ├── performance_summary.txt
    ├── position_sizes.csv               # ポジションサイズ履歴
    └── volatility_history.csv           # ボラティリティ履歴
```

### コード構造

```python
# 1. データ読み込み（既存のロジック）
df_growth = pd.read_csv(...)
df_price = pd.read_parquet(...)

# 2. 月次リターンの計算（既存のロジック）
monthly_returns = []
for current_month in months:
    # スクリーニング
    strategy_portfolio = screen_stocks(...)

    # 月次リターン
    strategy_return = calculate_return(...)
    monthly_returns.append(strategy_return)

# 3. ボラティリティターゲティングの適用（新規）
adjusted_returns = []
position_sizes = []
volatilities = []

for i, current_month in enumerate(months):
    if i < lookback_months:
        # 初期期間はフルポジション
        adjusted_returns.append(monthly_returns[i])
        position_sizes.append(1.0)
        volatilities.append(np.nan)
    else:
        # 過去ボラティリティを計算
        past_returns = monthly_returns[i-lookback_months:i]
        realized_vol = np.std(past_returns) * np.sqrt(12)

        # ポジションサイズを計算
        position_size = target_vol / realized_vol
        position_size = np.clip(position_size, 0.20, 1.00)

        # リターンを調整
        adjusted_return = monthly_returns[i] * position_size

        adjusted_returns.append(adjusted_return)
        position_sizes.append(position_size)
        volatilities.append(realized_vol)

# 4. パフォーマンス計算
cumulative_return = (1 + adjusted_returns).cumprod() - 1
...
```

---

## 検証ポイント

### 1. ポジションサイズの妥当性
- 極端な値（<20%, >100%）が頻発していないか
- 市況変動に適切に反応しているか

### 2. ドローダウンの削減
- 2018年末（-15.90%）が削減されているか
- 2020年初（コロナショック期）が削減されているか

### 3. リターンの維持
- 年率リターンが+15%以上を維持できているか
- 複利効果が適切に機能しているか

### 4. シャープレシオの改善
- リスク調整後リターンが改善しているか
- ボラティリティターゲティングの効果が確認できるか

---

## リスクと制約

### 1. パラメータ依存性
- ターゲットボラティリティの選択に依存
- ルックバック期間の選択に依存
- → 複数パラメータでロバストネスを確認

### 2. 過去データ依存
- 過去ボラティリティが将来を予測するとは限らない
- ボラティリティレジームの変化に対応できない可能性

### 3. 取引コスト
- ポジションサイズ変更によるリバランスコスト
- 月次リバランスなので影響は限定的

### 4. 実装の簡易化
- 月次集計で簡易化（日次調整ではない）
- より精緻な実装は日次ボラティリティ計算が必要

---

## 次のステップ

1. ✅ 計画完成
2. ⏳ 実装（backtest_06_volatility_targeting.py）
3. ⏳ 複数パラメータでテスト
4. ⏳ 結果評価と比較
5. ⏳ ドキュメント化

---

**作成者**: Claude Code
**計画日**: 2026-02-25 20:30
