# ナレッジベース: Streamlitセッション状態管理のベストプラクティス

**作成日**: 2026-03-29
**カテゴリ**: Streamlit, セッション管理, 永続化
**重要度**: ⭐⭐⭐ CRITICAL

---

## 🎯 概要

Streamlitアプリで**セッション状態とファイル（永続化）の同期**を正しく管理する方法。特に、ユーザーが設定を変更した際に値がリセットされる問題を防ぐためのベストプラクティス。

---

## ❌ アンチパターン：毎回上書きする

### 問題のあるコード

```python
def main():
    # ❌ 間違い：main()が実行されるたびに毎回上書き
    settings = load_settings()
    st.session_state.some_value = settings.get("some_value", default)

    # UIでユーザーが値を変更
    new_value = st.number_input("値", value=st.session_state.some_value)
```

### なぜ問題か？

1. **Streamlitの再実行モデル**：ユーザーがウィジェットを操作すると、スクリプト全体が再実行される
2. **上書きのタイミング**：`st.number_input`で値を変更 → 再実行 → `main()`が実行 → ファイルから古い値を読み込んで上書き ❌
3. **結果**：ユーザーの変更が失われる

### 具体例

```python
# 初期状態：settings.json = {"value": 100}
# ユーザーが200に変更
new_value = st.number_input("値", value=100)  # ユーザーが200に変更
# → Streamlitが再実行
# → main()が実行
st.session_state.some_value = 100  # ← ファイルから読み込んで上書き！
# → st.number_inputのvalue=100に戻る ❌
```

---

## ✅ ベストプラクティス1：条件付き初期化

### 正しいコード

```python
def main():
    # ✅ 正しい：未設定の場合のみファイルから読み込み
    if "some_value" not in st.session_state:
        settings = load_settings()
        st.session_state.some_value = settings.get("some_value", default)
        print(f"DEBUG: 初回読み込み - some_value = {st.session_state.some_value}")

    # UIでユーザーが値を変更（セッション状態が保持される）
    new_value = st.number_input("値", value=st.session_state.some_value)

    # 更新ボタン
    if st.button("更新"):
        st.session_state.some_value = new_value
        save_settings({"some_value": new_value})
        st.rerun()
```

### なぜ正しいか？

1. **初回のみ読み込み**：セッション開始時に1回だけファイルから読み込む
2. **セッション状態を保持**：再実行時も`st.session_state.some_value`が保持される
3. **更新時に両方を更新**：セッション状態とファイルの両方を更新することで同期を保つ

---

## ✅ ベストプラクティス2：明示的な更新フロー

### UIの改善

```python
with st.expander("⚙️ 設定"):
    # 1. 現在の値を明示的に表示
    st.info(f"**現在の値**: {st.session_state.some_value}")

    # 2. 入力フィールドにkeyを設定
    new_value = st.number_input(
        "新しい値",
        value=st.session_state.some_value,
        key="new_value_input",  # ← keyを設定
        help="変更後は「更新」ボタンを押してください"
    )

    # 3. 変更検出
    is_changed = new_value != st.session_state.some_value

    # 4. 変更がある場合のみボタンを有効化
    if st.button(
        "更新" if is_changed else "更新（変更なし）",
        disabled=not is_changed,
        type="primary" if is_changed else "secondary"
    ):
        # 5. 両方を更新
        st.session_state.some_value = new_value
        save_settings({"some_value": new_value})
        st.success(f"✅ 値を {new_value} に更新しました")
        st.rerun()
```

### ポイント

- ✅ **現在の値を表示**：ユーザーが現在の状態を確認できる
- ✅ **keyパラメータ**：Streamlitがウィジェットの状態を自動管理
- ✅ **変更検出**：変更がない場合はボタンを無効化
- ✅ **明確なフィードバック**：更新成功時のメッセージを表示

---

## ✅ ベストプラクティス3：ファイルとセッションの役割分担

