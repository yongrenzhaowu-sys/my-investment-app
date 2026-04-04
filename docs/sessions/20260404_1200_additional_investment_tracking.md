# セッション記録: 追加投資額トラッキング機能の実装

**日時**: 2026-04-04 12:00
**ステータス**: ✅ 完了
**成果物**:
- `apps/investment-tracker/src/settings.py`（修正）
- `apps/investment-tracker/src/profit_calculator.py`（修正）
- `apps/investment-tracker/app.py`（修正）

---

## 🎯 目的

楽天証券・楽天銀行のスイープ機能による追加投資額を正しく管理する機能を実装。

### 背景
- 楽天証券と楽天銀行の間で資金がスイープされる（自動入出金）
- 初期資金 + 利益確定額を超える投資を行った場合、**投資可能額がマイナス**になる
- このマイナス分は、実際には楽天銀行から追加で入金された資金（追加投資）
- ユーザー要望：初期資金と追加投資額を**別々に管理・表示**したい

---

## 🛠️ 実施した修正

### 1. `src/settings.py` の修正

#### 追加内容
```python
DEFAULT_SETTINGS = {
    "initial_capital": 1_000_000,
    "additional_capital": 0,  # 新規追加
}

def get_additional_capital() -> int:
    """追加投資額を取得（Streamlit Secrets優先、フォールバックでファイル読み込み）"""
    # Streamlit Secretsを試す
    try:
        import streamlit as st
        additional_capital = st.secrets.get("additional_capital", None)
        if additional_capital is not None:
            return int(additional_capital)
    except Exception:
        pass

    # Secretsがない場合は、settings.jsonから読み込み
    settings = load_settings()
    return int(settings.get("additional_capital", DEFAULT_SETTINGS["additional_capital"]))

def set_additional_capital(capital: float) -> bool:
    """追加投資額を設定"""
    settings = load_settings()
    settings["additional_capital"] = capital
    return save_settings(settings)
```

---

### 2. `src/profit_calculator.py` の修正

#### 修正内容
- `calculate_available_capital()`関数に`additional_capital`パラメータを追加
- 戻り値に`additional_capital`、`total_capital`を追加

#### 修正後の計算式
```python
def calculate_available_capital(
    hypotheses: List[Dict],
    initial_capital: float = 1_000_000,
    additional_capital: float = 0  # 新規パラメータ
) -> Dict[str, float]:
    # 合計投資額（初期資金 + 追加投資額）
    total_capital = initial_capital + additional_capital

    # 余力の計算
    available_capital = total_capital - current_investment - sold_purchase_amount + cumulative_sales

    return {
        "initial_capital": initial_capital,
        "additional_capital": additional_capital,  # 新規
        "total_capital": total_capital,  # 新規
        "current_investment": current_investment,
        "cumulative_sales": cumulative_sales,
        "available_capital": available_capital
    }
```

---

### 3. `app.py` の修正

#### 3.1 セッション状態の初期化（main関数）
```python
# 4. 追加投資額の設定（未設定の場合のみ読み込み）
if "additional_capital" not in st.session_state:
    from src.settings import get_additional_capital
    loaded_value = get_additional_capital()
    st.session_state.additional_capital = loaded_value
    print(f"DEBUG: 初回読み込み - additional_capital = {loaded_value}")
```

#### 3.2 投資可能額の計算呼び出し
```python
available = calculate_available_capital(
    hypotheses,
    st.session_state.initial_capital,
    st.session_state.additional_capital  # 新規追加
)
```

#### 3.3 損益計算の修正
```python
# 総資産と損益を計算
total_assets = available['current_investment'] + available['available_capital']
profit_loss = total_assets - available['total_capital']  # initial_capital → total_capital
profit_loss_rate = (profit_loss / available['total_capital'] * 100) if available['total_capital'] > 0 else 0
```

#### 3.4 損益サマリー画面の表示修正
```python
# 内訳表示
st.write("**内訳：**")

col1, col2 = st.columns(2)
with col1:
    st.metric("保有証券", f"¥{available['current_investment']:,.0f}", help=f"{len(hypotheses)}銘柄保有中")
with col2:
    st.metric("現金", f"¥{available['available_capital']:,.0f}", help="投資可能額")

col3, col4, col5 = st.columns(3)
with col3:
    st.metric("初期資金", f"¥{available['initial_capital']:,.0f}", help="最初に投入した資金")
with col4:
    st.metric("追加投資額", f"¥{available['additional_capital']:,.0f}", help="楽天銀行からスイープされた追加資金")
with col5:
    st.metric("合計投資額", f"¥{available['total_capital']:,.0f}", help="初期資金 + 追加投資額")
```

