# J-Quants Legacy データスキーマ定義

**作成日**: 2026-02-18
**データソース**: legacy/_inbox/jquants_*_10y_parquet/

---

## 1. 価格データ（OHLCV）

**パス**: `legacy/_inbox/jquants_daily_bars_10y_parquet/daily_parquet/date=YYYY-MM-DD.parquet`

### 1.1 基本情報
- **形式**: 日付パーティション（1ファイル = 1日分の全銘柄）
- **最新日**: 2026-01-22
- **レコード数例**: 4,435行/日（約4,400銘柄）
- **カラム数**: 16

### 1.2 カラム定義

| カラム名 | データ型 | 説明 | 備考 |
|----------|----------|------|------|
| Date | datetime64[ns] | 日付 | パーティションキー |
| Code | object | 銘柄コード | 4桁数値文字列（例："13010"） |
| O | float64 | 始値（非調整） | Open |
| H | float64 | 高値（非調整） | High |
| L | float64 | 安値（非調整） | Low |
| C | float64 | 終値（非調整） | Close |
| UL | object | 値幅上限フラグ | Upper Limit（推定） |
| LL | object | 値幅下限フラグ | Lower Limit（推定） |
| Vo | float64 | 出来高 | Volume |
| Va | float64 | 出来高金額 | Volume Amount |
| AdjFactor | float64 | 調整係数 | 分割・併合調整 |
| AdjO | float64 | 調整済み始値 | = O × AdjFactor |
| AdjH | float64 | 調整済み高値 | = H × AdjFactor |
| AdjL | float64 | 調整済み安値 | = L × AdjFactor |
| AdjC | float64 | 調整済み終値 | = C × AdjFactor |
| AdjVo | float64 | 調整済み出来高 | = Vo / AdjFactor |

### 1.3 サンプルデータ

```
Date        Code    O       H       L       C     Vo        AdjC
2026-01-22  13010   5030.0  5040.0  4980.0  5030.0  38800.0   5030.0
2026-01-22  13050   3859.0  3859.0  3833.0  3835.0  59420.0   3835.0
2026-01-22  13060   3817.0  3818.0  3794.0  3801.0  1460340.0 3801.0
```

### 1.4 J-Quants API との対応

**今回の要件**: 調整済み価格のみ使用

| Legacy カラム | J-Quants API フィールド | curated 出力カラム |
|---------------|------------------------|-------------------|
| Date | Date | date |
| Code | Code | code |
| AdjO | AdjustmentOpen | open |
| AdjH | AdjustmentHigh | high |
| AdjL | AdjustmentLow | low |
| AdjC | AdjustmentClose | close |
| AdjVo | AdjustmentVolume | volume |

**非使用カラム**: O, H, L, C, Vo, Va, UL, LL（非調整価格は今回不要）

---

## 2. 財務データ

**パス**: `legacy/_inbox/jquants_fins_summary_10y_parquet/daily_parquet/date=YYYY-MM-DD.parquet`

### 2.1 基本情報
- **形式**: 日付パーティション（1ファイル = その日に開示された全銘柄の財務データ）
- **最新日**: 2026-01-09
- **レコード数例**: 81行/日（開示があった銘柄のみ）
- **カラム数**: 108

### 2.2 主要カラム定義

#### 2.2.1 識別情報
| カラム名 | データ型 | 説明 |
|----------|----------|------|
| DiscDate | datetime64[ns] | 開示日（Disclosed Date） |
| DiscTime | object | 開示時刻（"16:00:00"形式） |
| Code | object | 銘柄コード |
| DiscNo | object | 開示番号（EDINET書類番号相当） |
| DocType | object | 文書タイプ（例："3QFinancialStatements_Consolidated_JP"） |

#### 2.2.2 期間情報
| カラム名 | データ型 | 説明 |
|----------|----------|------|
| CurPerType | object | 当期タイプ（"1Q", "2Q", "3Q", "FY"） |
| CurPerSt | datetime64[ns] | 当期開始日 |
| CurPerEn | datetime64[ns] | 当期終了日 |
| CurFYSt | datetime64[ns] | 会計年度開始日 |
| CurFYEn | datetime64[ns] | 会計年度終了日 |

#### 2.2.3 実績値（連結）
| カラム名 | データ型 | 説明 |
|----------|----------|------|
| Sales | float64 | 売上高 |
| OP | float64 | 営業利益（Operating Profit） |
| OdP | float64 | 経常利益（Ordinary Profit） |
| NP | float64 | 純利益（Net Profit） |
| EPS | float64 | 1株当たり利益（円） |
| DEPS | float64 | 希薄化後EPS |
| TA | float64 | 総資産（Total Assets） |
| Eq | float64 | 自己資本（Equity） |
| EqAR | float64 | 自己資本比率（Equity to Asset Ratio） |
| BPS | float64 | 1株当たり純資産（円） |

#### 2.2.4 予想値（Forecast）
| カラム名 | データ型 | 説明 |
|----------|----------|------|
| FSales | float64 | 売上高予想（当期通期） |
| FOP | float64 | 営業利益予想 |
| FOdP | float64 | 経常利益予想 |
| FNP | float64 | 純利益予想 |
| FEPS | float64 | EPS予想 |
| NxFSales | float64 | 来期売上高予想 |
| NxFOP | float64 | 来期営業利益予想 |
| NxFNP | float64 | 来期純利益予想 |
| NxFEPS | float64 | 来期EPS予想 |

