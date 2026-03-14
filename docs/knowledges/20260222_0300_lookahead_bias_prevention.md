# ルックアヘッドバイアスの予防と検出方法

**作成日**: 2026-02-22 03:00
**カテゴリ**: バックテスト、データ品質、リスク管理
**重要度**: 🚨 最高

---

## 概要

バックテストにおける**ルックアヘッドバイアス（lookahead bias）**は、実運用では利用不可能な未来の情報を使用してしまう、致命的なエラーです。

本ドキュメントは、2026-02-22の「理論株価×モメンタム戦略」で発見されたルックアヘッドバイアスから得られた教訓をまとめたものです。

---

## ルックアヘッドバイアスとは

### 定義

バックテストで、**その時点では入手不可能な未来の情報**を使用してしまうエラー。

### 具体例

```python
# ❌ 間違い（ルックアヘッドバイアス）
# 2017-10-02時点で、2018-04-02までの株価（未来）を使用
disclosed_date = '2017-10-02'
price_at_disclosed = price[disclosed_date]
price_6m_after = price[disclosed_date + 180days]  # ❌ 未来！
return_6M = (price_6m_after - price_at_disclosed) / price_at_disclosed

# ✅ 正しい（過去のデータのみ使用）
# 2017-10-02時点で、2017-04-05までの株価（過去）を使用
disclosed_date = '2017-10-02'
price_at_disclosed = price[disclosed_date]
price_6m_before = price[disclosed_date - 180days]  # ✅ 過去
return_6M = (price_at_disclosed - price_6m_before) / price_6m_before
```

---

## 実際の被害事例

### 2026-02-22: 理論株価×モメンタム戦略

**発見された問題**:
- prediction_scores.csvの`return_6M`列が**未来のリターン**を含んでいた
- バックテストで「未来のリターンが高い銘柄」を選択していた

**影響**:
- 修正前: 年率+34.88%（非現実的）
- 修正後: 年率-1.20%（現実的）
- 差分: **-36.08%pt**

**結論**:
- 元の戦略は実運用では**完全に使用不可**
- 年率+34.88%は幻想だった

---

## ルックアヘッドバイアスの検出方法

### 1. 異常に高いリターンを疑う

**警戒すべき兆候**:
- 年率+30%超（日本株の場合）
- シャープレシオ > 2.0
- 最大ドローダウン < 5%
- 勝率 > 80%

**対応**:
- 必ずロジックを再確認
- サンプルデータで手動検証
- 他の戦略と比較

### 2. データの出所を確認

**チェックリスト**:
- ✅ データの生成方法を確認
- ✅ 外部データの場合、生成スクリプトを読む
- ✅ 「予測」「リターン」などの列名に注意
- ✅ 時系列データの参照方向を確認（過去 or 未来）

### 3. サンプルで手動検証

**手順**:
1. 1銘柄の10期間を抽出
2. データ内の値と、実際の計算結果を比較
3. 一致しない場合、計算方法を確認

**例**:

```python
# 検証スクリプト
sample_code = '13010'
sample_dates = df[df['code'] == sample_code]['disclosed_date'].head(10)

for disclosed_date in sample_dates:
    # データ内の値
    data_return_6m = df.loc[(df['code'] == sample_code) &
                             (df['disclosed_date'] == disclosed_date), 'return_6M'].values[0]

    # 実際の計算（未来のリターン）
    price_at_disclosed = price[disclosed_date]
    price_6m_after = price[disclosed_date + 180days]
    actual_future_return = (price_6m_after - price_at_disclosed) / price_at_disclosed

    # 比較
    diff = abs(data_return_6m - actual_future_return)
    print(f"{disclosed_date}: データ={data_return_6m:.2%}, 未来={actual_future_return:.2%}, 差={diff:.2%}")
```

**判定基準**:
- 平均誤差 < 2%pt: データが未来を含んでいる可能性が高い
- 平均誤差 > 10%pt: データは過去を使用している可能性が高い

### 4. 時系列の整合性を確認

**チェックポイント**:

| 時点 | 利用可能なデータ | 利用不可なデータ |
|------|-----------------|-----------------|
| t日引け | t日までの株価、t-1期までの財務 | t+1日以降の株価、t期以降の未開示財務 |
| t日寄り | t-1日までの株価、t-1期までの財務 | t日以降の株価、t期以降の未開示財務 |

**日本株の実運用タイミング**:
```
t日引け: シグナル確定
↓
t+1日寄り: 売買執行（約定）
```

**注意点**:
- t日引けのシグナルで、t+1日以降のデータを使用してはいけない
- 財務データは`disclosed_date`（開示日）以降しか使用できない

---

## ルックアヘッドバイアスを防ぐ設計原則

### 原則1: Point-in-Time Database

**概念**:
- 各時点で**実際に利用可能だった情報のみ**を使用
- 「今日時点で知り得た情報」を厳密に管理

**実装例**:

```python
def get_available_data(target_date):
    """target_date時点で利用可能なデータのみを取得"""
    # 株価: target_date以前
    prices = df_price[df_price['date'] <= target_date]

    # 財務: disclosed_date <= target_date
    financials = df_fin[df_fin['disclosed_date'] <= target_date]

    return prices, financials
```

### 原則2: 明示的な時間方向の指定

**良い設計**:
```python
# 変数名で時間方向を明示
return_6M_past = calculate_past_return(price, disclosed_date, months=6)
return_6M_future = calculate_future_return(price, disclosed_date, months=6)  # 検証用のみ
```

**悪い設計**:
```python
# 時間方向が不明
return_6M = calculate_return(price, disclosed_date, months=6)  # 過去？未来？
```

### 原則3: バックテストと検証の分離