#### 3.5 追加投資額設定UIの追加
```python
with st.expander("💰 追加投資額設定"):
    st.info(f"**現在の追加投資額**: ¥{st.session_state.additional_capital:,}")
    st.caption("楽天銀行からスイープされた追加資金をここで管理します")

    # 仮の投資可能額を計算
    temp_available = calculate_available_capital(
        hypotheses,
        st.session_state.initial_capital,
        st.session_state.additional_capital
    )

    # 投資可能額がマイナスの場合、警告と自動計算ボタンを表示
    if temp_available['available_capital'] < 0:
        st.warning(f"⚠️ **投資可能額がマイナスです**: ¥{temp_available['available_capital']:,.0f}")
        st.info("💡 楽天銀行からスイープで資金が追加されている可能性があります")

        if st.button("🔄 追加投資額を自動計算", key="auto_calc_additional", type="primary"):
            # マイナス分を追加投資額に加算
            deficit = abs(temp_available['available_capital'])
            new_additional = st.session_state.additional_capital + deficit

            # セッション状態とファイルを更新
            st.session_state.additional_capital = new_additional
            settings = load_settings()
            settings["additional_capital"] = new_additional
            save_settings(settings)
            st.success(f"✅ 追加投資額を ¥{new_additional:,} に更新しました（マイナス分 ¥{deficit:,.0f} を追加）")
            st.rerun()

    st.divider()

    # 手動入力
    st.subheader("手動で設定")
    new_additional = st.number_input(
        "追加投資額（円）",
        min_value=0,
        value=int(st.session_state.additional_capital),
        step=100_000,
        key="new_additional_capital_input",
        help="楽天銀行からスイープされた追加資金を入力してください"
    )

    # 更新ボタン（変更検出付き）
    is_additional_changed = new_additional != st.session_state.additional_capital
    if st.button(
        "更新" if is_additional_changed else "更新（変更なし）",
        key="update_additional_capital",
        type="primary" if is_additional_changed else "secondary",
        disabled=not is_additional_changed
    ):
        # セッション状態とファイルを更新
        st.session_state.additional_capital = new_additional
        settings = load_settings()
        settings["additional_capital"] = new_additional
        save_settings(settings)
        st.success(f"✅ 追加投資額を ¥{new_additional:,} に更新しました（永続化済み）")
        st.rerun()
```

#### 3.6 累計リターン計算の修正
```python
# 累計リターン（合計投資額に対するリターン）
total_return = calculate_total_return(
    available['total_capital'],  # initial_capital → total_capital
    available['current_investment'],
    unrealized['total_unrealized'],
    available['cumulative_sales']
)
```

---

## 📊 新機能の詳細

### 1. 追加投資額の自動計算
- **トリガー**: 投資可能額がマイナスの場合
- **動作**:
  1. マイナス分（不足額）を計算
  2. 現在の追加投資額に不足額を加算
  3. settings.jsonに保存
  4. 投資可能額が0以上になる

**例**:
```
初期資金: ¥1,000,000
追加投資額: ¥0
保有額: ¥1,200,000
利益確定額: ¥0
→ 投資可能額: -¥200,000

「🔄 追加投資額を自動計算」をクリック
→ 追加投資額: ¥200,000（自動的に設定）
→ 投資可能額: ¥0
```

### 2. 追加投資額の手動設定
- **入力フィールド**: 100,000円単位で入力可能
- **更新ボタン**: 値が変更された場合のみ有効化
- **永続化**: settings.jsonに保存

### 3. 表示の改善
- **初期資金**と**追加投資額**を別々に表示
- **合計投資額**（初期 + 追加）を表示
- 各メトリクスにヘルプテキストを追加

---

## ✅ テストシナリオ

### シナリオ1: 追加投資額の自動計算
1. アプリを起動
2. 「📊 損益サマリー」を選択
3. 保有額が初期資金を超えている場合、投資可能額がマイナス表示
4. 「💰 追加投資額設定」を展開
5. 警告メッセージを確認
6. 「🔄 追加投資額を自動計算」をクリック
7. ✅ 追加投資額が自動的に設定され、投資可能額が0以上になる

### シナリオ2: 追加投資額の手動設定
1. 「💰 追加投資額設定」を展開
2. 「手動で設定」セクションで金額を入力
3. 「更新」ボタンをクリック
4. ✅ 追加投資額が更新される
5. ✅ 投資可能額が再計算される

### シナリオ3: 表示の確認
1. 「📊 損益サマリー」の「内訳」セクションを確認
2. ✅ 「初期資金」「追加投資額」「合計投資額」が別々に表示される
3. ✅ 各メトリクスにヘルプテキストが表示される

### シナリオ4: 永続化の確認
1. 追加投資額を設定
2. ブラウザをリロード
3. ✅ 設定した追加投資額が保持される
4. settings.jsonを確認
5. ✅ `additional_capital`フィールドが保存されている

---

## 🎯 解決された問題

- ✅ 楽天銀行からのスイープによる追加投資額を正しく管理できる
- ✅ 初期資金と追加投資額を別々に表示・管理できる
- ✅ 投資可能額がマイナスになった場合、自動的に追加投資額として記録できる
- ✅ 合計投資額に対する正しい損益率が計算される

---

## 📝 今後の改善案

### 1. 追加投資額の履歴管理
- 追加投資額の変更履歴を記録
- いつ、いくら追加されたかを追跡

### 2. グラフ表示
- 初期資金、追加投資額、利益の推移をグラフ化
- 資金の流れを可視化

### 3. 通知機能
- 投資可能額がマイナスになった場合、アラート通知
- 自動計算を促すメッセージ

---

## 🔗 関連ファイル

- **計画書**: `docs/plans/20260404_1200_additional_investment_tracking/01_first_plan.md`
- **修正ファイル**:
  - `apps/investment-tracker/src/settings.py`
  - `apps/investment-tracker/src/profit_calculator.py`
  - `apps/investment-tracker/app.py`
- **データファイル**: `apps/investment-tracker/data/settings.json`

---

## 📚 教訓

### データモデルの拡張
- デフォルト値を設定することで、後方互換性を保つ
- `DEFAULT_SETTINGS`にフィールドを追加し、既存の設定ファイルとマージ

### UIの設計
- **自動計算**と**手動入力**の両方を提供することで、柔軟性を確保
- 投資可能額がマイナスの場合、ユーザーに明確なガイダンスを提供

### セッション状態の管理
- 初期化は条件付きにする：`if "key" not in st.session_state:`
- 更新時はセッション状態とファイルの両方を更新

---

## 完了 ✅

追加投資額トラッキング機能の実装が**完全に完了**しました。
楽天証券・楽天銀行のスイープ機能による追加投資額を正しく管理できるようになりました。
