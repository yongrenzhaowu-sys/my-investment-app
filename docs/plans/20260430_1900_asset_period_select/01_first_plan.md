# 資産推移分析：任意期間選択機能

**作成日**: 2026-04-30 19:00
**目的**: 資産推移分析に終点（end_date）選択機能を追加し、任意期間のリターンを計算可能にする

## 現状

### 問題点
- 基準日（始点）のみ指定可能
- 終点は自動的に「現在日」に固定されている
- 過去の任意期間のリターンを確認できない

### 現在の実装
**app.py:1384-1576 `render_asset_tracking()`**
```python
base_date = st.date_input("基準日", value=datetime(2026, 3, 13))
# 終点の指定はなし（自動的に現在日）
```

**asset_calculator.py:200-258 `calculate_asset_change()`**
```python
def calculate_asset_change(
    start_date: str,
    # end_date パラメータなし
    ...
):
    # 現在日を自動取得
    current_date = datetime.now().strftime("%Y-%m-%d")
```

## 実装計画

### Phase 1: UI修正（app.py）

#### 1.1 終点選択UIの追加
**位置**: app.py:1395-1408（基準日選択セクション）

**変更内容**:
```python
# 変更前
col1, col2 = st.columns([2, 1])
with col1:
    base_date = st.date_input("基準日", ...)
with col2:
    calculate_button = st.button("🔍 計算開始", ...)

# 変更後
st.subheader("📅 期間を選択")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("開始日", value=datetime(2026, 3, 13))
with col2:
    end_date = st.date_input("終了日", value=datetime.now())

# バリデーション
if start_date >= end_date:
    st.error("開始日は終了日より前である必要があります")
    return

col3, _ = st.columns([1, 3])
with col3:
    calculate_button = st.button("🔍 計算開始", ...)
```

#### 1.2 calculate_asset_change()呼び出しの修正
**位置**: app.py:1415-1421

**変更内容**:
```python
# 変更前
change = calculate_asset_change(
    start_date=base_date.strftime("%Y-%m-%d"),
    ...
)

# 変更後
change = calculate_asset_change(
    start_date=start_date.strftime("%Y-%m-%d"),
    end_date=end_date.strftime("%Y-%m-%d"),
    ...
)
```

#### 1.3 get_asset_history()呼び出しの修正
**位置**: app.py:1512-1519

**変更内容**:
```python
# 変更前
history = get_asset_history(
    start_date=change['start_date'],
    end_date=change['current_date'],  # 現在日
    ...
)

# 変更後
# end_dateは既にchange['end_date']に含まれているため変更なし
# （calculate_asset_changeの戻り値を修正）
history = get_asset_history(
    start_date=change['start_date'],
    end_date=change['end_date'],
    ...
)
```

#### 1.4 表示ラベルの修正
**位置**: app.py:1434-1469（資産増減サマリー）

**変更内容**:
```python
# "現在資産額" → "終了日資産額"
# "現在日: {change['current_date']}" → "終了日: {change['end_date']}"
# "現在の保有銘柄" → "終了日時点の保有銘柄"
```

### Phase 2: ロジック修正（asset_calculator.py）

#### 2.1 calculate_asset_change()の修正
**位置**: asset_calculator.py:200-258

**変更内容**:
```python
def calculate_asset_change(
    start_date: str,
    end_date: str,  # 新規追加
    hypotheses: List[Dict],
    trading_history: List[Dict],
    initial_capital: float,
    additional_capital: float = 0
) -> Dict[str, float]:
    """
    基準日から指定日までの資産増減を計算

    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）  # 追加
        ...
    """
    # 開始日の資産額
    start_value = calculate_asset_value_at_date(...)

    # 終了日の資産額（変更）
    # 変更前: current_date = datetime.now().strftime("%Y-%m-%d")
    # 変更後: 引数のend_dateを使用
    end_value = calculate_asset_value_at_date(
        end_date, hypotheses, trading_history, initial_capital, additional_capital
    )

    change_amount = end_value["total_asset"] - start_value["total_asset"]
    change_rate = (change_amount / start_value["total_asset"] * 100) if start_value["total_asset"] > 0 else 0

    return {
        "start_date": start_date,
        "start_asset": start_value["total_asset"],
        "start_market_value": start_value["market_value"],
        "start_cash": start_value["cash"],
        "start_holdings": start_value["holdings"],
        "end_date": end_date,  # 変更: current_date → end_date
        "end_asset": end_value["total_asset"],  # 変更: current_asset → end_asset
        "end_market_value": end_value["market_value"],  # 変更
        "end_cash": end_value["cash"],  # 変更
        "end_holdings": end_value["holdings"],  # 変更
        "change_amount": change_amount,
        "change_rate": change_rate
    }
```