### 設計原則

| データ | 保存場所 | 読み込みタイミング | 更新タイミング |
|--------|----------|-------------------|----------------|
| **永続的な設定** | ファイル（settings.json） | セッション開始時（1回） | ユーザーが明示的に更新 |
| **一時的な状態** | セッション状態のみ | 不要（初期化時に設定） | 再実行のたびに更新可能 |
| **ユーザー入力** | セッション状態 → ファイル | セッション状態から読み込み | ボタンクリック時にファイルに保存 |

### 実装例

```python
# セッション開始時（1回のみ）
if "settings" not in st.session_state:
    st.session_state.settings = load_settings()
    print("DEBUG: 設定を読み込みました")

# 設定値の取得（高速、ファイルI/O不要）
initial_capital = st.session_state.settings.get("initial_capital", 1_000_000)

# 設定の更新（明示的）
if st.button("設定を保存"):
    save_settings(st.session_state.settings)
    st.success("✅ 設定を保存しました")
```

---

## 🚨 よくある落とし穴

### 落とし穴1: st.number_inputのvalueと実際の値の混同

```python
# ❌ 間違い
value = st.number_input("値", value=100)
# → ユーザーが200に変更しても、valueは200を返すが、
#    次の再実行時にvalue=100で初期化されるため、リセットされる

# ✅ 正しい
if "value" not in st.session_state:
    st.session_state.value = 100

value = st.number_input("値", value=st.session_state.value)
# → セッション状態が保持されるため、200が保たれる
```

### 落とし穴2: st.rerun()後の初期化

```python
# ❌ 間違い
if st.button("更新"):
    save_settings({"value": new_value})
    st.rerun()
    # ← ここで再実行されるが、main()の先頭で上書きされる可能性

# ✅ 正しい
if st.button("更新"):
    st.session_state.value = new_value  # ← 先にセッション状態を更新
    save_settings({"value": new_value})
    st.rerun()
```

### 落とし穴3: 複数のセッションでの競合

**問題**：複数のブラウザタブやユーザーが同時にアクセスした場合、ファイルの競合が発生する可能性がある。

**解決策**：
1. **セッション状態を優先**：各セッションは独自のセッション状態を持つ
2. **ファイルは永続化のみ**：ファイルは「保存」ボタン押下時のみ更新
3. **競合時の挙動**：最後に保存したセッションの値が勝つ（通常これで問題ない）

---

## 📊 パフォーマンス比較

| 方法 | ファイルI/O回数 | セッション状態への影響 | 推奨度 |
|------|----------------|----------------------|--------|
| 毎回読み込み | 再実行のたびに1回 | 上書きされる ❌ | ❌ 非推奨 |
| 条件付き読み込み | セッション開始時に1回 | 保持される ✅ | ✅ 推奨 |
| セッション状態のみ | 保存時のみ | 保持される ✅ | ✅ 推奨 |

---

## 🔗 関連リソース

- [Streamlit公式: Session State](https://docs.streamlit.io/library/api-reference/session-state)
- [投資支援アプリの実装例](../../apps/investment-tracker/app.py)
- [セッション記録: 初期資金問題の修正](../sessions/20260329_0000_investment_tracker_capital_fix.md)

---

## ✅ チェックリスト：セッション状態管理

実装時に以下を確認：

- [ ] セッション状態の初期化は条件付き（`if "key" not in st.session_state:`）
- [ ] ファイルからの読み込みは1回のみ（セッション開始時）
- [ ] ユーザーが値を変更してもリセットされない
- [ ] 更新時は、セッション状態とファイルの両方を更新
- [ ] UIで現在の値を明示的に表示
- [ ] 変更検出を実装（変更がない場合はボタンを無効化）
- [ ] 更新成功時に明確なフィードバックを表示

---

## 完了 ✅

このナレッジは、Streamlitアプリでセッション状態とファイルを正しく同期するための完全ガイドです。
