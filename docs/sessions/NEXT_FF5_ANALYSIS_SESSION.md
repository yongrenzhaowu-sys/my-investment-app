# FF5ファクター分析 - 次回セッション開始ガイド

**最終更新**: 2026-03-19 00:00
**前回セッション**: `docs/sessions/20260319_0000_ff5_corrected_screening.md`

---

## ✅ 前回完了タスク（2026-03-19）

### 1. 調整済み株価の修正（CRITICAL）🚨
- **問題**: J-Quants APIの`AdjC`列が実際には調整されていない（`AdjC = C`）
- **影響**: 極端なリターン値（+3,273%）が発生、時価総額・PBRも誤計算
- **解決**: `AdjC_Correct = C × AdjFactor`で正しく計算
- **効果**: 極端なリターン値が+3,273%から+568.73%に改善
- **詳細**: `docs/knowledges/20260319_0000_adjusted_price_validation.md`

### 2. FF5ファクター再計算（全期間、調整済み株価版）✅
- **期間**: 2021-03～2026-03（5年間）
- **ウィンドウ**: 12ヶ月×50ウィンドウ（1ヶ月スライド）
- **対象**: 全銘柄（4,976銘柄）
- **結果**（5年平均）:
  - MKT: +7.57%（SR 0.62）← 市場全体は上昇
  - SMB: -12.00%（SR -2.43）← **大型株優勢**
  - HML: -17.29%（SR -1.52）← **グロース株優勢**
  - RMW: -9.28%（SR -1.45）← 収益性弱い
  - CMA: -1.25%（SR -0.38）← 投資弱い
  - WML: -6.04%（SR -1.15）← モメンタム弱い

### 3. 銘柄スクリーニング完了（調整済み株価版）✅
- **条件**:
  1. 時価総額上位30%（≧747.9億円）
  2. 6ヶ月リターン中央値以上（≧1.54%）← モメンタムを緩和
  3. PBR≧2.0（グロース株）
- **結果**: 204銘柄抽出
- **統計**:
  - 平均6ヶ月リターン: 56.57%（中央値37.85%）
  - 平均時価総額: 1.98兆円（中央値3,412億円）
  - 平均PBR: 4.23（中央値3.11）
- **出力**: `analyses/20260318_1800_ff5_rolling_6years/results/screened_stocks_corrected.csv`

### 4. 上位10銘柄（時価総額順）
| 銘柄コード | 企業名 | 時価総額 | 6M騰落率 | PBR | 営業利益率 |
|:---:|:---|---:|---:|---:|---:|
| 6501 | 日立製作所 | 22.6兆円 | +23.45% | 3.44 | 11.0% |
| 8058 | 三菱商事 | 21.0兆円 | +49.01% | 2.13 | N/A |
| 9983 | ファーストリテイリング | 20.5兆円 | +32.17% | 7.96 | 20.5% |
| 6857 | アドバンテスト | 18.1兆円 | +98.07% | 26.87 | 43.2% |
| 8035 | 東京エレクトロン | 18.1兆円 | +86.12% | 9.02 | 24.2% |
| 7011 | 三菱重工業 | 16.0兆円 | +27.31% | 5.75 | N/A |
| 4519 | 中外製薬 | 15.4兆円 | +40.19% | 7.61 | 47.6% |
| 6861 | キーエンス | 14.8兆円 | +8.93% | 4.44 | 49.9% |
| 4063 | 信越化学工業 | 12.7兆円 | +47.19% | 2.83 | 25.8% |
| 6503 | 三菱電機 | 11.5兆円 | +49.11% | 2.68 | 7.1% |

---

## 🎯 次回タスク（優先順位順）

### 優先度1: バックテスト実施 ⭐️⭐️⭐️
**目的**: スクリーニング戦略の有効性検証

**設定**
- 対象: 204銘柄（調整済み株価版）
- リバランス: 月次（毎月月初）
- ポートフォリオサイズ: 10～30銘柄
- 期間: 2021-03～2026-03（5年間）

**実装タスク**
```python
# ファイル: analyses/20260318_1800_ff5_rolling_6years/backtest_ff5_strategy.py
#
# 機能:
# 1. 毎月月初にスクリーニング条件を適用
# 2. 上位N銘柄を等金額で購入
# 3. 1ヶ月後にリバランス
# 4. パフォーマンス指標を計算（リターン、SR、MDD、勝率）
```