#### 2.2.5 配当
| カラム名 | データ型 | 説明 |
|----------|----------|------|
| Div1Q, Div2Q, Div3Q, DivFY | float64 | 各四半期・通期配当（円） |
| DivAnn | float64 | 年間配当予想 |
| FDivFY | float64 | 当期配当予想 |
| NxFDivFY | float64 | 来期配当予想 |
| PayoutRatioAnn | float64 | 配当性向（%） |

#### 2.2.6 単体値（NC = Non-Consolidated）
| カラム名 | データ型 | 説明 |
|----------|----------|------|
| NCSales, NCOP, NCOdP, NCNP | float64 | 単体：売上、営業利益、経常利益、純利益 |
| NCEPS | float64 | 単体EPS |
| NCTA, NCEq | float64 | 単体：総資産、自己資本 |

### 2.3 サンプルデータ（簡略版）

```
DiscDate    Code   DocType                          Sales         OP          NP      EPS    TA         Eq
2026-01-09  59820  3QFinancialStatements_Consolidated  5.06e10  4.90e9  3.80e9  239.82  7.46e10  5.03e10
2026-01-09  66680  1QFinancialStatements_Consolidated  2.41e9   2.13e8  1.02e8   12.00  2.70e10  1.34e10
```

### 2.4 J-Quants API との対応

**今回の要件**: 発表日以降のみ使用（未来参照回避）

| Legacy カラム | J-Quants API フィールド | curated 出力カラム | 備考 |
|---------------|------------------------|-------------------|------|
| DiscDate | DisclosedDate | disclosed_date | 有効日として使用 |
| DiscTime | DisclosedTime | disclosed_time | |
| Code | Code | code | |
| CurPerType | FiscalQuarter | fiscal_quarter | "1Q", "2Q", "3Q", "FY" |
| CurFYEn | FiscalYear | fiscal_year | 会計年度終了日 |
| Sales | NetSales | net_sales | |
| OP | OperatingProfit | operating_profit | |
| OdP | OrdinaryProfit | ordinary_profit | |
| NP | Profit | net_profit | |
| EPS | EarningsPerShare | eps | |
| TA | TotalAssets | total_assets | |
| Eq | Equity | equity | |
| BPS | BookValuePerShare | bps | |

---

## 3. 差分更新時の注意点

### 3.1 価格データ
- **キー**: (Date, Code)
- **重複処理**: 後勝ち（API取得データを優先） ← 訂正データ対応
- **欠損日**: QCで検出するが、エラーにはしない（営業日カレンダー未整備のため）

### 3.2 財務データ
- **キー**: (Code, DiscDate, DiscNo)
  - 同一日に複数開示がある場合（訂正、修正など）を考慮
- **重複処理**: 後勝ち（API取得データを優先）
- **未来参照チェック**: DiscDate < CurPerEn の場合は警告（通常はDiscDate >= CurPerEn）

---

## 4. データ品質（既知の問題）

### 4.1 価格データ
- ✅ AdjFactor は正常（1.0が多数、分割時のみ変動）
- ✅ 欠損値は少ない（上場廃止・売買停止銘柄のみ）
- ⚠️ UL/LL の意味が不明（"0"が大半）→ 今回は使用しない

### 4.2 財務データ
- ✅ DocType で文書種別が判別可能
- ⚠️ NaN が多い（予想値は未発表の場合NaN）
- ⚠️ 単体値（NC*）は一部銘柄のみ提供

---

## 5. 統合時のマッピング計画

### 5.1 consolidate_legacy.py の処理

1. **全パーティション読み込み**: `pd.read_parquet(..., engine='pyarrow')`
2. **カラムリネーム**:
   ```python
   rename_map_prices = {
       'Date': 'date',
       'Code': 'code',
       'AdjO': 'open',
       'AdjH': 'high',
       'AdjL': 'low',
       'AdjC': 'close',
       'AdjVo': 'volume'
   }
   ```
3. **不要カラム削除**: O, H, L, C, Vo, Va, UL, LL, AdjFactor
4. **重複削除**: `drop_duplicates(subset=['date', 'code'], keep='last')`
5. **ソート**: `sort_values(['code', 'date'])`
6. **保存**: `to_parquet('data/curated/jquants/prices/daily_quotes_all.parquet')`

### 5.2 update_jquants_prices.py の処理（API取得後）

1. **API レスポンスのカラムリネーム**:
   ```python
   rename_map_api = {
       'Date': 'date',
       'Code': 'code',
       'AdjustmentOpen': 'open',
       'AdjustmentHigh': 'high',
       'AdjustmentLow': 'low',
       'AdjustmentClose': 'close',
       'AdjustmentVolume': 'volume'
   }
   ```
2. **既存curated読み込み**
3. **新規データ追加**: `pd.concat([curated, new_data])`
4. **重複削除**: `drop_duplicates(subset=['date', 'code'], keep='last')`
5. **ソート & 保存**

---

**メンテナンス**:
- APIスキーマ変更時は本ドキュメントを更新
- カラムマッピング変更時は consolidate_legacy.py と update_jquants_*.py を同時修正
