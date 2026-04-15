# J-Quants APIで最新データ取得＆FF5ファクター更新分析

**作成日時**: 2026-03-15 16:00
**ステータス**: 計画中
**目的**: J-Quants API V2を使って最新データ（2026年3月まで）を取得し、FF5ファクター分析を更新

---

## 📋 背景

### 現状の課題
- **既存データ**: 2025-09-30まで（約5.5ヶ月前）
- **未反映期間**: 2025年10月 ～ 2026年3月（約5.5ヶ月）
- **影響**: 直近の市場変動が分析に反映されていない

### 解決策
J-Quants API V2を使って最新データを取得し、FF5ファクターを再計算

---

## 🎯 実装目標

### 1. 最新データ取得
- [ ] 株価データ（日次バー）: 2025-10-01 ～ 2026-03-15
- [ ] 財務データ（四半期決算）: 2025年Q3-Q4の開示データ
- [ ] 銘柄マスター（業種分類）: 最新版

### 2. FF5ファクター計算
- [ ] 時価総額（MarketCap）の更新
- [ ] BM比率（Book-to-Market）の更新
- [ ] 収益性指標（ROE、営業利益率）の更新
- [ ] 投資指標（総資産成長率）の更新
- [ ] モメンタム（過去6ヶ月リターン）の計算

### 3. ファクターリターン計算
- [ ] 月次ポートフォリオ構築（2×3ソート）
- [ ] MKT、SMB、HML、RMW、CMA、WMLの月次リターン
- [ ] 2026年1月、2月、3月の最新ファクターリターン

### 4. 分析更新
- [ ] 直近12ヶ月のパフォーマンス再計算
- [ ] 有効ファクターランキング更新
- [ ] 推奨戦略の見直し

---

## 📊 データ取得計画

### Step 1: APIキー設定確認
```powershell
# Windows環境変数に設定（推奨）
setx JQUANTS_API_KEY "your_api_key_here"

# または .env ファイル（プロジェクトルート）
JQUANTS_API_KEY=your_api_key_here
```

### Step 2: 株価データ取得
```python
# エンドポイント: /v2/equities/bars/daily
# パラメータ: start_dt=20251001, end_dt=20260315
# 取得列: Date, Code, AdjC（調整済み終値）、AdjVo（調整済み出来高）

# 全銘柄（約4000銘柄）× 約120営業日 ≈ 48万レコード
```

### Step 3: 財務データ取得
```python
# エンドポイント: /v2/fins/summary
# 取得列: Code, DisclosedDate, Sales, OP, Profit, Equity, Assets

# 2025年Q3-Q4の開示データ（約8000レコード）
```

### Step 4: データマージ
```python
# 既存データ（2016-01 ～ 2025-09）+ 新規データ（2025-10 ～ 2026-03）
# 月次スナップショット再構築
```

---

## 🔬 FF5ファクター計算方法

### 1. 月次スナップショット作成
```python
# 各月末時点での銘柄スナップショット
for month_end in [2025-10-31, 2025-11-30, 2025-12-31, 2026-01-31, 2026-02-28, 2026-03-31]:
    # 株価データ（月末終値）
    price = get_price_at_month_end(month_end)

    # 財務データ（月末時点で利用可能な最新データ）
    # 注意: 未来参照バイアス防止（DisclosedDate < month_end）
    financials = get_latest_financials(disclosed_before=month_end)

    # マージ
    snapshot = merge(price, financials)
```

### 2. ファクター計算
```python
# 時価総額（MarketCap）
MarketCap = AdjC * SharesOut

# BM比率（Book-to-Market）
BM = Equity / MarketCap

# 収益性（ROE）
ROE = Profit / Equity

# 営業利益率
OP_Margin = OP / Sales

# 投資（総資産成長率）
INV_Growth = (Assets_t - Assets_t-1) / Assets_t-1

# モメンタム（過去6ヶ月リターン、t-7 ～ t-1ヶ月）
MOM_6M = (Price_t-1 / Price_t-7) - 1
```