**注意事項**
- ✅ 調整済み株価を使用（`C × AdjFactor`）
- ✅ ルックアヘッドバイアス防止（t日終値でシグナル → t+1日始値でエントリー）
- ✅ 各時点でスクリーニング条件を再計算（全期間統計を使わない）

**参照**
- `docs/knowledges/20260225_1900_lookahead_bias_correction.md`（ルックアヘッドバイアス防止）
- `docs/knowledges/20260319_0000_adjusted_price_validation.md`（調整済み株価検証）

---

### 優先度2: リスク分析 ⭐️⭐️
**目的**: ポートフォリオのリスク特性を把握

**分析項目**
1. **セクター集中度**
   - 上位10銘柄の業種分布
   - TOPIX業種分類（33業種）

2. **ファクターエクスポージャー**
   - 時価総額: 平均1.98兆円（大型株中心）
   - PBR: 平均4.23（グロース株中心）
   - 6ヶ月リターン: 平均56.57%（高モメンタム）

3. **最大ドローダウン**
   - 過去5年間の最悪期
   - リーマンショック級のストレステスト

**実装タスク**
```python
# ファイル: analyses/20260318_1800_ff5_rolling_6years/risk_analysis.py
#
# 機能:
# 1. セクター分類の追加（J-Quants API）
# 2. 時系列でのセクター集中度推移
# 3. ファクターエクスポージャーの時系列推移
```

---

### 優先度3: ポートフォリオサイズの最適化 ⭐️
**目的**: 分散効果とリターンのトレードオフを検証

**検証内容**
- N = 5, 10, 20, 30, 50銘柄で比較
- 各Nでのリターン、シャープレシオ、最大ドローダウン

**仮説**
- N=10: 高リターン・高リスク
- N=30: 中リターン・中リスク
- N=50: 低リターン・低リスク

---

## 📁 重要ファイル

### データ（5年間、調整済み株価版）
- `data/processed/jquants_historical_6years/daily_bars_2021_2026.parquet`
  - 株価: 5,285,728レコード → 5,282,853レコード（重複除外後）
  - 対象銘柄: 4,976銘柄
  - 期間: 2021-03-01～2026-03-13

- `data/processed/jquants_historical_6years/financials_2021_2026.parquet`
  - 財務: 91,734レコード
  - 対象銘柄: 4,375銘柄
  - 期間: 2021-03-01～2026-03-13

### FF5分析結果（調整済み株価版）
- `analyses/20260318_1800_ff5_rolling_6years/results/ff5_rolling_factors_corrected.csv`
  - 50ウィンドウ×6ファクター（MKT, SMB, HML, RMW, CMA, WML）

### スクリーニング結果（調整済み株価版）
- `analyses/20260318_1800_ff5_rolling_6years/results/screened_stocks_corrected.csv`
  - 204銘柄

### 実装スクリプト
- `analyses/20260318_1800_ff5_rolling_6years/calculate_ff5_rolling_corrected.py`（FF5ファクター計算）
- `analyses/20260318_1800_ff5_rolling_6years/screen_stocks_corrected.py`（銘柄スクリーニング）
- `analyses/20260318_1800_ff5_rolling_6years/visualize_simple.py`（可視化）

---

## 🚨 重要な教訓（必読）

### 1. 調整済み株価の検証
**必ず実施**: `docs/knowledges/20260319_0000_adjusted_price_validation.md`

```python
# AdjFactorの確認
print(f"AdjFactor != 1.0: {(df['AdjFactor'] != 1.0).sum()}レコード")

# 正しい調整
df['AdjC_Correct'] = df['C'] * df['AdjFactor']
df['Price'] = df['AdjC_Correct']

# 重複除外
df = df.sort_values(['Code', 'Date', 'Vo'], ascending=[True, True, False])
df = df.drop_duplicates(subset=['Code', 'Date'], keep='first')
```

### 2. ルックアヘッドバイアス防止
**必ず実施**: `docs/knowledges/20260225_1900_lookahead_bias_correction.md`

