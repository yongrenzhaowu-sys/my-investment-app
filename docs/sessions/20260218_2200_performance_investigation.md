# セッションサマリー：パフォーマンス差異の調査

**日時**: 2026-02-18 22:00～
**所要時間**: 約30分
**目的**: 週次/月次戦略（-86.98%, -88.03%）と年次戦略（+35.64%）の大きな性能差の原因を特定

---

## やったこと

### 1. 年次パフォーマンスの確認（週次戦略）

Jupyter Notebookの Cell 19 出力を確認：

| 年 | リターン(%) | 最大DD(%) | 開始資産(百万円) | 終了資産(百万円) | リバランス回数 |
|----|------------|-----------|----------------|----------------|--------------|
| 2017 | **+32.68** | -14.44 | 10.00 | 13.27 | 52 |
| 2018 | **-28.43** | -34.16 | 12.36 | 8.85 | 52 |
| 2019 | **-53.69** | -70.11 | 8.67 | 4.02 | 51 |
| 2020 | **-35.00** | -82.93 | 3.50 | 2.27 | 52 |
| 2021 | -4.85 | -84.10 | 2.24 | 2.13 | 52 |
| 2022 | -8.49 | -87.29 | 2.01 | 1.84 | 52 |
| 2023 | **+32.82** | -86.63 | 1.77 | 2.36 | 52 |
| 2024 | +4.32 | -83.08 | 2.27 | 2.36 | 52 |
| 2025 | **+30.95** | -83.21 | 2.31 | 3.02 | 52 |
| 2026 | **-55.53** | -90.19 | 2.93 | 1.30 | 5 |

**重要な発見**：
- 2017年は+32.68%で好調スタート
- **2018～2020年に壊滅的な損失**（-28.43%, -53.69%, -35.00%）
- この3年間で資産が13.27百万円 → 2.27百万円に激減（-82.9%）
- 2023年と2025年に+30%超の回復があったが、資産規模が小さいため影響が限定的

### 2. 年次戦略のパフォーマンス確認

`idea_01.md`から確認（2016年10月～2025年10月、9年間）：

| 期間 | 税引前リターン | 税引後リターン | TOPIX | 超過リターン |
|------|--------------|--------------|-------|-------------|
| 2016-10～2017-10 | **+50.01%** | +39.85% | +26.74% | +13.11% |
| 2017-10～2018-10 | **+16.25%** | +12.95% | +8.58% | +4.37% |
| 2018-10～2019-10 | **-2.41%** | -2.41% | -8.87% | +6.46% |
| 2019-10～2020-10 | **+7.18%** | +5.72% | +10.66% | -4.94% |
| 2020-10～2021-10 | **+60.66%** | +48.34% | +12.65% | +35.69% |
| 2021-10～2022-10 | **+23.36%** | +18.62% | -4.73% | +23.35% |
| 2022-10～2023-10 | **+63.98%** | +50.98% | +9.73% | +41.25% |
| 2023-10～2024-10 | **+32.95%** | +26.26% | +10.45% | +15.81% |
| 2024-10～2025-10 | **+45.35%** | +36.14% | +13.63% | +22.50% |

**結果**：
- 年率リターン: **35.64%**（税引前）
- 唯一のマイナス: 2018-10～2019-10で-2.41%のみ
- 他の年はすべてプラス

### 3. データソースの違いを特定

#### 週次/月次戦略のデータソース
パス: `data/curated/jquants/`
- 価格データ: `prices/daily_quotes_all.parquet`
  - 期間: 2016-01-15 ~ 2026-02-17
  - 総レコード数: 10,051,531
  - ユニーク銘柄数: **5,308**
  - 列: date, code, open, high, low, close, volume

- 財務データ: `financials/statements_all.parquet`
  - 期間: 2016-01-15 ~ 2026-01-29
  - 総レコード数: 190,873
  - ユニーク銘柄数: **4,663**
  - fiscal_quarter分布: 1Q (38,865), 2Q (45,815), 3Q (38,559), FY (67,599)

**特徴**:
- J-Quants API V2から新規取得した生データ
- 列名: 小文字形式（date, code, close等）
- 調整後終値（AdjustedClose）がない → **未調整の終値を使用している可能性**

#### 年次戦略のデータソース
パス: `C:\Users\yongr\Project\merged_data_all_stocks\merged_parts\*.parquet`

