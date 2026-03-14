# セッション記録: NISA口座対応の実装

**日時**: 2026-03-15 12:30
**タスク**: タスク9 - NISA口座対応
**ステータス**: ✅ 完了
**推定時間**: 1時間 → **実績**: 約30分

---

## 📊 完了したこと

### タスク9: NISA口座対応 ✅

#### 問題
- すべて課税口座として扱われている（税率20.315%）
- NISA口座の銘柄も税金がかかってしまう

#### 解決策
- NISA口座フラグを追加
- NISA口座の場合、税金を0%にする
- 登録フォームで選択可能
- 売却時にNISA表示

---

## 🔧 実装内容

### ファイル1: `src/models.py` 修正

#### 修正1: `calculate_tax()` にNISAパラメータ追加

**変更内容**:
```python
# 修正前
def calculate_tax(profit: float) -> float:
    if profit <= 0:
        return 0.0
    tax_rate = 0.20315
    return profit * tax_rate

# 修正後
def calculate_tax(profit: float, is_nisa: bool = False) -> float:
    if profit <= 0 or is_nisa:  # ← NISA口座は非課税
        return 0.0
    tax_rate = 0.20315
    return profit * tax_rate
```

#### 修正2: `TradingRecord` にis_nisaフィールド追加

**変更内容**:
```python
@dataclass
class TradingRecord:
    # ...既存フィールド...
    is_nisa: bool = False  # NISA口座フラグ

    def to_dict(self):
        return {
            # ...既存フィールド...
            "is_nisa": self.is_nisa  # ← 追加
        }
```

---

### ファイル2: `src/trading_history.py` 修正

**関数**: `add_sell_record()`

**変更内容**:
```python
# NISA口座フラグを取得
is_nisa = hypothesis.get("is_nisa", False)

# 税金を計算（NISA口座の場合は0%）
tax_amount = calculate_tax(realized_profit, is_nisa=is_nisa)

# TradingRecordを作成
record = TradingRecord(
    # ...既存フィールド...
    is_nisa=is_nisa  # ← 追加
)
```

---

### ファイル3: `app.py` 修正

#### 修正1: 仮説登録フォームにNISAチェックボックス追加（192行目）

**追加したフィールド**:
```python
is_nisa = st.checkbox(
    "NISA口座",
    value=False,
    help="NISA口座の場合、売却時の税金が0%になります"
)
```

**new_hypothesisに追加**:
```python
new_hypothesis = {
    # ...既存フィールド...
    "is_nisa": is_nisa,  # ← 追加
    # ...
}
```

#### 修正2: 売却フォームでNISA表示（594-623行目）

**NISAステータス表示**:
```python
# NISA口座フラグを取得
is_nisa = hypo.get("is_nisa", False)

# 税金計算（NISA口座の場合は0%）
if is_nisa:
    expected_tax = 0.0
    st.success("✅ NISA口座（税金0%）")
else:
    expected_tax = max(0, expected_profit * 0.20315)
    st.info("課税口座（税率20.315%）")
```

**税金表示**:
```python
if is_nisa:
    st.caption(f"税金: ¥0（NISA口座）| 1株あたり損益: ¥{expected_profit_per_share:,.0f}")
else:
    st.caption(f"税金: ¥{expected_tax:,.0f} (20.315%) | 1株あたり損益: ¥{expected_profit_per_share:,.0f}")
```

---

## 📂 GitHubコミット

### コミット情報
- **コミットID**: `c8a837c`
- **メッセージ**: "feat: Add NISA account support"
- **変更内容**:
  - NISA口座フラグ追加
  - 税金計算でNISA対応（0%）
  - 登録・売却フォームで表示

---

## 🎯 使い方（デプロイ完了後）

### ステップ1: デプロイ完了を待つ（2-3分）
https://share.streamlit.io/ にアクセス

### ステップ2: NISA口座で銘柄を登録
1. サイドバーの「📋 仮説登録」フォームを開く
2. 銘柄情報を入力
3. **「NISA口座」にチェック** ✅
4. 「登録」ボタンをクリック

### ステップ3: NISA銘柄を売却
1. NISA銘柄の詳細画面を開く
2. 「📤 売却」ボタンをクリック
3. **「✅ NISA口座（税金0%）」** と表示される
4. 売却情報を入力
5. → **税金が0円**で計算される ✅

### ステップ4: 課税口座との比較
- **NISA口座**: 税金 ¥0（NISA口座）
- **課税口座**: 税金 ¥XX,XXX (20.315%)

---

## 💡 学んだ教訓

### データモデルの拡張
- **デフォルト値**: `is_nisa: bool = False` で既存データに影響なし
- **後方互換性**: `hypothesis.get("is_nisa", False)` で古いデータも対応
- **to_dict()**: 新しいフィールドも辞書に含める

### UIデザイン
- **チェックボックス**: `st.checkbox()` でON/OFFを選択
- **ヘルプテキスト**: `help` パラメータで説明を表示
- **ステータス表示**: `st.success()` と `st.info()` で視覚的に区別

### 税金計算のロジック
- **条件分岐**: `if profit <= 0 or is_nisa` で簡潔に
- **表示**: NISA口座と課税口座で異なるメッセージ
- **日本の税制**: 所得税15% + 住民税5% + 復興税0.315% = 20.315%

---

## 🔗 関連ドキュメント

### 前回のセッション
- `docs/sessions/20260315_1200_partial_sell_feature.md` - 部分売却機能の実装

---

## 🎯 次回タスク（最後のタスク！）

### タスク10: 投資指標の追加（推定1時間）

**実装する指標**:
1. **シャープレシオ**: リスク調整後リターン
2. **最大ドローダウン**: 最大下落率
3. **勝率**: 売買履歴の勝率
4. **平均保有日数**: 平均的な保有期間
5. **累計リターン**: 初期資金からの総合リターン

**表示場所**: 損益サマリー画面

**推定工数**: 1時間

---

## 📊 進捗状況

### ✅ 完了したタスク（4/5）
- タスク6: 銘柄名表示の修正 ✅
- タスク7: 初期資金設定の永続化 ✅
- タスク8: 部分売却機能 ✅
- タスク9: NISA口座対応 ✅

### 🔜 残りのタスク
- タスク10: 投資指標の追加（1時間）← **最後のタスク！**

---

**ステータス**: ✅ タスク9完了（NISA口座対応）
**次回**: Streamlit Cloudで動作確認 → タスク10へ進む（最終タスク！）