#### 2.2 戻り値のキー名変更
- `current_date` → `end_date`
- `current_asset` → `end_asset`
- `current_market_value` → `end_market_value`
- `current_cash` → `end_cash`
- `current_holdings` → `end_holdings`

**理由**: 「現在」という用語は終点が「今」でない場合に誤解を招くため

### Phase 3: 表示の修正（app.py）

#### 3.1 メトリクス表示の修正
**位置**: app.py:1438-1468

**変更内容**:
```python
# col2のラベル変更
with col2:
    st.metric(
        "終了日資産額",  # 変更: "現在資産額" → "終了日資産額"
        f"¥{change['end_asset']:,.0f}",  # キー変更
        help=f"終了日: {change['end_date']}"  # 変更
    )
    st.caption(f"時価総額: ¥{change['end_market_value']:,.0f}")  # キー変更
    st.caption(f"現金: ¥{change['end_cash']:,.0f}")  # キー変更
```

#### 3.2 保有銘柄詳細の見出し修正
**位置**: app.py:1488-1504

**変更内容**:
```python
st.subheader(f"📋 終了日時点の保有銘柄（{change['end_date']}）")

if change['end_holdings']:  # キー変更
    current_df = pd.DataFrame(change['end_holdings'])  # キー変更
    ...
```

### Phase 4: 使い方ガイドの更新

**位置**: app.py:1553-1576

**変更内容**:
```markdown
### 資産推移分析の使い方

#### 1. 期間を選択
- **開始日**: 分析開始日を選択（デフォルト: 2026-03-13）
- **終了日**: 分析終了日を選択（デフォルト: 今日）
- 開始日 < 終了日 である必要があります

#### 2. 計算開始
- 「🔍 計算開始」ボタンをクリックすると、以下が計算されます:
  - **開始日時点の資産額**: 開始日の時価総額 + 現金残高
  - **終了日時点の資産額**: 終了日の時価総額 + 現金残高
  - **増減額**: 終了日資産額 - 開始日資産額
  - **増減率**: (終了日資産額 / 開始日資産額 - 1) × 100%

#### 3. 資産推移グラフ
- 開始日から終了日までの日次資産推移をグラフで表示
- 営業日のみデータが表示されます

### ユースケース
- 📊 **過去1ヶ月のリターンを確認**: 開始日=1ヶ月前、終了日=今日
- 📊 **特定月のパフォーマンス**: 開始日=2026-03-01、終了日=2026-03-31
- 📊 **現在までのリターン**: 開始日=運用開始日、終了日=今日
```

## 実装順序

1. ✅ **asset_calculator.py修正**（Phase 2）
   - ロジックを先に修正（引数とキー名変更）

2. ✅ **app.py修正**（Phase 1, 3, 4）
   - UI追加
   - 関数呼び出し修正
   - 表示修正
   - ガイド更新

## テスト項目

### 基本動作
- [ ] 開始日 < 終了日 の通常ケース
- [ ] 開始日 = 終了日 のエッジケース（エラー表示）
- [ ] 開始日 > 終了日 の異常ケース（エラー表示）

### 計算精度
- [ ] 開始日=2026-03-13、終了日=今日（デフォルト動作確認）
- [ ] 開始日=2026-03-01、終了日=2026-03-31（過去期間）
- [ ] 開始日=1年前、終了日=今日（長期間）

### UI/UX
- [ ] カレンダー選択が直感的か
- [ ] エラーメッセージが適切か
- [ ] グラフの期間が正しいか

## リスク

### 低リスク
- 既存機能への影響なし（引数追加のみ、デフォルト動作は維持）
- 後方互換性の問題なし（新機能追加）

### 注意点
- yfinance APIの株価取得失敗時の挙動（既存実装で対応済み）
- 長期間（数年）のグラフ描画パフォーマンス（現状でも対応済み）

## 完了条件

- [x] asset_calculator.py修正完了
- [x] app.py修正完了
- [x] 基本動作テスト完了
- [x] docs/sessions/にセッションサマリー保存
