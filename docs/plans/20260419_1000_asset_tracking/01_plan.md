# 任意の日付からの資産増減計算機能

**作成日**: 2026-04-19 10:00
**ステータス**: 実装中

## 目的

投資判断支援アプリに、任意の基準日からの資産額の増減を計算・表示する機能を追加する。

## 要件

### Phase 1: 基本機能
1. **基準日選択UI**
   - カレンダーで任意の日付を選択
   - デフォルト: 2026-03-13

2. **資産額計算**
   - 基準日時点の資産額（時価総額 + 現金残高）
   - 現在の資産額
   - 増減額・増減率

3. **表示**
   - 基準日資産額
   - 現在資産額
   - 増減額（色分け: プラス=緑、マイナス=赤）
   - 増減率

### Phase 2: 推移グラフ
- 基準日～現在の日次資産額推移
- Plotly折れ線グラフで表示

## 技術仕様

### データソース
- **保有銘柄**: `data/hypotheses.json`
- **売買履歴**: `data/trading_history.json`
- **初期資金**: `data/settings.json`
- **株価データ**: yfinance API

### 計算ロジック

#### 基準日時点の保有銘柄特定
```python
# 現在保有中の銘柄で、基準日以前に購入したもの
if purchase_date <= 基準日:
    → 基準日時点でも保有

# 売却済み銘柄で、基準日時点では保有していたもの
if purchase_date <= 基準日 < sell_date:
    → 基準日時点では保有
```

#### 資産額計算
```python
# 基準日
基準日時価総額 = Σ(基準日株価 × 株数)  # 基準日時点の全保有銘柄
基準日現金 = 初期資金 - 投資済み額 + 売却済み現金（基準日まで）
基準日資産額 = 基準日時価総額 + 基準日現金

# 現在
現在資産額 = 現在時価総額 + 現在現金（既存ロジック流用）

# 増減
増減額 = 現在資産額 - 基準日資産額
増減率 = (現在資産額 / 基準日資産額 - 1) × 100%
```

#### 株価取得（営業日対応）
- yfinance: `ticker.history(start=基準日-7日, end=基準日+1日)`
- 基準日以前の最も近い営業日の終値を使用
- 取得失敗時は0円として扱う

### 新規モジュール: `src/asset_calculator.py`

#### 関数一覧
1. `get_holdings_at_date(target_date, hypotheses, trading_history)`
   - 指定日時点の保有銘柄リストを取得

2. `get_stock_price_at_date(code, target_date)`
   - 指定日の株価を取得（営業日対応）

3. `calculate_cash_at_date(target_date, hypotheses, trading_history, initial_capital, additional_capital)`
   - 指定日時点の現金残高を計算

4. `calculate_asset_value_at_date(target_date, hypotheses, trading_history, initial_capital, additional_capital)`
   - 指定日時点の資産額を計算（時価総額 + 現金）

5. `calculate_asset_change(start_date, hypotheses, trading_history, initial_capital, additional_capital)`
   - 基準日から現在までの資産増減を計算

6. `get_asset_history(start_date, end_date, hypotheses, trading_history, initial_capital, additional_capital)`
   - 期間中の日次資産推移を取得（グラフ用）

### UI追加: `app.py`

#### サイドバーメニュー
```python
menu = st.sidebar.radio(
    "選択してください",
    ["📋 仮説登録", "📊 損益サマリー", "📜 売買履歴", "📈 バリュエーション分析", "💰 資産推移分析"],  # ← 追加
    label_visibility="collapsed"
)
```

#### 資産推移分析画面
```python
def render_asset_tracking():
    st.title("💰 資産推移分析")

    # 基準日選択
    base_date = st.date_input("基準日を選択", value=datetime(2026, 3, 13))

    # 資産増減計算
    change = calculate_asset_change(
        start_date=base_date.strftime("%Y-%m-%d"),
        hypotheses=hypotheses,
        trading_history=trading_history,
        initial_capital=initial_capital
    )

    # 表示
    col1, col2 = st.columns(2)
    with col1:
        st.metric("基準日資産額", f"¥{change['start_asset']:,.0f}")
    with col2:
        st.metric("現在資産額", f"¥{change['current_asset']:,.0f}")

    st.metric(
        "増減",
        f"¥{change['change_amount']:,.0f}",
        delta=f"{change['change_rate']:.2f}%"
    )

    # 推移グラフ
    history = get_asset_history(
        start_date=base_date.strftime("%Y-%m-%d"),
        end_date=datetime.now().strftime("%Y-%m-%d"),
        hypotheses=hypotheses,
        trading_history=trading_history,
        initial_capital=initial_capital
    )

    fig = px.line(
        history,
        x="date",
        y="total_asset",
        title="資産推移",
        labels={"date": "日付", "total_asset": "総資産額（円）"}
    )
    st.plotly_chart(fig, use_container_width=True)
```

## 実装順序

1. ✅ 計画ファイル作成
2. ⏳ `src/asset_calculator.py` 実装
3. ⏳ `app.py` UI追加
4. ⏳ ローカルテスト
5. ⏳ セッション記録作成

## 注意事項

### 株価データ取得
- **営業日のみデータ存在**: 休日の場合は直近営業日を使用
- **取得失敗時の対応**: 0円として扱い、エラー表示（警告）

### パフォーマンス
- 日次推移グラフは期間が長いと時間がかかる
- 初回表示時にspinnerでローディング表示

### データ整合性
- 基準日が最初の購入日より前の場合: 資産額 = 初期資金
- 基準日が未来の場合: エラー表示

## 推定工数

- Phase 1（基本機能）: 2時間
- Phase 2（推移グラフ）: 1時間
- テスト: 30分
- **合計**: 3.5時間
