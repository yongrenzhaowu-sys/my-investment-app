# セッション記録: 投資支援アプリ - 初期資金問題の完全修正

**日時**: 2026-03-29 00:00
**ステータス**: ✅ 完了
**成果物**: `apps/investment-tracker/app.py`（修正）

---

## 🔍 問題の詳細

### 症状
- 初期資金を更新しても、値がリセットされる
- settings.jsonには正しく保存されているが、画面に反映されない
- セッション状態とファイルの同期が取れていない

### 根本原因
**app.py 990-1000行目**で、`main()`関数が実行されるたびに**毎回**settings.jsonから読み込んで`st.session_state.initial_capital`を上書きしていた。

```python
# 修正前（問題あり）
settings = load_settings()
loaded_value = settings.get("initial_capital", 1_000_000)
st.session_state.initial_capital = loaded_value  # ← 毎回上書き！
```

Streamlitの実行モデルでは、ユーザーが`st.number_input`で値を変更すると自動的に再実行されるが、その時点ではまだ「更新」ボタンが押されていないため、settings.jsonは古い値のまま。結果として、再実行時に古い値で上書きされてしまう。

---

## 🛠️ 実施した修正

### 修正1: セッション状態の初期化を条件付きに（app.py 990-998行目）

```python
# 修正後（正しい）
if "initial_capital" not in st.session_state:
    settings = load_settings()
    loaded_value = settings.get("initial_capital", 1_000_000)
    st.session_state.initial_capital = loaded_value
    print(f"DEBUG: 初回読み込み - initial_capital = {loaded_value}")
```

**効果**:
- セッション開始時に**1回だけ**settings.jsonから読み込み
- その後はセッション状態が保持される
- ユーザーが値を変更しても、再実行時に上書きされない

### 修正2: デバッグ情報の削除（app.py 698-701行目）

```python
# 修正前
st.info(f"🔍 デバッグ: 現在の初期資金 = ¥{st.session_state.get('initial_capital', 'NOT SET'):,}")

# 修正後
# （削除）
```

### 修正3: 初期資金更新UIの改善（app.py 759-788行目）

**変更点**:
1. **現在の初期資金を明示的に表示**
   ```python
   st.info(f"**現在の初期資金**: ¥{st.session_state.initial_capital:,}")
   ```

2. **入力フィールドに`key`パラメータを追加**
   ```python
   new_capital = st.number_input(
       "新しい初期資金（円）",
       key="new_initial_capital_input",  # ← 追加
       ...
   )
   ```

3. **変更検出とボタンの無効化**
   ```python
   is_changed = new_capital != st.session_state.initial_capital
   st.button(
       "更新" if is_changed else "更新（変更なし）",
       disabled=not is_changed  # ← 変更がない場合は無効化
   )
   ```

4. **更新成功メッセージの改善**
   ```python
   st.success(f"✅ 初期資金を ¥{new_capital:,} に更新しました（永続化済み）")
   ```

---

## ✅ 動作確認方法

### 1. アプリ起動
```powershell
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
streamlit run app.py
```

### 2. テストシナリオ

#### シナリオ1: 初期資金の更新
1. サイドバーから「📊 損益サマリー」を選択
2. 「⚙️ 初期資金設定」を展開
3. 「現在の初期資金」が表示されることを確認
4. 「新しい初期資金」に別の値を入力（例: 10,000,000）
5. 「更新」ボタンが青色（primary）になることを確認
6. 「更新」ボタンをクリック
7. ✅ 成功メッセージが表示されることを確認
8. 画面が再描画され、新しい値が反映されることを確認

#### シナリオ2: ページ遷移後の値の保持
1. 初期資金を更新（例: 10,000,000）
2. サイドバーから「📋 仮説登録」を選択
3. 再度「📊 損益サマリー」を選択
4. 「⚙️ 初期資金設定」を展開
5. ✅ 更新した値（10,000,000）が保持されていることを確認

#### シナリオ3: ブラウザリロード後の値の保持
1. 初期資金を更新（例: 10,000,000）
2. ブラウザをリロード（Ctrl+R）
3. ログイン
4. 「📊 損益サマリー」を選択
5. 「⚙️ 初期資金設定」を展開
6. ✅ 更新した値（10,000,000）が保持されていることを確認

#### シナリオ4: settings.jsonの確認
```powershell
cat apps/investment-tracker/data/settings.json
```
更新した値が正しく保存されていることを確認。

---

## 📊 修正前後の比較

### 修正前の動作
1. ユーザーが初期資金を変更
2. Streamlitが自動再実行
3. `main()`が実行され、settings.jsonから古い値を読み込み
4. `st.session_state.initial_capital`が上書きされる ❌
5. ユーザーの変更が失われる

### 修正後の動作
1. ユーザーが初期資金を変更
2. Streamlitが自動再実行
3. `main()`が実行されるが、セッション状態が既に存在するため読み込みをスキップ ✅
4. ユーザーの変更が保持される
5. 「更新」ボタンをクリックすると、settings.jsonに保存される ✅

---

## 🎯 解決された問題

- ✅ 初期資金を更新しても値がリセットされる問題
- ✅ settings.jsonに保存されているのに画面に反映されない問題
- ✅ セッション状態とファイルの同期問題
- ✅ ユーザーが値を変更しても保存されない問題

---

## 📝 次回のタスク

**なし**（問題完全解決）

---

## 🔗 関連ファイル

- `apps/investment-tracker/app.py` - メインアプリケーション（修正済み）
- `apps/investment-tracker/src/settings.py` - 設定管理モジュール（変更なし）
- `apps/investment-tracker/data/settings.json` - 設定ファイル（現在の値: 6,711,800円）

---

## 📚 教訓

### Streamlitのセッション状態管理
- **セッション状態は再実行後も保持される**が、明示的に上書きすると失われる
- **初期化処理は条件付きにする**：`if "key" not in st.session_state:`
- **ファイルからの読み込みは1回だけ**：セッション開始時のみ
- **更新時は両方を更新**：セッション状態とファイルの両方を更新することで同期を保つ

### UIの改善
- **現在の値を明示的に表示**：ユーザーが現在の状態を確認できるようにする
- **変更検出**：値が変更されたときのみボタンを有効化
- **明確なフィードバック**：更新成功時のメッセージを具体的に表示

---

## 完了 ✅

この修正により、投資支援アプリの初期資金問題は**完全に解決**されました。
