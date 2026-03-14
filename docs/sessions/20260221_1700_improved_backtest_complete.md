# Session: 改善版バックテスト完成

**日時**: 2026-02-21 17:00
**目的**: Legacy版の問題点を修正し、より現実的なバックテスト実装を完成

## やったこと

### 1. Legacy版の問題点を特定

#### 主要な問題
1. **ルックアヘッド（未来参照）リスク**
   - 前後5日猶予で、リバランス日より前の価格を使う可能性
   - `start_date - 5days` の価格取得は過去の情報だが不正確

2. **現金残高を無視**
   - 100株単位制限で毎回端数（現金）が出る
   - その現金を次期に引き継いでいない
   - 非現実的（実際は現金も運用に使える）

3. **税金計算のタイミング**
   - 期間ごとではなく、暦年で損益通算すべき
   - 実際の税制に準拠していない

4. **投資比率100%の仮定**
   - 現金残高が消える
   - 実際は95〜99%程度

### 2. 改善版の実装（backtest_annual_improved.py）

#### 改善点の詳細

**【改善1】ルックアヘッド対策**
```python
# リバランス日以降の価格のみ使用
start_prices_df = df_price[
    (df_price['date'] >= start_date) &  # 当日以降のみ
    (df_price['date'] <= start_date + pd.Timedelta(days=5))
]
start_prices = start_prices_df.groupby('code').first()['adjusted_close']
```

**【改善2】現金管理の明示的追跡**
```python
cash = INITIAL_CAPITAL  # 現金残高を追跡
# 投資
cash -= total_invested
# 売却
cash += sell_value
# 税金支払い
cash -= tax
```

**【改善3】暦年ベースの税金計算**
```python
# 暦年が変わったら税金を支払う
if current_year != start_date.year:
    if annual_realized_pnl > 0:
        tax = annual_realized_pnl * TAX_RATE
        cash -= tax
    annual_realized_pnl = 0
```

**【改善4】税金支払いのための株式売却**
```python
# 現金不足の場合は株式を一部売却
if tax > cash and len(portfolio) > 0:
    # 時価総額が小さい銘柄から売却
    portfolio_values.sort(key=lambda x: x[1])
    # 必要な分だけ売却
```

**【改善5】総資産の正確な計算**
```python
total_value = cash + portfolio_value  # 現金 + 株式時価
```

## 決めたこと

### 改善版の最終成績

| 指標 | Legacy版 | 再現版 | **改善版** |
|------|----------|--------|-----------|
| 年率リターン | +28.52% | +24.27% | **+25.61%** |
| シャープレシオ | 1.47 | 0.86 | **1.07** |
| 最大DD | -2.41% | -12.49% | **-16.60%** |
| 総リターン | - | 605.62% | **734.24%** |
| 平均投資比率 | ～100% | - | **97.7%** |
| 最終現金 | - | - | **+1,955,075円** |

### Legacy版との差分（-2.91%pt）の理由

改善版の方が**現実的な制約**を正確に反映：

1. **ルックアヘッド対策**: 保守的な価格取得（未来の情報を使わない）
2. **税金支払いのための株式売却**: 実際の運用では避けられない
3. **正確な現金管理**: 投資比率が100%未満

→ **実際の運用では改善版に近い結果になると期待**

### 期間別実績（改善版）

```
2016-10 → 2017-10: +90.0%（税引後）
2017-10 → 2018-10: +39.7%
2018-10 → 2019-10: -17.3%（税支払い含む）
2019-10 → 2020-10: +34.2%
2020-10 → 2021-10: +6.9%
2021-10 → 2022-10: +7.4%
2022-10 → 2023-10: +44.3%
2023-10 → 2024-10: +46.0%
2024-10 → 2026-01: +39.7%
```

## 次にやること

### パフォーマンス向上戦略

改善版ベースライン（年率+25.61%）に以下の指標を追加：

#### 利用可能な指標（prediction_scores.csv）
1. **quarterly_per**: 四半期PER → 低PER銘柄を選択
2. **custom_growth_rate**: カスタム成長率 → 高成長銘柄を選択
3. **peg_score**: PEG的スコア → 高PEGスコア銘柄を選択
4. **earnings_yield**: 益利回り → 高益利回り銘柄を選択
5. **volume_ma20**: 出来高20日移動平均 → 高出来高銘柄を選択

#### 戦略候補
1. ベースライン: 低PBR × 高ROE（+25.61%）
2. + 高出来高フィルタ
3. + 低PER（四半期）
4. + 高PEG的スコア
5. + 高成長率
6. + 高益利回り
7. 複合戦略（全て組み合わせ）

### 実装アプローチ

```python
# 1. 予測スコアデータを年次リバランス日に統合
scores_by_date = {}
for rdate in rebalance_dates:
    available = df_scores[df_scores['disclosed_date'] <= rdate]
    latest = available.groupby('code').tail(1)
    scores_by_date[rdate] = latest

# 2. 各戦略で銘柄選定ロジックを変更
def select_stocks_with_volume_filter(merged, n_stocks=20):
    # 出来高中央値以上に絞る
    volume_median = merged['volume_ma20'].median()
    high_volume = merged[merged['volume_ma20'] >= volume_median]
    # ベースライン戦略を適用
    return select_stocks_baseline(high_volume, n_stocks)

# 3. 全戦略を並列実行して比較
for strategy_name, select_func in strategies.items():
    results[strategy_name] = run_backtest(select_func)
```

## 重要なパス/コマンド

```bash
# 改善版バックテスト実行
python analyses/20260221_1500_annual_backtest_improved/backtest_annual_improved.py

# 予測スコアデータ確認
head analyses/growth_yield_prediction/prediction_scores.csv
```

## 重要な発見

### 改善版の強み

1. **現実的な実装**: 実際の運用に最も近い
2. **保守的なリターン**: ルックアヘッドなし、税金支払い含む
3. **堅実なパフォーマンス**: シャープレシオ1.07（Legacy 1.47、再現版0.86）
4. **プラスの現金残高**: 最終現金+195万円（運用継続可能）

### Legacy版 vs 再現版 vs 改善版

| 版 | 年率 | 特徴 | 推奨度 |
|----|------|------|--------|
| Legacy | +28.52% | 簡易的、問題あり | × |
| 再現版 | +24.27% | Legacy再現、リターン率ベース | △ |
| 改善版 | +25.61% | 現実的、全ての問題を修正 | ◎ |

**結論**: 改善版（+25.61%）が最も信頼できる実装

## 成果物

```
analyses/20260221_1500_annual_backtest_improved/
├── backtest_annual_improved.py       # 改善版実装 ✅
├── annual_results_improved.csv       # 結果データ
├── summary_improved.txt              # サマリー
├── backtest_annual_legacy_style.py  # 再現版（参考）
└── backtest_annual_fixed.py         # 初期版（失敗）
```