**構造**:
```
data/
├── features/
│   └── stock_features_point_in_time.parquet    # Point-in-Time特徴量
├── labels/
│   └── future_returns.parquet                  # 未来のリターン（検証用）
└── ...
```

**ルール**:
- **バックテストでは`features/`のみ使用**
- `labels/`は予測精度の検証にのみ使用
- バックテストと検証を明確に分離

### 原則4: 外部データの監査

**チェックリスト**:
- ✅ データの生成スクリプトを読む
- ✅ 各列の計算方法を確認
- ✅ 時系列の参照方向を確認
- ✅ サンプルで手動検証

---

## よくあるルックアヘッドバイアスのパターン

### パターン1: 未来のリターンを特徴量として使用

**例**:
```python
# ❌ 間違い
features['momentum_6M'] = calculate_return(price, date, months=6, direction='forward')  # 未来

# ✅ 正しい
features['momentum_6M'] = calculate_return(price, date, months=6, direction='backward')  # 過去
```

### パターン2: 未開示の財務データを使用

**例**:
```python
# ❌ 間違い
# 2020-03-31期（開示日: 2020-05-15）のデータを、2020-04-01に使用
financials = df_fin[df_fin['fiscal_period_end'] <= target_date]  # fiscal_period_endで判定

# ✅ 正しい
# disclosed_date（開示日）で判定
financials = df_fin[df_fin['disclosed_date'] <= target_date]
```

### パターン3: 調整後株価（Adjusted Close）の遡及的修正

**問題**:
- 株式分割や配当が発生すると、過去の調整後株価が変更される
- バックテストでは「現在の調整後株価」を使用するため、問題ない

**注意点**:
- 実運用では「その時点の調整後株価」を使用する必要がある
- ただし、日本の実務では「現在の調整後株価」を使用することが一般的

### パターン4: 生存バイアス（Survivorship Bias）

**問題**:
- 現在も上場している銘柄のみでバックテスト
- 上場廃止銘柄を除外すると、パフォーマンスが過大評価される

**対策**:
- 上場廃止銘柄も含めてバックテスト
- 上場廃止時の処理を明示的に定義

---

## 推奨される開発フロー

### ステップ1: データ生成

```python
# 01_generate_features.py
# Point-in-Time特徴量の生成
for date in all_dates:
    available_data = get_available_data(date)  # その時点で利用可能なデータのみ
    features = calculate_features(available_data)
    save_features(features, date)
```

### ステップ2: 検証用ラベルの生成

```python
# 02_generate_labels.py
# 未来のリターン（検証用）
for date in all_dates:
    future_prices = get_future_prices(date, months=6)
    labels = calculate_future_returns(future_prices)
    save_labels(labels, date)  # バックテストでは使用禁止
```

### ステップ3: バックテスト

```python
# 03_backtest.py
# バックテストではfeaturesのみ使用
for rebalance_date in rebalance_dates:
    features = load_features(rebalance_date)  # Point-in-Time特徴量
    selected_stocks = strategy(features)  # labelsは使用しない
    execute_trades(selected_stocks)
```

### ステップ4: 検証

```python
# 04_validate.py
# 予測精度の検証（バックテストとは別）
features = load_features(all_dates)
labels = load_labels(all_dates)  # ここで初めて使用
accuracy = evaluate(features, labels)
```

---

## ツールとチェックリスト

### バックテスト前のチェックリスト

- [ ] データの生成方法を確認した
- [ ] 外部データの計算方法を確認した
- [ ] サンプルで手動検証した
- [ ] 時系列の整合性を確認した
- [ ] 異常に高いリターンを疑った
- [ ] Point-in-Time原則を守った

### バックテスト後のチェックリスト

- [ ] 年率リターンが現実的か（日本株: 10-20%程度）
- [ ] シャープレシオが現実的か（< 2.0）
- [ ] 最大ドローダウンが現実的か（> 10%）
- [ ] 他の戦略と比較した
- [ ] サンプル期間で再検証した

---

## 参考: 今回の事例の詳細

### 発見のきっかけ

ユーザーの指示:
> 「新しいスクリプトと元のスクリプトで結果が大きく違うのであれば、元のスクリプトのロジックに非現実的な点がないか洗い出す必要がある。ルックフォワードなどないか確認願う」

### 検証方法

1. サンプルデータで手動計算
2. データ内return_6Mと実際の未来6ヶ月リターンを比較
3. 平均誤差 < 2%ptで一致 → ルックアヘッドバイアスと確定

### 修正方法

```python
# 修正前（間違い）
price_6m_after = price[disclosed_date + 180days]
return_6M = (price_6m_after - price_at_disclosed) / price_at_disclosed

# 修正後（正しい）
price_6m_before = price[disclosed_date - 180days]
return_6M = (price_at_disclosed - price_6m_before) / price_6m_before
```

### 影響

- 年率リターン: +34.88% → -1.20%（差分-36.08%pt）
- シャープレシオ: 1.07 → -0.31
- 最大DD: -1.10% → -21.14%

---

## まとめ

### 重要な教訓

1. **異常に高いリターンは必ず疑う**
2. **データの出所と計算方法を確認**
3. **サンプルで手動検証**
4. **Point-in-Time原則を守る**
5. **バックテストと検証を分離**

### 金言

> 「バックテストで年率+30%を超えたら、まずルックアヘッドバイアスを疑え」

> 「完璧なバックテストは存在しない。しかし、ルックアヘッドバイアスのないバックテストは作れる」

---

**参考文献**:
- docs/sessions/20260222_0130_lookahead_bias_discovered.md
- docs/reports/20260222_lookahead_correction_complete.md
- analyses/20260222_0200_correct_lookahead_bias/

**関連トピック**:
- バックテスト設計
- データ品質管理
- Point-in-Time Database
- 生存バイアス（Survivorship Bias）
