# 実装計画: 売買履歴＆損益管理機能

**作成日**: 2026-03-11
**優先度**: 中（デプロイ後）
**推定工数**: 4〜6時間

---

## 背景

現在の投資判断支援アプリは「保持中の銘柄」のみを管理しています。ユーザーから以下の要望がありました：

1. **売買履歴の記録**: 利益確定/損失確定時の理由を記録したい
2. **損益の可視化**: 実現損益と含み損益を分けて表示したい
3. **余力の管理**: 税金考慮で現在の投資可能額を知りたい

---

## 目標

### ゴール
- 売却機能の実装
- 売買履歴の永続化
- 損益サマリー画面の作成
- 余力計算機能

### 成功指標
- 売却理由を記録できる
- 実現損益が正確に計算される
- 税金を考慮した余力が表示される

---

## 機能仕様

### 機能1: 売却機能

#### UI
- 詳細画面に「📤 売却」ボタンを追加
- 売却フォーム:
  - 売却日（日付選択）
  - 売却価格（数値入力）
  - 売却理由（テキストエリア）
    - 例: 「目標価格到達」「損切り」「資金需要」

#### データフロー
1. ユーザーが売却ボタンをクリック
2. 売却フォームを表示
3. 売却情報を入力
4. 売却実行:
   - `hypotheses.json` から該当銘柄を削除
   - `trading_history.json` に売却記録を追加
   - 損益を計算（売却価格 - 購入価格）

---

### 機能2: 売買履歴データ構造

#### ファイル: `data/trading_history.json`

```json
[
  {
    "id": "uuid-1234",
    "code": "72030",
    "name": "トヨタ自動車",
    "purchase_date": "2026-03-09",
    "purchase_price": 3000,
    "purchase_reason": "中計で注目している",
    "sell_date": "2026-03-15",
    "sell_price": 3500,
    "sell_reason": "目標価格到達",
    "realized_profit": 500,
    "realized_profit_rate": 16.67,
    "holding_days": 6,
    "tax_amount": 101.575,
    "after_tax_profit": 398.425,
    "original_hypothesis_id": "original-uuid",
    "created_at": "2026-03-09T10:00:00",
    "sold_at": "2026-03-15T15:30:00"
  }
]
```

#### フィールド説明
- `realized_profit`: 実現損益（売却価格 - 購入価格）
- `realized_profit_rate`: 実現損益率（%）
- `tax_amount`: 税金額（利益 × 0.20315、損失時は0）
- `after_tax_profit`: 税引き後利益

---

### 機能3: 損益サマリー画面

#### レイアウト

```
📊 損益サマリー
================

【実現損益】
  売却済み銘柄数: 3銘柄
  累計実現損益: +5,000円
  累計税金: 1,015円
  税引き後利益: 3,985円

【含み損益】
  保持中銘柄数: 2銘柄
  累計含み損益: +2,000円

【合計損益】
  実現+含み: +7,000円

【年間損益（2026年）】
  実現損益: +5,000円
  税金: 1,015円
  ※確定申告用
```

#### 計算ロジック

**実現損益**:
```python
realized_profit = sum([
    record["realized_profit"]
    for record in trading_history
])
```

**税金**:
```python
tax_total = sum([
    max(0, record["realized_profit"]) * 0.20315
    for record in trading_history
])
```

**含み損益**:
```python
unrealized_profit = sum([
    (current_price - hypo["purchase_price"])
    for hypo in hypotheses
])
```

---

### 機能4: 余力計算

#### 計算式

```python
# 初期資金（固定値、設定画面で入力）
initial_capital = 1_000_000  # 100万円

# 累計投資額（現在保有中の銘柄）
current_investment = sum([
    hypo["purchase_price"] * hypo.get("shares", 100)
    for hypo in hypotheses
])

# 累計売却額（税引き後）
cumulative_sales = sum([
    record["sell_price"] - record["tax_amount"]
    for record in trading_history
])

# 余力
available_capital = initial_capital - current_investment + cumulative_sales
```

#### UI表示

```
💰 余力
=======

初期資金: 1,000,000円
現在保有額: 600,000円
累計売却額: 350,000円（税引き後）
------------------------
余力: 750,000円
```

---

## 実装ステップ

### Phase 1: データ構造とバックエンド（2時間）

#### ステップ1: データモデル作成
- [ ] `src/models.py` 新規作成
- [ ] `TradingRecord` データクラス定義
- [ ] 税金計算関数 `calculate_tax(profit)`

