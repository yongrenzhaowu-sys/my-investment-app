# Knowledge: Legacy版バックテスト再現のベストプラクティス

**作成日**: 2026-02-21 15:30
**カテゴリ**: バックテスト実装、データ処理

## 要約

Legacy版の年次リバランス戦略（+28.52%）を再現する過程で発見した重要な実装パターンとデータ処理のベストプラクティス。

## Legacy実装の3つの重要パターン

### 1. リターン率ベースの複利計算

**従来（キャッシュフロー方式）**:
```python
# 売却
sell_value = sum(shares * price for each stock)
cash += sell_value

# 購入
cash -= sum(shares * price for each stock)

# 最終評価
total_value = cash + portfolio_value
```

**Legacy方式（リターン率ベース）**:
```python
# 各期間のリターン率を計算
total_profit = total_end_value - total_investment
net_return = (total_profit - tax) / cumulative_capital

# 複利計算
cumulative_capital = cumulative_capital * (1 + net_return)
```

**利点**:
- シンプルで理解しやすい
- 複利効果が明確
- キャッシュ管理不要

### 2. 価格データ取得時の前後5日猶予

**問題**: 特定の日（例: 2020-10-01）にadjusted_closeが全てNaN

**解決策**:
```python
# 前後5日の範囲で最初/最後の有効な価格を取得
start_window = df_price[
    (df_price['date'] >= start_date - pd.Timedelta(days=5)) &
    (df_price['date'] <= start_date + pd.Timedelta(days=5))
]
start_prices = start_window.groupby('code').first()['adjusted_close']

end_window = df_price[
    (df_price['date'] >= end_date - pd.Timedelta(days=5)) &
    (df_price['date'] <= end_date + pd.Timedelta(days=5))
]
end_prices = end_window.groupby('code').last()['adjusted_close']
```

**効果**:
- データ欠損に対するロバスト性
- リバランス成功率: 8/9 → 9/9

### 3. 最後のリバランス日を除外

**理由**: 保有期間を確保するため

```python
# 最後のリバランスは除外（評価のみ）
for i in range(len(rebalance_dates) - 1):
    start_date = rebalance_dates[i]
    end_date = rebalance_dates[i + 1]
    # バックテスト処理
```

## データ品質の注意点

### adjusted_close の欠損パターン

1. **完全欠損日**: 2020-10-01（全銘柄でNaN）
   - 原因: 調整係数が未計算
   - 頻度: 稀だが致命的
   - 対策: 前後5日猶予

2. **個別銘柄の欠損**: ランダム
   - 原因: 取引停止、上場廃止等
   - 頻度: 普通
   - 対策: dropna() で除外

### 財務データの利用可能性

- **開示日ベース**: `disclosed_date <= rebalance_date`
- **最新値取得**: `groupby('code').tail(1)` で各銘柄の最新決算
- **年次のみフィルタ**: `fiscal_quarter == 'FY'`

## パフォーマンス差分の分析

### Legacy vs 再現版

| 指標 | Legacy | 再現版 | 差分 |
|------|--------|--------|------|
| 年率リターン | +28.52% | +24.27% | -4.25%pt |
| リバランス回数 | 9回 | 9回 | ✅ |
| 最大DD（年次） | -2.41% | -12.49% | -10.08%pt |
| シャープレシオ | 1.47 | 0.86 | -0.61 |

### 差分の原因候補

1. **価格取得タイミング**:
   - 再現版: first() / last()
   - Legacy: 具体的な実装未確認

2. **100株単位制限**:
   - 再現版: int(amount / (price * 100)) * 100
   - Legacy: build_unit_share_portfolio() 関数

3. **税金計算**:
   - 再現版: 期間ごと
   - Legacy: 年次 + 累積

4. **銘柄選定**:
   - 再現版: nsmallest(20, 'pbr')
   - Legacy: 50銘柄から選択？

## 推奨実装パターン

### バックテストの基本構造

```python
# 1. データ読み込み
df_price = pd.read_parquet('prices.parquet')
df_fin = pd.read_parquet('financials.parquet')

# 2. リバランス日設定
rebalance_dates = [find_first_trading_day_after(f'{y}-10-01')
                   for y in range(2016, 2026)]

# 3. 財務データ事前処理
fin_by_date = {}
for rdate in rebalance_dates:
    available = df_fin[df_fin['disclosed_date'] <= rdate]
    latest = available.groupby('code').tail(1)
    fin_by_date[rdate] = latest

# 4. バックテストループ
cumulative_capital = INITIAL_CAPITAL
for i in range(len(rebalance_dates) - 1):
    start_date = rebalance_dates[i]
    end_date = rebalance_dates[i + 1]

    # 価格取得（前後5日猶予）
    start_prices = get_prices_with_window(df_price, start_date, days=5, method='first')
    end_prices = get_prices_with_window(df_price, end_date, days=5, method='last')

    # 銘柄選定
    merged = merge_price_and_fin(start_prices, fin_by_date[start_date])
    selected = select_stocks(merged, n=20)

    # ポートフォリオ構築
    portfolio = build_portfolio(selected, cumulative_capital, unit=100)

    # リターン計算
    profit = calculate_profit(portfolio, end_prices)
    tax = max(profit, 0) * TAX_RATE
    net_return = (profit - tax) / cumulative_capital

    # 累積資本更新
    cumulative_capital *= (1 + net_return)
```

## 次の改善ポイント

### 1. 日次MDD計算
- 簡易版（線形補間）: -12.49%
- 正確版（日次価格評価）: 目標-37.76%

### 2. 細かい差分の解消
- Legacy notebookの詳細実装を完全一致させる
- 4.25%ptの差分を0.5%pt以内に

### 3. 改善戦略の追加
- ベースライン + 出来高フィルタ
- ベースライン + 低PER
- ベースライン + PEG的スコア