**特徴**（`data_dictionary.md`より）:
- 日足+財務+ファクターが既に統合済み
- ユニーク銘柄数: 約4,000～5,000
- 列: Date, Code, **AdjustedClose**, Profit, Equity, PBR, ROE等
- **AdjustedClose（調整後終値）を使用**

### 4. 重要な違いのまとめ

| 項目 | 週次/月次戦略 | 年次戦略 |
|------|-------------|---------|
| **データソース** | data/curated/jquants/ | C:\Users\yongr\Project\merged_data_all_stocks\ |
| **データ取得元** | J-Quants API V2（新規取得） | 既存の統合データ |
| **銘柄数** | 5,308（価格）、4,663（財務） | 約4,000～5,000 |
| **価格データ** | **close（未調整終値）** | **AdjustedClose（調整後終値）** |
| **データ加工** | 生データ | 統合・ファクター計算済み |
| **リバランス頻度** | 週次（472回）、月次（110回） | 年次（10回） |
| **総リターン** | -86.98%（週次）、-88.03%（月次） | **+35.64%** |
| **最悪年** | 2019年（-53.69%）、2020年（-35.00%） | 2018-10～2019-10（-2.41%のみ） |

---

## 決めたこと

### 仮説：パフォーマンス差の主要因

#### 仮説1: **株式分割・併合の未調整（最も可能性が高い）**

**問題**:
- 週次/月次戦略は`close`（未調整終値）を使用
- 年次戦略は`AdjustedClose`（調整後終値）を使用
- 株式分割・併合が発生すると、未調整終値では不連続なジャンプが発生

**影響**:
- PBR計算: `PBR = close / bps`
  - 株式分割後、closeは1/2、1/10等に変化
  - bps（1株当たり純資産）も同様に調整されるはずだが、開示タイミングにずれがあると不一致
  - **結果**: PBRが異常値となり、誤った銘柄選定が発生

- 例: 1:10の株式分割
  - 分割前: close = 10,000円、bps = 1,000円 → PBR = 10.0
  - 分割後: close = 1,000円、bps = 1,000円（未更新） → **PBR = 1.0**（誤って割安と判定）

**検証方法**:
1. 2018～2020年に選定された銘柄を確認
2. 株式分割・併合が発生した銘柄がないか確認
3. AdjustedCloseを使用したバックテストを再実行

#### 仮説2: リバランス頻度の違い

**問題**:
- 週次戦略: 472回リバランス
- 月次戦略: 110回リバランス
- 年次戦略: 10回リバランス

**影響**:
- 頻繁なリバランスによる取引コスト（100株単位制約による未投資現金の増加）
- 短期的なノイズに反応しやすい

**反証**:
- 週次と月次の結果がほぼ同じ（-86.98% vs -88.03%）
- リバランス頻度が4倍以上違うのに、結果に大差なし
- **結論**: リバランス頻度は主要因ではない

#### 仮説3: データ品質の違い

**問題**:
- `merged_data_all_stocks`は何らかの前処理・検証済み
- `data/curated/jquants`は生データのまま

**影響**:
- 欠損値、異常値の処理が不十分
- 銘柄の上場・廃止のタイミングが正確でない

**検証方法**:
1. 2018～2020年のデータ品質をチェック
2. 欠損値、異常値の分布を確認

#### 仮説4: 財務データの質的な違い

**問題**:
- `data/curated/jquants`の財務データは新規取得
- `merged_data_all_stocks`の財務データは既存データ

**影響**:
- 決算訂正、再発表が反映されていない
- 開示日のタイミングが異なる

---

## 次にやること

### 優先度1: AdjustedClose（調整後終値）の導入 ✅ 必須

**目的**: 株式分割・併合の影響を除去する

**手順**:
1. J-Quants API V2からAdjustedClose列を取得できるか確認
   ```bash
   # データ確認
   python -c "
   import pandas as pd
   df = pd.read_parquet('data/curated/jquants/prices/daily_quotes_all.parquet')
   print(df.columns.tolist())
   # AdjustedCloseがあるか確認
   "
   ```

2. AdjustedCloseがない場合:
   - スクリプトを修正して、AdjustedCloseを取得・保存
   - または、既存のcloseから調整率を計算
   - J-Quants API V2のドキュメントを確認