```python
# ❌ 間違い: 全期間で四分位計算
df['quartile'] = pd.qcut(df['value'], q=4)

# ✅ 正しい: 各時点で利用可能なデータのみ
available = df[df['date'] <= current_date]
available['quartile'] = pd.qcut(available['value'], q=4)
```

### 3. BPS代替計算
**必要時**: `docs/knowledges/20260318_1730_bps_recovery_technique.md`

```python
# BPSが欠損している場合
df_fins['SharesOut'] = df_fins['ShOutFY'].fillna(df_fins['TrShFY']).fillna(df_fins['AvgSh'])
df_fins['BPS_Calc'] = df_fins['Eq'] / df_fins['SharesOut']
df_fins['BPS_Final'] = df_fins['BPS'].fillna(df_fins['BPS_Calc'])
```

---

## 📊 現在の分析状況

### データ期間
- **開始**: 2021-03-01
- **終了**: 2026-03-13
- **期間**: 5年間（60ヶ月）

### 対象銘柄
- **株価データ**: 4,976銘柄
- **財務データ**: 4,375銘柄
- **スクリーニング後**: 204銘柄

### ファクター結果（5年平均）
| ファクター | 年率リターン | シャープレシオ | 解釈 |
|:---:|---:|---:|:---|
| **MKT** | +7.57% | 0.62 | 市場全体は上昇 |
| **SMB** | -12.00% | -2.43 | **大型株優勢** |
| **HML** | -17.29% | -1.52 | **グロース株優勢** |
| **RMW** | -9.28% | -1.45 | 収益性は弱い |
| **CMA** | -1.25% | -0.38 | 投資は弱い |
| **WML** | -6.04% | -1.15 | モメンタム弱い |

### 最新ウィンドウ（2025-04～2026-03）
- MKT: +24.02%
- SMB: -18.37%（大型株優勢継続）
- HML: -18.35%（グロース株優勢継続）
- WML: +6.76%（モメンタムはやや回復）

### スクリーニング条件
1. **時価総額上位30%**（≧747.9億円）
2. **6ヶ月リターン中央値以上**（≧1.54%）
3. **PBR≧2.0**（グロース株）

### 投資戦略の示唆
✅ **大型株**（SMB -12.00%）
✅ **グロース株**（HML -17.29%）
⚠️ **モメンタムは緩和**（WML -6.04%、最新+6.76%）

---

## 🎯 次回セッション開始コマンド

### データ確認
```powershell
cd "C:\Users\yongr\claude project\workspace\analyses\20260318_1800_ff5_rolling_6years"

# スクリーニング結果を確認
python -c "import pandas as pd; df = pd.read_csv('results/screened_stocks_corrected.csv'); print(df.head(10))"

# FF5ファクターを確認
python -c "import pandas as pd; df = pd.read_csv('results/ff5_rolling_factors_corrected.csv'); print(df.tail(10))"
```

### バックテスト開始
```powershell
# 新規スクリプト作成
python backtest_ff5_strategy.py --start 2021-03 --end 2026-03 --portfolio-size 20
```

---

## 📚 関連ドキュメント

### 最新セッション
- `docs/sessions/20260319_0000_ff5_corrected_screening.md`（調整済み株価修正、FF5再計算、スクリーニング完了）

### ナレッジベース
- `docs/knowledges/20260319_0000_adjusted_price_validation.md`（🆕 調整済み株価検証）
- `docs/knowledges/20260225_1900_lookahead_bias_correction.md`（ルックアヘッドバイアス防止）
- `docs/knowledges/20260318_1730_bps_recovery_technique.md`（BPS代替計算）

### 過去セッション
- `docs/sessions/20260318_1800_ff5_rolling_start.md`（ローリング分析開始）
- `docs/sessions/20260318_1730_bps_recovery_complete.md`（BPS復旧完了）

---

## 💡 改善効果

### 修正前（誤った調整済み株価）
- データソース: `AdjC`列（未調整）
- 最大リターン: **+3,273%**（異常値）
- 極端な銘柄が多数抽出

### 修正後（正しい調整済み株価）
- データソース: `C × AdjFactor`
- 最大リターン: **+568.73%**（より現実的）
- 大型優良株が上位に

---

**次回開始時**: このファイルを最初に確認してください！
