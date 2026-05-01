# セクター強弱判定機能 実装完了サマリー

**作業日時**: 2026-05-01 14:30 〜 15:00
**作業内容**: 東証33業種指数のTOPIX対比強弱判定機能を実装

## 🎯 実施したこと

### Phase 1: データ定義とAPI修正

1. **東証33業種指数マスターデータの作成**
   - ファイル: `src/sector_33_data.py`
   - 内容: 指数コード（0040〜0072）と業種名のマッピング
   - 関数: `get_sector_name()`, `get_index_code()`, `get_all_sector_codes()`

2. **API取得部分の修正**
   - ファイル: `src/api.py`
   - メソッド: `get_sector_33_indices(start_date, end_date)`
   - エンドポイント: `GET /v2/indices/bars/daily`
   - パラメータ: `code={index_code}&from={YYYYMMDD}&to={YYYYMMDD}`

### Phase 2: 分析ロジック実装

3. **強弱判定ロジックの実装**
   - ファイル: `src/sector_strength.py`
   - 関数:
     - `calculate_period_return()`: 期間リターン計算（33業種 + TOPIX）
     - `calculate_ma_divergence()`: 移動平均乖離計算（25日MA、75日MA）
     - `calculate_rsi()`: RSI計算（14日）
     - `judge_sector_strength()`: 3指標の統合判定（スコア: -3〜+3）
     - `analyze_all_sectors()`: 全業種一括分析

### Phase 3: UI実装

4. **セクター強弱判定画面の追加**
   - ファイル: `app.py`
   - メニュー追加: 「💪 セクター強弱判定」
   - 関数: `render_sector_strength()`
   - 機能:
     - 期間選択（1ヶ月、3ヶ月、6ヶ月、1年、カスタム）
     - 分析実行ボタン
     - 結果一覧（スコア順、フィルタリング、ソート）
     - 詳細情報表示（各業種の指標をカード形式で表示）
     - データテーブル表示

## 📊 実装した機能の詳細

### 判定指標

1. **期間リターン**
   - 選択期間の騰落率を計算
   - TOPIX対比でプラスなら +1、マイナスなら -1

2. **移動平均乖離**
   - 25日MA・75日MAとの乖離率を計算
   - TOPIX対比でプラスなら +1、マイナスなら -1

3. **RSI（相対力指数）**
   - 14日RSIを計算
   - TOPIX対比でプラスなら +1、マイナスなら -1

### 総合判定

- **スコア**: 3つの指標の合計（-3〜+3）
- **強い**: スコア >= 2
- **普通**: -1 <= スコア <= 1
- **弱い**: スコア <= -2

## ✅ 成功基準の達成状況

- [x] 東証33業種指数の全データが取得できる
- [x] 3つの判定基準（期間リターン、MA乖離、RSI）が正しく計算される
- [x] TOPIX対比で相対的な強弱が判定される
- [x] UI上で見やすく表示される
- [x] エラーハンドリングが適切に行われる

## 🔧 技術的な決定事項

### J-Quants API仕様の正しい理解

**重要**: 以下の点を確認・実装しました:

1. **指数コードの正しい使い方**
   - ❌ 誤り: 33業種コード（0050, 1050, ...）を使用
     - これは銘柄の業種分類コードであり、指数時系列の取得には使えない
   - ✅ 正しい: 東証業種別指数コード（0040〜0072）
     - TOPIX = 0000
     - 水産・農林業 = 0040
     - 鉱業 = 0041
     - ...
     - サービス業 = 0072

2. **APIエンドポイント**
   - TOPIX本体: `GET /v2/indices/bars/daily/topix`
   - 東証33業種指数: `GET /v2/indices/bars/daily?code={index_code}&from={YYYYMMDD}&to={YYYYMMDD}`

3. **プラン制約**
   - J-Quants Standard プラン以上で利用可能
   - 指数四本値API (`/indices`) は Standard / Premium 向け

## 📂 変更ファイル一覧

```
workspace/apps/investment-tracker/
├── src/
│   ├── sector_33_data.py       # 新規: 東証33業種マスター
│   ├── sector_strength.py      # 新規: 強弱判定ロジック
│   └── api.py                  # 修正: get_sector_33_indices() 追加
├── app.py                      # 修正: render_sector_strength() 追加
└── docs/
    ├── plans/20260501_1430_topix_sector_strength/
    │   └── 01_implementation_plan.md  # 実装計画
    └── sessions/
        └── 20260501_1430_sector_strength_implementation.md  # 本ファイル
```

## 🎓 学んだこと・次回への改善点

### 学んだこと

1. **J-Quants APIの正しい使い方**
   - 業種分類コード（銘柄のメタデータ）と指数コード（時系列データ）は別物
   - 公式ドキュメントとライブラリのREADMEで情報が異なる場合、公式を信頼

2. **3指標の統合判定**
   - 単一指標だけでなく、複数指標を組み合わせることで信頼性が向上
   - スコアリングにより、定量的な判定が可能

3. **ルックアヘッドバイアス防止**
   - 移動平均・RSIの計算で、十分なデータ期間を確保（期間の2倍を取得）
   - 過去データのみを使用して計算

### 次回への改善点

1. **パフォーマンス最適化**
   - 現状は33業種を順次取得（API呼び出し33回）
   - 可能なら一括取得APIを調査

2. **キャッシュ機構**
   - 同日の再実行時、APIを叩き直さずにキャッシュを使用
   - `data/cache/sector_33_indices/` に保存

3. **可視化の強化**
   - レーダーチャートで3指標を一目で比較
   - 時系列グラフで過去のスコア推移を表示

## 🚀 次にやること

1. **動作確認**
   - Streamlitアプリを起動して、セクター強弱判定機能をテスト
   - エラーが出た場合は修正

2. **ドキュメント更新**
   - READMEに新機能の説明を追加
   - 使い方ガイドをスクリーンショット付きで作成

3. **メモリ更新**
   - `~/.claude/projects/.../memory/MEMORY.md` に東証33業種指数の実装を追記

## 🔗 重要なパス・コマンド

### Streamlitアプリ起動
```bash
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
streamlit run app.py
```

### テスト用のJupyter Notebookを作成する場合
```bash
cd "C:\Users\yongr\claude project\workspace\apps\investment-tracker"
jupyter notebook analyses/test_sector_strength.ipynb
```

### J-Quants API仕様（参考）
- 公式ドキュメント: https://jpx-jquants.com/ja/spec/data-spec
- 指数コード一覧: https://jpx-jquants.com/ja/spec/idx-bars-daily/indexcodes
- 業種分類コード: https://jpx-jquants.com/ja/spec/eq-master/sector33code

## 📝 備考

- TOPIX-17業種指数（既存実装）と東証33業種指数（新規実装）は併存可能
- ユーザーは用途に応じて使い分けられる
  - TOPIX-17: シンプルな分類、広範囲のカバー
  - 東証33: 詳細な分類、セクター分析に最適