3. AdjustedCloseがある場合:
   - `analysis_01_optimized.ipynb`のCell 3を修正
   ```python
   # 修正前
   df_price['close']

   # 修正後
   df_price['adjusted_close']  # または 'AdjustedClose'
   ```

4. バックテスト再実行

### 優先度2: 2018～2020年の選定銘柄を調査

**目的**: どのような銘柄が選定され、なぜ損失が発生したかを特定

**手順**:
1. `analysis_01_optimized.ipynb`に診断セルを追加
   ```python
   # 2019年1月のリバランス日の選定銘柄を確認
   test_date = pd.Timestamp('2019-01-04')  # 例
   selected = screen_stocks_fast(test_date, df_price_pivot, fin_by_date, 20)

   # 選定銘柄の詳細
   print(selected[['code', 'close', 'bps', 'pbr', 'roe']])

   # 株式分割の確認
   for code in selected['code']:
       price_history = df_price[df_price['code'] == code].sort_values('date')
       # 価格の急激な変化をチェック
       price_history['price_change'] = price_history['close'].pct_change()
       large_changes = price_history[abs(price_history['price_change']) > 0.5]
       if len(large_changes) > 0:
           print(f"銘柄{code}: 大きな価格変動あり")
           print(large_changes[['date', 'close', 'price_change']])
   ```

2. 選定銘柄のリストをCSV保存
   ```python
   selected.to_csv('selected_stocks_2019.csv')
   ```

### 優先度3: 年次戦略のデータソースとの比較

**目的**: `merged_data_all_stocks`のデータ品質を理解

**手順**:
1. `legacy/_inbox/merged_data_all_stocks/`のデータを確認
   ```bash
   python -c "
   import pandas as pd
   import glob

   files = glob.glob('legacy/_inbox/merged_data_all_stocks/merged_parts/*.parquet')
   df = pd.read_parquet(files[0])
   print(df.columns.tolist())
   print(df.head())
   "
   ```

2. 同じ銘柄・期間のデータを比較
   - `data/curated/jquants`と`merged_data_all_stocks`で同じ銘柄のcloseを比較
   - 差異があれば、調整率を計算

### 優先度4: データ品質チェックスクリプトの作成

**目的**: 生データの品質を自動チェック

**手順**:
1. `scripts/validate_data.py`を作成
   ```python
   import pandas as pd
   from pathlib import Path

   PROJECT_ROOT = Path(__file__).parent.parent

   # 価格データチェック
   df_price = pd.read_parquet(PROJECT_ROOT / 'data/curated/jquants/prices/daily_quotes_all.parquet')

   # 1. 欠損値チェック
   print("欠損値:")
   print(df_price.isnull().sum())

   # 2. 異常値チェック（価格が0以下）
   invalid_prices = df_price[df_price['close'] <= 0]
   print(f"異常な価格: {len(invalid_prices)} 件")

   # 3. 株式分割・併合の検出
   df_price['price_change'] = df_price.groupby('code')['close'].pct_change()
   large_changes = df_price[abs(df_price['price_change']) > 0.5]
   print(f"大きな価格変動（±50%超）: {len(large_changes)} 件")
   print(large_changes[['date', 'code', 'close', 'price_change']].head(20))
   ```

2. スクリプト実行
   ```bash
   python scripts/validate_data.py
   ```

---

## 重要なパス/コマンド

### データ確認コマンド
```bash
# 週次/月次戦略のデータソース
cd "C:\Users\yongr\claude project\workspace"
python -c "
import pandas as pd
df_price = pd.read_parquet('data/curated/jquants/prices/daily_quotes_all.parquet')
df_fin = pd.read_parquet('data/curated/jquants/financials/statements_all.parquet')
print('価格データ:', df_price.shape)
print('財務データ:', df_fin.shape)
print('価格データ列:', df_price.columns.tolist())
print('財務データ列:', df_fin.columns.tolist())
"
```

### Notebook再実行
```bash
# Jupyter起動
cd "C:\Users\yongr\claude project\workspace\analyses\20260218_1630_weekly_long_only"
jupyter notebook

# ブラウザで analysis_01_optimized.ipynb を開く
# Cell 3を修正してから、Run All
```

