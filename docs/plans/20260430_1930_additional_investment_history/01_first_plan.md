# 追加投資履歴の日付管理機能

**作成日**: 2026-04-30 19:30
**目的**: 追加投資額に日付情報を追加し、資産推移分析で正しい時点の資産額を計算できるようにする

## 問題点

### 現在の実装の問題
**asset_calculator.py:118**
```python
# 初期資金 + 追加投資額
cash = initial_capital + additional_capital  # ← 日付チェックなし！
```

**問題**: 追加投資額が日付に関係なく常に加算される

**具体例**:
- 追加投資日: 2026年3月15日（50万円）
- 確認したい日: 2026年3月1日

→ 現状では3月1日の資産額に50万円が含まれる（未来参照バイアス）

**CLAUDE.mdとの関係**:
```
## 🚨 Lookahead bias prevention (CRITICAL)
**必ず問う**: 「この時点で、このデータは本当に利用可能か？」
```

追加投資額は「追加した日付以降」のみ利用可能であるべき。

## 実装計画

### Phase 1: データ構造の変更

#### 1.1 settings.json構造

**変更前**:
```json
{
  "initial_capital": 1000000,
  "additional_capital": 500000
}
```

**変更後**:
```json
{
  "initial_capital": 1000000,
  "additional_investments": [
    {"date": "2026-03-15", "amount": 500000},
    {"date": "2026-04-20", "amount": 300000}
  ]
}
```

#### 1.2 マイグレーション処理

既存の`additional_capital`を`additional_investments`に変換：
```python
# settings.py
def migrate_additional_capital():
    """既存のadditional_capitalをadditional_investmentsに変換"""
    settings = load_settings()

    # 古い形式があれば変換
    if "additional_capital" in settings and "additional_investments" not in settings:
        if settings["additional_capital"] > 0:
            # デフォルト日付は初期資金と同じ日とする
            settings["additional_investments"] = [
                {
                    "date": "2026-01-01",  # デフォルト（運用開始日と仮定）
                    "amount": settings["additional_capital"]
                }
            ]
        else:
            settings["additional_investments"] = []

        # 古いキーを削除
        del settings["additional_capital"]
        save_settings(settings)

    return settings
```

### Phase 2: settings.py の修正

**ファイル**: workspace/apps/investment-tracker/src/settings.py

#### 2.1 新規関数の追加

```python
def get_additional_investments() -> List[Dict]:
    """
    追加投資履歴を取得

    Returns:
        [{"date": "YYYY-MM-DD", "amount": 金額}, ...]
    """
    settings = load_settings()

    # マイグレーション
    if "additional_capital" in settings:
        migrate_additional_capital()
        settings = load_settings()

    return settings.get("additional_investments", [])


def add_additional_investment(date: str, amount: float) -> bool:
    """
    追加投資を記録

    Args:
        date: 追加投資日（YYYY-MM-DD）
        amount: 金額

    Returns:
        成功時True
    """
    settings = load_settings()

    if "additional_investments" not in settings:
        settings["additional_investments"] = []

    settings["additional_investments"].append({
        "date": date,
        "amount": amount
    })

    # 日付順にソート
    settings["additional_investments"] = sorted(
        settings["additional_investments"],
        key=lambda x: x["date"]
    )

    return save_settings(settings)


def remove_additional_investment(index: int) -> bool:
    """
    追加投資を削除

    Args:
        index: 削除するインデックス

    Returns:
        成功時True
    """
    settings = load_settings()

    if "additional_investments" not in settings:
        return False

    if 0 <= index < len(settings["additional_investments"]):
        settings["additional_investments"].pop(index)
        return save_settings(settings)

    return False
```

#### 2.2 既存関数の非推奨化

```python
def get_additional_capital() -> float:
    """
    【非推奨】追加投資額の合計を取得（後方互換性のため残す）

    Returns:
        追加投資額の合計
    """
    investments = get_additional_investments()
    return sum(inv["amount"] for inv in investments)
```

### Phase 3: asset_calculator.py の修正

**ファイル**: workspace/apps/investment-tracker/src/asset_calculator.py

#### 3.1 calculate_cash_at_date() の修正