### 3. ポートフォリオ構築（2×3ソート）
```python
# サイズ（Size）: 時価総額で2分位
# Size = Small（下位50%）, Big（上位50%）

# 各ファクター: 3分位
# HML: BM比率で3分位（L=下位30%, M=中位40%, H=上位30%）
# RMW: 収益性で3分位（W=下位30%, M=中位40%, R=上位30%）
# CMA: 投資で3分位（A=上位30%, M=中位40%, C=下位30%）

# 6ポートフォリオ構築
portfolios = {
    'SL': Small & Low,
    'SM': Small & Mid,
    'SH': Small & High,
    'BL': Big & Low,
    'BM': Big & Mid,
    'BH': Big & High
}

# ファクターリターン
HML = (SH + BH) / 2 - (SL + BL) / 2
SMB = (SL + SM + SH) / 3 - (BL + BM + BH) / 3
RMW = (SR + BR) / 2 - (SW + BW) / 2
CMA = (SC + BC) / 2 - (SA + BA) / 2
WML = Winners - Losers  # モメンタム
MKT = 等ウェイト市場リターン
```

---

## 📁 出力ファイル

### データファイル
- `data/processed/jquants_latest/daily_bars_2025_2026.parquet`（株価データ）
- `data/processed/jquants_latest/financials_2025_2026.parquet`（財務データ）
- `data/processed/jquants_latest/month_end_snapshot_updated.parquet`（月次スナップショット）

### ファクターファイル
- `data/processed/jquants_latest/ff5_factors_monthly_updated.parquet`（FF5月次ファクター）
- `analyses/20260315_1600_jquants_latest_ff5/factor_returns_2026.csv`（2026年最新）

### レポート
- `docs/sessions/20260315_1600_jquants_latest_ff5.md`（セッション記録）
- `docs/knowledges/20260315_1600_ff5_updated_analysis.md`（更新後の知見）

---

## ⚠️ 注意事項

### 未来参照バイアス防止（CRITICAL）
- ✅ t月末時点で利用可能な財務データのみ使用
- ✅ DisclosedDate < month_end を厳守
- ✅ t月末のファクター値 → t+1月のリターン予測に使用

### APIレート制限
- J-Quants APIのレート制限: 1秒あたり10リクエスト
- 全銘柄取得時は適切な待機時間を設定

### データ遅延
- 株価データ: 1〜2日遅れ
- 財務データ: 決算発表後、数日〜数週間遅れ
- 最新月（2026年3月）は月末確定前のため、暫定データの可能性あり

---

## 📅 実装スケジュール

### Phase 1: 環境準備（10分）
- [ ] APIキー設定確認
- [ ] J-Quantsクライアントの動作確認
- [ ] 出力ディレクトリ作成

### Phase 2: データ取得（30分）
- [ ] 銘柄マスター取得（業種分類含む）
- [ ] 株価データ取得（2025-10 ～ 2026-03）
- [ ] 財務データ取得（2025年Q3-Q4）

### Phase 3: データマージ（20分）
- [ ] 既存データと新規データの結合
- [ ] 月次スナップショット再構築
- [ ] 欠損値・異常値の確認

### Phase 4: FF5ファクター計算（30分）
- [ ] ファクター値計算（BM、ROE、INV_Growth、MOM）
- [ ] ポートフォリオ構築（2×3ソート）
- [ ] 月次ファクターリターン計算

### Phase 5: 分析更新（20分）
- [ ] 直近12ヶ月のパフォーマンス再計算
- [ ] 有効ファクターランキング更新
- [ ] 可視化（グラフ）

### Phase 6: ドキュメント更新（10分）
- [ ] セッション記録作成
- [ ] ナレッジ更新
- [ ] 推奨戦略の見直し

**推定所要時間**: 120分（2時間）

---

## 🔑 前提条件

### 必須
1. ✅ J-Quants APIキー（環境変数 `JQUANTS_API_KEY`）
2. ✅ Python環境（pandas, requests, pyarrow）
3. ✅ 既存データ（`legacy/_inbox/merged_data_all_stocks/factors/`）

### オプション
- Docker環境（セキュア実行）
- GitHub Actions（自動更新）

---

## 🎓 期待される成果

### 定量的成果
1. **最新ファクターリターン**（2026年1月、2月、3月）
2. **更新後の有効ファクターランキング**（直近12ヶ月）
3. **トレンド分析**（ファクター効果の時間変化）

### 定性的成果
- 現時点（2026年3月）での市場環境の把握
- 有効ファクターの変化の検出
- 実運用に向けた戦略の精緻化

---

## 📚 参考資料

- `docs/knowledges/20260311_1800_jquants_api_v2_complete.md`: J-Quants API V2完全ガイド
- `docs/knowledges/20260315_1500_ff5_current_effectiveness.md`: 既存のFF5分析結果
- `jquants-sector-momo/src/momo/providers/jquants_provider.py`: 既存のAPIクライアント

---

**作成者**: Claude Code
**承認**: 未承認
**次のアクション**: APIキー設定確認 → データ取得スクリプト作成