### データ品質チェック
```bash
# 株式分割・併合の検出
python -c "
import pandas as pd
df = pd.read_parquet('data/curated/jquants/prices/daily_quotes_all.parquet')
df['price_change'] = df.groupby('code')['close'].pct_change()
large_changes = df[abs(df['price_change']) > 0.5]
print(f'大きな価格変動: {len(large_changes)} 件')
print(large_changes[['date', 'code', 'close', 'price_change']].head(20))
"
```

---

## 学んだこと・注意点

### 1. 調整後終値（AdjustedClose）の重要性

**理由**:
- 株式分割・併合により、未調整終値は不連続に変化
- PBR等のバリュエーション指標が異常値となり、誤った銘柄選定を引き起こす

**対処**:
- 必ず調整後終値を使用
- J-Quants API V2で取得可能か確認
- 取得できない場合は、分割・併合情報から自動計算

### 2. リバランス頻度は主要因ではない

**確認事項**:
- 週次（472回）と月次（110回）で結果がほぼ同じ（-86.98% vs -88.03%）
- リバランス頻度の違いは、パフォーマンス差の主要因ではない

**結論**:
- データ品質（特に調整後終値）が最重要

### 3. データソースの違いが性能差の主要因

**2つのデータソース**:
1. `data/curated/jquants/`（新規取得、生データ）
2. `C:\Users\yongr\Project\merged_data_all_stocks\`（既存、統合・検証済み）

**性能差**:
- 新規データ: -86.98%（週次）、-88.03%（月次）
- 既存データ: **+35.64%**（年次）

**推測される違い**:
- 調整後終値の有無
- データ品質チェックの有無
- ファクター計算の正確性

### 4. 2018～2020年が転換点

**週次戦略の年次パフォーマンス**:
- 2017年: +32.68%（好調）
- 2018年: -28.43%
- 2019年: **-53.69%**（壊滅的）
- 2020年: **-35.00%**（壊滅的）

**仮説**:
- この期間に株式分割・併合が多発した可能性
- または、データ品質の問題が顕在化

**検証**:
- 2018～2020年の選定銘柄を確認
- 株式分割・併合の発生を確認

### 5. 年次戦略は頑健

**年次戦略の特徴**:
- 唯一のマイナス: 2018-10～2019-10で-2.41%のみ
- 他の年はすべてプラス
- 年率リターン: 35.64%

**理由**:
- 調整後終値（AdjustedClose）を使用
- データ品質が高い
- 年1回のリバランス（短期ノイズに反応しにくい）

### 6. fiscal_quarter フィルタは正常動作

**確認済み**:
- Cell 3で年次決算（FY）のみに絞り込み
- 171,943行 → 60,649行（35.3%）
- この部分は問題なし

**結論**:
- fiscal_quarter フィルタは仮説1～4の原因ではない

---

## 📊 パフォーマンス比較サマリ

| 戦略 | データソース | 価格列 | リバランス | 総リターン | 年率リターン | 最大DD | 最悪年 |
|------|------------|--------|----------|----------|------------|--------|--------|
| **年次** | merged_data_all_stocks | **AdjustedClose** | 10回 | **+35.64%** | **+35.64%** | -2.41% | 2018-10～2019-10 (-2.41%) |
| **週次** | data/curated/jquants | **close（未調整）** | 472回 | -86.98% | -20.05% | -90.19% | 2019年 (-53.69%) |
| **月次** | data/curated/jquants | **close（未調整）** | 110回 | -88.03% | -20.91% | -90.04% | 2019年 |

**結論**:
- 調整後終値（AdjustedClose）の使用が、パフォーマンス差の最大の要因と推測

---

## 📈 次回セッション候補

### 緊急度★★★（最優先）
1. **AdjustedCloseの導入**:
   - J-Quants API V2でAdjustedCloseを取得
   - `fetch_jquants_data.py`を修正
   - データ再取得
   - バックテスト再実行

### 緊急度★★（重要）
2. **2018～2020年の選定銘柄調査**:
   - 選定銘柄のリスト作成
   - 株式分割・併合の確認
   - 異常値の特定

### 緊急度★（任意）
3. **データ品質チェックスクリプト作成**:
   - `scripts/validate_data.py`を作成
   - 自動チェック機能を実装

4. **年次戦略データソースの調査**:
   - `merged_data_all_stocks`の詳細確認
   - データ処理方法の理解

---

**ステータス**: データソースの違いを特定、調整後終値の重要性を確認
**次のアクション**: AdjustedClose導入、バックテスト再実行
**推定所要時間**: 1～2時間

