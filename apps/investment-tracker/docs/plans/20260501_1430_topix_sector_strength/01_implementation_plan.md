# TOPIX対比 東証33業種指数 強弱判定機能 実装計画

**作成日**: 2026-05-01 14:30
**目的**: 東証33業種指数をTOPIX対比で強弱判定する機能を実装

## 📋 要件

### 業種分類
- **東証33業種指数** (指数コード: 0040〜0060)
- TOPIX-17業種指数から切り替え

### 判定基準（3つ）
1. **期間リターン** (既存実装を流用)
   - 選択期間のリターンでTOPIX対比を計算
2. **移動平均乖離** (新規)
   - 25日MA・75日MAとの乖離率を計算
   - TOPIXとの差分で強弱判定
3. **相対力指数（RSI）** (新規)
   - 14日RSIを計算
   - TOPIXとの差分で強弱判定

### 統合判定
- 3つの判定基準の合計スコアで「強い」「普通」「弱い」を判定

## 🛠️ 実装タスク

### Phase 1: データ定義とAPI修正
1. ✅ 東証33業種指数のマスターデータ作成
   - ファイル: `src/sector_33_data.py`
   - 内容: 指数コード (0040〜0060) と業種名のマッピング

2. ✅ API取得部分の修正
   - ファイル: `src/api.py`
   - メソッド: `get_sector_33_indices(start_date, end_date)`
   - エンドポイント: `GET /v2/indices/bars/daily`
   - パラメータ: `code=0040〜0060`

### Phase 2: 分析ロジック実装
3. ✅ 期間リターン計算（既存流用）
   - ファイル: `src/sector_strength.py` (新規)
   - 関数: `calculate_period_return(df, sector_code)`

4. ✅ 移動平均乖離計算
   - ファイル: `src/sector_strength.py`
   - 関数: `calculate_ma_divergence(df, sector_code, ma_periods=[25, 75])`

5. ✅ RSI計算
   - ファイル: `src/sector_strength.py`
   - 関数: `calculate_rsi(df, sector_code, period=14)`

6. ✅ 統合強弱判定
   - ファイル: `src/sector_strength.py`
   - 関数: `judge_sector_strength(sector_code, period_return, ma_div, rsi, topix_return, topix_ma_div, topix_rsi)`
   - スコアリング:
     - 期間リターン: TOPIX対比 > 0% → +1、< 0% → -1
     - MA乖離: TOPIX対比 > 0% → +1、< 0% → -1
     - RSI: TOPIX対比 > 0 → +1、< 0 → -1
   - 判定: 合計スコア >= 2 → 強い、<= -2 → 弱い、その他 → 普通

### Phase 3: UI実装
7. ✅ セクター強弱一覧画面
   - ファイル: `app.py`
   - 関数: `render_sector_strength()` (新規)
   - 内容:
     - 期間選択（1ヶ月、3ヶ月、6ヶ月、1年、カスタム）
     - 33業種の強弱判定結果を表示
     - フィルタリング（強いのみ、弱いのみ）
     - ソート（スコア順、期間リターン順、MA乖離順、RSI順）

8. ✅ 詳細表示
   - 各業種の詳細指標を展開表示
   - TOPIXとの比較グラフ

## 📂 ファイル構成

```
workspace/apps/investment-tracker/
├── src/
│   ├── sector_33_data.py       # 新規: 東証33業種マスター
│   ├── sector_strength.py      # 新規: 強弱判定ロジック
│   └── api.py                  # 修正: 33業種指数取得API追加
├── app.py                      # 修正: UI追加
└── docs/
    ├── plans/20260501_1430_topix_sector_strength/
    │   └── 01_implementation_plan.md  # 本ファイル
    └── sessions/
        └── (作業完了後にサマリーを保存)
```

## 🔍 J-Quants API仕様（重要）

### 指数コードの正しい使い方

#### ❌ 誤り: 33業種コード (0050, 1050, ...) を使用
- これは**銘柄の業種分類コード**であり、指数時系列の取得には使えない

#### ✅ 正しい: 東証業種別指数コード (0040〜0060)
- TOPIX = 0000
- 水産・農林業 = 0040
- 鉱業 = 0041
- 建設業 = 0042
- ...
- サービス業 = 0060

### APIエンドポイント

#### TOPIX本体
```
GET /v2/indices/bars/daily/topix
```

#### 東証33業種指数
```
GET /v2/indices/bars/daily?code={index_code}&from={start_date}&to={end_date}
```

パラメータ:
- `code`: 指数コード (0040〜0060)
- `from`: 開始日 (YYYY-MM-DD)
- `to`: 終了日 (YYYY-MM-DD)

## 📝 注意事項

### ルックアヘッドバイアス防止
- 使用するデータはすべて `end_date` 以前のもの
- 将来データの参照は禁止

### プラン制約
- J-Quants Standard プランで実装
- 指数四本値API (`/indices`) は Standard 以上で利用可能

## 🎯 成功基準

1. ✅ 東証33業種指数の全データが取得できる
2. ✅ 3つの判定基準（期間リターン、MA乖離、RSI）が正しく計算される
3. ✅ TOPIX対比で相対的な強弱が判定される
4. ✅ UI上で見やすく表示される
5. ✅ エラーハンドリングが適切に行われる

## 📅 次のステップ

1. Phase 1 から順に実装
2. 各フェーズ完了後にテスト
3. 全体完了後に `docs/sessions/` にサマリーを保存
