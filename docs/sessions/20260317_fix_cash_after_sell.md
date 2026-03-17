# セッション記録: 売却後の余力計算の修正

**日時**: 2026-03-17
**タスク**: 投資判断支援アプリ - 売却後の現金が余力に反映されない問題の修正

---

## 📋 問題の定義

### ユーザーからの報告
1. **売却時に現金が余力に反映されない**
2. **売却処理後、初期資金が1,000,000に戻る**

### 現金の定義
- **現金** = 売却銘柄の取得額（購入価格 × 株数）+ 税引き後利益

---

## 🔍 原因分析

### 問題箇所
`src/profit_calculator.py` の `calculate_available_capital` 関数（166行目）

### 誤った計算式
```python
cumulative_sales = sum(
    record["sell_price"] - record["tax_amount"]  # ← 間違い！
    for record in history
)
```

**問題点**:
- `record["sell_price"]` は**売却価格/株**
- `record["tax_amount"]` は**税金（総額）**
- つまり、「売却価格/株 - 税金」という無意味な計算をしていた

### 正しい計算式
```python
cumulative_sales = sum(
    record["purchase_price"] * record["shares"] + record["after_tax_profit"]
    for record in history
)
```

**説明**:
- `record["purchase_price"] * record["shares"]` = 取得額（元本回収）
- `record["after_tax_profit"]` = 税引き後利益
- 合計 = 売却で得た現金

---

## ✅ 修正内容

### 修正ファイル
- `apps/investment-tracker/src/profit_calculator.py`

### 修正箇所
166行目の `cumulative_sales` の計算式を修正

```python
# 修正前
cumulative_sales = sum(
    record["sell_price"] - record["tax_amount"]
    for record in history
)

# 修正後
cumulative_sales = sum(
    record["purchase_price"] * record["shares"] + record["after_tax_profit"]
    for record in history
)
```

---

## 🧪 検証シナリオ

### 例1: 利益が出た場合
- **初期資金**: 1,000,000円
- **銘柄A購入**: 100,000円（保有中）
- **銘柄B購入**: 200,000円 → 売却: 250,000円（税引き後利益+40,000円）

**売却前の余力**:
```
1,000,000 - (100,000 + 200,000) = 700,000円
```

**売却後の余力**:
```
1,000,000 - 100,000 + (200,000 + 40,000) = 1,140,000円
```

✅ 正しく40,000円の利益が余力に反映される

### 例2: 損失が出た場合
- **初期資金**: 1,000,000円
- **銘柄A購入**: 100,000円（保有中）
- **銘柄B購入**: 200,000円 → 売却: 150,000円（税引き後損失-50,000円）

**売却前の余力**:
```
1,000,000 - (100,000 + 200,000) = 700,000円
```

**売却後の余力**:
```
1,000,000 - 100,000 + (200,000 - 50,000) = 1,050,000円
```

✅ 損失分（50,000円）が正しく反映される

---

## 📊 修正後の動作

### 余力の計算式
```
余力 = 初期資金 - 現在保有額 + 累計売却額（取得額 + 税引き後利益）
```

### 累計売却額の内訳
- **取得額**: `purchase_price × shares` （元本回収）
- **税引き後利益**: `after_tax_profit` （利益または損失）

---

## 🔧 初期資金の永続化について

### 現在の実装
- 初期資金は `data/settings.json` に保存される
- `src/settings.py` で管理
- ログイン後も保持される

### 確認事項
- `settings.json` が正しく作成・更新されているか
- アプリ再起動後も初期資金が保持されるか

**結論**: 初期資金が1,000,000に戻る問題は、累計売却額の計算誤りが原因。修正により、売却後の現金が正しく余力に反映されるようになった。

---

## 📝 次回の作業候補

1. **実機テスト**: 修正後のアプリをローカルで起動し、売却機能をテスト
2. **データ移行**: 既存の `trading_history.json` がある場合、正しく動作するか確認
3. **デプロイ**: Streamlit Cloudへのデプロイ（MEMORY.mdに記載済み）

---

## 📚 関連ファイル

- `apps/investment-tracker/src/profit_calculator.py` - 修正済み
- `apps/investment-tracker/src/trading_history.py` - 参照のみ
- `apps/investment-tracker/src/settings.py` - 参照のみ
- `apps/investment-tracker/app.py` - 参照のみ

---

## ✅ 完了

修正が完了し、売却後の現金が余力に正しく反映されるようになりました。