**変更前**:
```python
def calculate_cash_at_date(
    target_date: str,
    hypotheses: List[Dict],
    trading_history: List[Dict],
    initial_capital: float,
    additional_capital: float = 0
) -> float:
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")

    # 初期資金 + 追加投資額
    cash = initial_capital + additional_capital  # ← 問題！
```

**変更後**:
```python
def calculate_cash_at_date(
    target_date: str,
    hypotheses: List[Dict],
    trading_history: List[Dict],
    initial_capital: float,
    additional_investments: List[Dict] = None
) -> float:
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")

    # 初期資金
    cash = initial_capital

    # target_date以前の追加投資のみを加算
    if additional_investments:
        for investment in additional_investments:
            inv_dt = datetime.strptime(investment["date"], "%Y-%m-%d")
            if inv_dt <= target_dt:
                cash += investment["amount"]
```

#### 3.2 calculate_asset_value_at_date() の修正

引数を `additional_capital` → `additional_investments` に変更

#### 3.3 calculate_asset_change() の修正

引数を `additional_capital` → `additional_investments` に変更

#### 3.4 get_asset_history() の修正

引数を `additional_capital` → `additional_investments` に変更

### Phase 4: profit_calculator.py の確認・修正

**ファイル**: workspace/apps/investment-tracker/src/profit_calculator.py

#### 4.1 calculate_available_capital() の確認

現在の実装を確認し、必要に応じて修正

### Phase 5: app.py の修正

**ファイル**: workspace/apps/investment-tracker/app.py

#### 5.1 セッション状態の変更

**変更箇所**: main() 関数（行1600付近）

```python
# 変更前
if "additional_capital" not in st.session_state:
    loaded_value = get_additional_capital()
    st.session_state.additional_capital = loaded_value

# 変更後
if "additional_investments" not in st.session_state:
    loaded_value = get_additional_investments()
    st.session_state.additional_investments = loaded_value
```

#### 5.2 損益サマリーのUI修正

**変更箇所**: render_profit_summary() 関数（行815-886付近）

**変更前**:
```python
with st.expander("💰 追加投資額設定"):
    st.info(f"**現在の追加投資額**: ¥{st.session_state.additional_capital:,}")

    new_additional = st.number_input(
        "追加投資額（円）",
        value=int(st.session_state.additional_capital),
        ...
    )
```

**変更後**:
```python
with st.expander("💰 追加投資履歴"):
    investments = st.session_state.additional_investments

    # 合計表示
    total = sum(inv["amount"] for inv in investments)
    st.info(f"**追加投資額の合計**: ¥{total:,}")

    # 履歴一覧
    if investments:
        st.subheader("📋 履歴")
        for i, inv in enumerate(investments):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"日付: {inv['date']}")
            with col2:
                st.write(f"金額: ¥{inv['amount']:,}")
            with col3:
                if st.button("🗑️", key=f"delete_inv_{i}"):
                    remove_additional_investment(i)
                    st.session_state.additional_investments = get_additional_investments()
                    st.rerun()

    st.divider()

    # 新規追加フォーム
    st.subheader("➕ 追加投資を記録")
    with st.form("add_investment_form"):
        inv_date = st.date_input("追加投資日", value=datetime.now())
        inv_amount = st.number_input("金額（円）", min_value=0, step=100_000)

        submitted = st.form_submit_button("追加")
        if submitted:
            if inv_amount > 0:
                add_additional_investment(
                    inv_date.strftime("%Y-%m-%d"),
                    inv_amount
                )
                st.session_state.additional_investments = get_additional_investments()
                st.success(f"✅ ¥{inv_amount:,} を記録しました")
                st.rerun()
```

#### 5.3 自動計算ボタンの削除

追加投資履歴は明示的に記録するため、自動計算ボタンは削除

#### 5.4 関数呼び出しの修正

**変更箇所**: calculate_available_capital(), calculate_asset_change(), get_asset_history() の呼び出し

```python
# 変更前
available = calculate_available_capital(
    hypotheses,
    st.session_state.initial_capital,
    st.session_state.additional_capital
)

# 変更後
available = calculate_available_capital(
    hypotheses,
    st.session_state.initial_capital,
    st.session_state.additional_investments
)
```

