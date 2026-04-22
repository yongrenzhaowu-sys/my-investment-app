# 資産推移分析機能の実装

**作成日**: 2026-04-19 10:00
**ステータス**: 実装完了

## 概要

投資判断支援アプリに、任意の基準日からの資産額の増減を計算・表示する機能を実装しました。

## やったこと

### 1. 計画ファイル作成
- `docs/plans/20260419_1000_asset_tracking/01_plan.md`
- Phase 1（基本機能）+ Phase 2（推移グラフ）の実装計画を策定

### 2. 資産計算モジュール実装
**ファイル**: `apps/investment-tracker/src/asset_calculator.py`

**実装した関数**:
1. `get_holdings_at_date(target_date, hypotheses, trading_history)`
   - 指定日時点の保有銘柄リストを取得
   - 現在保有中の銘柄と売却済み銘柄を考慮

2. `get_stock_price_at_date(code, target_date)`
   - 指定日の株価を取得（yfinance API）
   - 営業日対応（休日の場合は直近営業日を使用）

3. `calculate_cash_at_date(target_date, hypotheses, trading_history, initial_capital, additional_capital)`
   - 指定日時点の現金残高を計算
   - 購入による支出と売却による入金を考慮

4. `calculate_asset_value_at_date(target_date, hypotheses, trading_history, initial_capital, additional_capital)`
   - 指定日時点の資産額を計算（時価総額 + 現金）
   - 保有銘柄詳細も返す

5. `calculate_asset_change(start_date, hypotheses, trading_history, initial_capital, additional_capital)`
   - 基準日から現在までの資産増減を計算
   - 増減額、増減率を返す

6. `get_asset_history(start_date, end_date, hypotheses, trading_history, initial_capital, additional_capital)`
   - 期間中の日次資産推移を取得
   - グラフ表示用のDataFrameを返す

### 3. UI実装
**ファイル**: `apps/investment-tracker/app.py`

**変更内容**:
1. **import追加**:
   - `from src.asset_calculator import calculate_asset_change, get_asset_history`
   - `import plotly.express as px`
   - モジュール強制リロード設定

2. **サイドバーメニュー追加**:
   - 「💰 資産推移分析」メニューを追加
   - `current_view = "asset_tracking"` に設定

3. **main()関数更新**:
   - 資産推移分析ビューの切り替え処理を追加
   - `render_asset_tracking()` を呼び出し

4. **render_asset_tracking()関数実装**:
   - **基準日選択**: カレンダーUI（デフォルト: 2026-03-13）
   - **資産増減表示**:
     - 基準日資産額（時価総額 + 現金）
     - 現在資産額
     - 増減額・増減率（色分け）
   - **保有銘柄詳細**:
     - 基準日時点の保有銘柄リスト
     - 現在の保有銘柄リスト
   - **資産推移グラフ**:
     - Plotly折れ線グラフ
     - 日次資産推移を表示
     - 詳細データテーブル（展開可能）
   - **使い方ガイド**: エキスパンダーで説明を表示

## 実装の詳細

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
基準日現金 = 初期資金 + 追加投資 - 投資済み額 + 売却済み現金（基準日まで）
基準日資産額 = 基準日時価総額 + 基準日現金

# 現在
現在資産額 = 現在時価総額 + 現在現金

# 増減
増減額 = 現在資産額 - 基準日資産額
増減率 = (現在資産額 / 基準日資産額 - 1) × 100%
```

#### 株価取得（営業日対応）
- yfinance: `ticker.history(start=基準日-7日, end=基準日+1日)`
- 基準日以前の最も近い営業日の終値を使用
- 取得失敗時は0円として扱う（警告表示なし）

### UI設計

#### メトリクス表示
- **3カラムレイアウト**:
  - 基準日資産額（時価総額 + 現金の内訳）
  - 現在資産額（時価総額 + 現金の内訳）
  - 増減額・増減率（色分け: プラス=緑、マイナス=赤）

#### 保有銘柄詳細
- **基準日時点**: 銘柄コード、名前、株価、株数、評価額
- **現在**: 銘柄コード、名前、株価、株数、評価額

#### 資産推移グラフ
- **Plotly折れ線グラフ**:
  - X軸: 日付
  - Y軸: 総資産額（円、カンマ区切り）
  - タイトル: 「資産推移」
- **詳細データテーブル**: エキスパンダーで展開可能

## 決めたこと

### 仕様
1. **基準日デフォルト**: 2026-03-13（ユーザー指定）
2. **株価取得失敗時**: 0円として扱う（エラー表示なし）
3. **グラフ表示**: 日次（週次/月次集計は今回は実装しない）

### 技術選択
1. **株価データソース**: yfinance API
2. **グラフライブラリ**: Plotly Express
3. **キャッシング**: セッション状態に計算結果を保存（`st.session_state.asset_change_data`）

## 次にやること

### テスト
1. **ローカルテスト**:
   ```powershell
   cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
   streamlit run app.py
   ```
   - ブラウザ: http://localhost:8501
   - 「💰 資産推移分析」メニューを選択
   - 基準日を 2026-03-13 に設定して計算

2. **確認項目**:
   - ✅ 基準日選択UIが表示されるか
   - ✅ 計算ボタンが動作するか
   - ✅ 資産増減が正しく計算されるか
   - ✅ 保有銘柄詳細が表示されるか
   - ✅ 資産推移グラフが表示されるか
   - ✅ エラー処理が適切か

### 将来の拡張（オプション）
1. **ベンチマーク比較**:
   - TOPIX、S&P500との比較グラフ
   - アウトパフォーマンス/アンダーパフォーマンス表示

2. **集計期間選択**:
   - 日次/週次/月次の切り替え
   - 長期間の場合は週次/月次で表示

3. **銘柄別寄与度分析**:
   - 各銘柄が資産増減にどれだけ寄与したかを表示
   - 寄与度ランキング

## 重要なパス/コマンド

### ファイル
- **計画**: `docs/plans/20260419_1000_asset_tracking/01_plan.md`
- **モジュール**: `apps/investment-tracker/src/asset_calculator.py`
- **UI**: `apps/investment-tracker/app.py`
- **セッション**: `docs/sessions/20260419_1000_asset_tracking_implementation.md`

### コマンド
```powershell
# アプリ起動
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
streamlit run app.py

# ブラウザ
http://localhost:8501
```

### データファイル
- **保有銘柄**: `apps/investment-tracker/data/hypotheses.json`
- **売買履歴**: `apps/investment-tracker/data/trading_history.json`
- **設定**: `apps/investment-tracker/data/settings.json`

## 注意事項

### パフォーマンス
- 日次推移グラフは期間が長いと時間がかかる（各日の株価をAPIから取得）
- 初回表示時はspinnerでローディング表示

### データ整合性
- 基準日が最初の購入日より前の場合: 資産額 = 初期資金
- 基準日が未来の場合: エラーは出ないが、現在と同じ値になる

### 株価データ
- yfinance APIに依存（無料、レート制限あり）
- 営業日のみデータ存在（休日は直近営業日を使用）
- 取得失敗時は0円として扱う（警告なし）

## 推定工数（実績）

- Phase 1（基本機能）: 1.5時間
- Phase 2（推移グラフ）: 0.5時間
- ドキュメント作成: 0.5時間
- **合計**: 2.5時間（予定3.5時間より短縮）
