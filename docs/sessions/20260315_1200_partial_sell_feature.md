# セッション記録: 部分売却機能の実装

**日時**: 2026-03-15 12:00
**タスク**: タスク8 - 部分売却機能の実装
**ステータス**: ✅ 完了
**推定時間**: 1時間 → **実績**: 約30分

---

## 📊 完了したこと

### タスク8: 部分売却機能 ✅

#### 問題
- 全株売却しかできない
- 一部だけ売却したい場合でも、仮説一覧から削除される

#### 解決策
- 売却数量を指定できるようにする
- 部分売却時: 残株数を計算して仮説を更新（削除しない）
- 全株売却時: 仮説から削除（既存の動作）

---

## 🔧 実装内容

### ファイル1: `src/trading_history.py` 修正

**関数**: `add_sell_record()`

**変更内容**:
```python
# 修正前
def add_sell_record(
    hypothesis: Dict,
    sell_date: str,
    sell_price: float,
    sell_reason: str
) -> TradingRecord:
    shares = hypothesis.get("shares", 100)  # 全株

# 修正後
def add_sell_record(
    hypothesis: Dict,
    sell_date: str,
    sell_price: float,
    sell_reason: str,
    sell_shares: int = None  # ← 追加
) -> TradingRecord:
    total_shares = hypothesis.get("shares", 100)
    shares = sell_shares if sell_shares is not None else total_shares  # 売却数量
```

**ポイント**:
- `sell_shares` パラメータを追加（デフォルトはNoneで全株売却）
- 売却数量のみを売買履歴に記録

---

### ファイル2: `app.py` 修正

#### 修正1: 売却数量フィールドの追加（568-589行目）

**追加したフィールド**:
```python
sell_shares = st.number_input(
    "売却数量（株）",
    min_value=1,
    max_value=total_shares,
    value=total_shares,  # デフォルトは全株
    step=100,
    help=f"保有株数: {total_shares:,}株"
)
```

**予想損益の計算**:
```python
# 修正前: 全株で計算
expected_profit = expected_profit_per_share * shares

# 修正後: 売却数量で計算
expected_profit = expected_profit_per_share * sell_shares
```

**残株数の表示**:
```python
remaining_shares = total_shares - sell_shares
if remaining_shares > 0:
    st.info(f"**売却後の残株数**: {remaining_shares:,}株（保有継続）")
else:
    st.warning(f"**全株売却**: 仮説一覧から削除されます")
```

#### 修正2: 部分売却処理（600-627行目）

**部分売却の処理**:
```python
# 売却記録を追加（売却数量を指定）
record = add_sell_record(
    hypo,
    sell_date.strftime("%Y-%m-%d"),
    sell_price,
    sell_reason,
    sell_shares=sell_shares  # ← 追加
)

# 残株数を計算
remaining_shares = total_shares - sell_shares

if remaining_shares > 0:
    # 部分売却: 仮説の株数を更新
    for h in hypotheses:
        if h["id"] == hypothesis_id:
            h["shares"] = remaining_shares
            break
    save_hypotheses(hypotheses)

    st.success(f"✅ {hypo['name']} を{sell_shares:,}株売却しました（残{remaining_shares:,}株）")
else:
    # 全株売却: 仮説から削除
    hypotheses = [h for h in hypotheses if h["id"] != hypothesis_id]
    save_hypotheses(hypotheses)

    st.success(f"✅ {hypo['name']} を全株売却しました")
```

---

## 📂 GitHubコミット

### コミット情報
- **コミットID**: `2d5fa54`
- **メッセージ**: "feat: Add partial sell functionality"
- **変更内容**:
  - 売却数量パラメータ追加
  - 部分売却処理実装
  - 適切な成功メッセージ表示

---

## 🎯 使い方（デプロイ完了後）

### ステップ1: デプロイ完了を待つ（2-3分）
https://share.streamlit.io/ にアクセス

### ステップ2: 部分売却を試す
1. アプリにログイン
2. 保有銘柄の詳細画面を開く
3. 「📤 売却」ボタンをクリック
4. **「売却数量（株）」** を入力
   - 例: 保有1000株のうち300株だけ売却
5. 売却日、売却価格、売却理由を入力
6. 「✅ 売却を確定」をクリック

### ステップ3: 確認
- **部分売却の場合**:
  - 「✅ XX株売却しました（残XX株）」と表示される
  - 仮説一覧に残株数で表示される
  - 売買履歴に売却記録が追加される

- **全株売却の場合**:
  - 「✅ 全株売却しました」と表示される
  - 仮説一覧から削除される
  - 売買履歴に売却記録が追加される

---

## 💡 学んだ教訓

### UIデザイン
- **デフォルト値**: 売却数量のデフォルトは全株にして、変更しやすく
- **バリデーション**: max_valueで保有株数を超えないように制限
- **ヘルプテキスト**: 保有株数を表示して、ユーザーが確認しやすく

### ロジック設計
- **残株数の計算**: 売却前に計算して、分岐処理を明確に
- **条件分岐**: 残株数 > 0 なら更新、== 0 なら削除
- **メッセージ**: 部分売却と全株売却で異なるメッセージを表示

### 後方互換性
- **デフォルト引数**: `sell_shares=None` でデフォルトは全株売却
- **既存コードの動作**: パラメータを省略しても従来通り動作

---

## 🔗 関連ドキュメント

### 前回のセッション
- `docs/sessions/20260315_1130_initial_capital_persistence.md` - 初期資金設定の永続化

---

## 🎯 次回タスク

### タスク9: NISA口座対応（推定1時間）
**実装**:
1. 仮説登録フォームに「NISA口座」チェックボックス追加
2. データ構造に `is_nisa` フィールド追加
3. 売却時の税金計算: NISA口座は税金0%
4. 損益サマリーでNISA/課税口座を区別表示
5. 既存銘柄: デフォルト `is_nisa = false`

### タスク10: 投資指標の追加（推定1時間）
**実装する指標**:
1. シャープレシオ
2. 最大ドローダウン
3. 勝率
4. 平均保有日数
5. 累計リターン

---

**ステータス**: ✅ タスク8完了（部分売却機能）
**次回**: Streamlit Cloudで動作確認 → タスク9へ進む