#### 5.5 資産推移分析の修正

**変更箇所**: render_asset_tracking() 関数（行1384-1577付近）

```python
# 変更前
additional_capital = st.session_state.get("additional_capital", 0)

change = calculate_asset_change(
    start_date=start_date.strftime("%Y-%m-%d"),
    hypotheses=hypotheses,
    trading_history=trading_history,
    initial_capital=initial_capital,
    additional_capital=additional_capital,
    end_date=end_date.strftime("%Y-%m-%d")
)

# 変更後
additional_investments = st.session_state.get("additional_investments", [])

change = calculate_asset_change(
    start_date=start_date.strftime("%Y-%m-%d"),
    hypotheses=hypotheses,
    trading_history=trading_history,
    initial_capital=initial_capital,
    additional_investments=additional_investments,
    end_date=end_date.strftime("%Y-%m-%d")
)
```

### Phase 6: 後方互換性の確保

#### 6.1 マイグレーション処理の自動実行

app.py の main() 関数で、初回読み込み時にマイグレーションを実行

```python
# 3. 初期資金の設定（未設定の場合のみ読み込み）
if "initial_capital" not in st.session_state:
    loaded_value = get_initial_capital()
    st.session_state.initial_capital = loaded_value

# 4. 追加投資履歴の設定（マイグレーション含む）
if "additional_investments" not in st.session_state:
    # マイグレーション自動実行
    loaded_value = get_additional_investments()  # 内部でマイグレーション
    st.session_state.additional_investments = loaded_value
```

#### 6.2 既存ユーザーへの影響

- 既存の `additional_capital` は自動的に `additional_investments` に変換
- デフォルト日付: 2026-01-01（運用開始日と仮定）
- ユーザーは後から正しい日付に修正可能

## 実装順序

1. ✅ **settings.py 修正**
   - get_additional_investments()
   - add_additional_investment()
   - remove_additional_investment()
   - migrate_additional_capital()

2. ✅ **asset_calculator.py 修正**
   - calculate_cash_at_date()
   - calculate_asset_value_at_date()
   - calculate_asset_change()
   - get_asset_history()

3. ✅ **profit_calculator.py 確認・修正**
   - calculate_available_capital()

4. ✅ **app.py 修正**
   - セッション状態の変更
   - 損益サマリーのUI修正
   - 関数呼び出しの修正
   - 資産推移分析の修正

## テスト項目

### マイグレーション
- [ ] 既存のadditional_capitalが正しく変換される
- [ ] additional_capital=0の場合、空配列になる
- [ ] 変換後、古いキーが削除される

### 追加投資履歴の管理
- [ ] 追加投資を記録できる
- [ ] 日付順にソートされる
- [ ] 削除できる
- [ ] 合計金額が正しく表示される

### 資産額計算の正確性
- [ ] 追加投資日以前の日付では、その追加投資が反映されない
- [ ] 追加投資日以降の日付では、その追加投資が反映される
- [ ] 複数の追加投資がある場合、正しく合計される

### 具体例
**設定**:
- 初期資金: 100万円
- 追加投資1: 2026-03-15に50万円
- 追加投資2: 2026-04-20に30万円

**確認**:
- 2026-03-01の現金: 100万円（初期資金のみ）
- 2026-03-15の現金: 150万円（初期資金 + 追加投資1）
- 2026-04-01の現金: 150万円（初期資金 + 追加投資1）
- 2026-04-20の現金: 180万円（初期資金 + 追加投資1 + 追加投資2）

## リスク

### 中リスク
- 既存ユーザーのデータ移行が必要
- マイグレーション処理のバグがあると、データが失われる可能性

### 対策
- マイグレーション前に settings.json をバックアップ
- マイグレーション処理を慎重に実装
- 既存の `additional_capital` キーは削除せず、残す（オプション）

## 完了条件

- [x] settings.py修正完了
- [x] asset_calculator.py修正完了
- [x] profit_calculator.py確認・修正完了
- [x] app.py修正完了
- [x] マイグレーション処理のテスト完了
- [x] 資産額計算の精度テスト完了
- [x] docs/sessions/にセッションサマリー保存
- [x] GitHubにプッシュ