#### ステップ2: 売買履歴管理
- [ ] `src/trading_history.py` 新規作成
- [ ] `load_trading_history()`
- [ ] `save_trading_history()`
- [ ] `add_sell_record()`

#### ステップ3: 損益計算
- [ ] `src/profit_calculator.py` 新規作成
- [ ] `calculate_realized_profit()`
- [ ] `calculate_unrealized_profit()`
- [ ] `calculate_total_profit()`
- [ ] `calculate_available_capital()`

---

### Phase 2: UI実装（2時間）

#### ステップ4: 売却機能
- [ ] `app.py` に売却ボタン追加（詳細画面）
- [ ] 売却フォーム実装
- [ ] 売却処理実装
  - `hypotheses.json` から削除
  - `trading_history.json` に追加

#### ステップ5: 損益サマリー画面
- [ ] サイドバーに「📊 損益サマリー」メニュー追加
- [ ] `render_profit_summary()` 関数作成
- [ ] 実現損益セクション
- [ ] 含み損益セクション
- [ ] 合計損益セクション

#### ステップ6: 余力表示
- [ ] `render_available_capital()` 関数作成
- [ ] 初期資金設定機能（設定画面）
- [ ] 余力計算＆表示

---

### Phase 3: 売買履歴一覧画面（1時間）

#### ステップ7: 履歴画面
- [ ] `render_trading_history()` 関数作成
- [ ] テーブル表示（pandas DataFrame）
- [ ] フィルタリング機能（年ごと、銘柄ごと）
- [ ] ソート機能（日付、損益）

---

### Phase 4: テストとドキュメント（1時間）

#### ステップ8: テスト
- [ ] 売却機能のテスト
- [ ] 損益計算の検証
- [ ] 税金計算の検証

#### ステップ9: ドキュメント
- [ ] `docs/knowledges/` にナレッジ追加
- [ ] `docs/sessions/` にセッション記録
- [ ] README更新

---

## データベース設計（将来）

現在はJSONファイルですが、将来的にはSQLiteやPostgreSQLへの移行を検討：

```sql
CREATE TABLE trading_history (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT,
    purchase_date DATE NOT NULL,
    purchase_price REAL NOT NULL,
    purchase_reason TEXT,
    sell_date DATE NOT NULL,
    sell_price REAL NOT NULL,
    sell_reason TEXT,
    realized_profit REAL,
    tax_amount REAL,
    holding_days INTEGER,
    created_at TIMESTAMP,
    sold_at TIMESTAMP
);

CREATE INDEX idx_sell_date ON trading_history(sell_date);
CREATE INDEX idx_code ON trading_history(code);
```

---

## 税金計算の詳細

### 日本の株式譲渡所得税

- **税率**: 20.315%
  - 所得税: 15%
  - 住民税: 5%
  - 復興特別所得税: 0.315%

### 計算式

```python
def calculate_tax(profit: float) -> float:
    """
    株式譲渡所得税を計算

    Args:
        profit: 実現損益（売却価格 - 購入価格）

    Returns:
        税金額（損失時は0）
    """
    if profit <= 0:
        return 0.0

    tax_rate = 0.20315
    return profit * tax_rate
```

### 損益通算

- 同一年内の利益と損失は通算可能
- 損失が出た場合、翌年3年間繰越可能（確定申告必要）

**実装方針**:
- 年ごとに損益を集計
- 利益と損失を相殺
- 純利益に対して税率を適用

---

## UI/UXの考慮事項

### モバイル最適化
- テーブルはスクロール可能に
- メトリックは `st.metric()` で強調
- グラフは横幅いっぱいに

### エラーハンドリング
- 売却価格が負の値 → エラー
- 売却日が購入日より前 → エラー
- データ不整合 → 警告表示

### パフォーマンス
- 履歴が増えても高速に表示
- キャッシュ機能の活用

---

## リスクと対策

### リスク1: データ損失
- **対策**: 定期バックアップ機能
- **対策**: CSVエクスポート機能

### リスク2: 税金計算の誤り
- **対策**: 税理士監修
- **対策**: 免責事項の表示

### リスク3: 複雑化
- **対策**: シンプルなUIを維持
- **対策**: 段階的な機能追加

---

## 参考リンク

- [国税庁: 株式等の譲渡所得](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1463.htm)
- [損益通算について](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2250.htm)

---

## 次のステップ

1. ✅ 計画作成（このドキュメント）
2. ⏸️ デプロイ完了後に実装開始
3. ⏸️ Phase 1から順番に実装

---

**推定工数**: 4〜6時間
**優先度**: 中（デプロイ完了後）
