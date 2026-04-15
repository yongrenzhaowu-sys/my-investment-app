# 持ち株バリュエーション分析システム 実装計画

## 目的
投資判断支援アプリ (`apps/investment-tracker/`) に、現在の持ち株に対して複数のバリュエーション分析を半自動で実行する機能を追加する。

## 背景
- 営業利益×10手法の有効性を確認（中型株でCAGR 19.09%）
- FCF手法も比較済み（営業利益×10の方が優位）
- 現在の持ち株に対してより多角的な分析を行い、投資判断を支援したい

## 分析項目（4つ）

### 1. PEG Ratio（完全実装可能）
- **計算式**: `PEG = PER / (成長率 × 100)`
- **データ**: NP（純利益）から PER 計算、過去5年の NP から成長率計算
- **判定基準**:
  - PEG < 1.0: 割安（成長性に対して株価が低い）
  - PEG 1.0-2.0: 適正
  - PEG > 2.0: 割高

### 2. Moving Average Divergence（完全実装可能）
- **計算対象**: 25日移動平均線、75日移動平均線
- **データ**: 日次株価データ（`daily_bars_2021_2026.parquet`）
- **判定基準**:
  - 現在価格が25日MAより上: 短期上昇トレンド
  - 現在価格が75日MAより上: 中期上昇トレンド
  - 25日MAが75日MAを上抜け（ゴールデンクロス）: 買いシグナル
  - 25日MAが75日MAを下抜け（デッドクロス）: 売りシグナル

### 3. EV/EBITDA（簡易版）
- **計算式**: `EV/EBITDA = (時価総額 + 純負債) / EBITDA`
- **データ制約**: EBITDAデータなし → 営業利益（OP）で代用
- **簡易計算**:
  - `EV = 時価総額 + (総資産 - 自己資本 - 現金)`
  - `EBITDA ≈ 営業利益（OP）`
- **判定基準**:
  - EV/EBITDA < 10: 割安
  - EV/EBITDA 10-15: 適正
  - EV/EBITDA > 15: 割高

### 4. DCF Proxy（簡易版）
- **計算式**: `理論株価 = FCF × (1 / WACC) / 発行済株式数`
- **簡易仮定**:
  - WACC = 10%（固定）
  - FCF = CFO - CFI
  - 発行済株式数 = 時価総額 / 株価
- **判定基準**:
  - 現在株価 / 理論株価 < 0.8: 割安
  - 0.8-1.2: 適正
  - > 1.2: 割高

## 技術スタック

### データソース
- **J-Quants API**: 財務データ、株価データ（既存のparquetファイル使用）
- **ローカルデータ**:
  - `data/processed/jquants_historical_6years/daily_bars_2021_2026.parquet`
  - `data/processed/jquants_historical_6years/financials_2021_2026.parquet`

### アプリ構成
- **既存**: `apps/investment-tracker/app.py`（Streamlit）
- **新規**:
  - `apps/investment-tracker/valuation_analysis.py` - バリュエーション分析ロジック
  - `apps/investment-tracker/pages/valuation.py` - Streamlitページ（分析結果表示）

## 実装手順

### Step 1: データアクセス層の実装
**ファイル**: `apps/investment-tracker/valuation_analysis.py`

```python
# 主要関数
def load_jquants_data():
    """J-Quantsデータ読み込み"""

def get_latest_financials(code, reference_date):
    """最新の財務データ取得"""

def get_price_history(code, days=100):
    """株価履歴取得（移動平均用）"""
```

### Step 2: 各分析関数の実装
**ファイル**: `apps/investment-tracker/valuation_analysis.py`

```python
def calculate_peg_ratio(code, reference_date):
    """PEG Ratio計算"""

def calculate_ma_divergence(code):
    """移動平均乖離率計算"""

def calculate_ev_ebitda(code, reference_date):
    """EV/EBITDA（簡易版）計算"""

def calculate_dcf_proxy(code, reference_date, wacc=0.10):
    """DCF Proxy（簡易版）計算"""

def analyze_stock(code, reference_date=None):
    """全分析を統合実行"""
    return {
        'code': code,
        'peg_ratio': {...},
        'ma_divergence': {...},
        'ev_ebitda': {...},
        'dcf_proxy': {...},
        'overall_signal': 'BUY'/'HOLD'/'SELL'
    }
```

### Step 3: Streamlit UI統合
**ファイル**: `apps/investment-tracker/pages/valuation.py`

- 持ち株リスト（`hypotheses.json`）を読み込み
- 各銘柄に対して `analyze_stock()` を実行
- 結果を表形式で表示
- 各指標のシグナル（🟢買い、🟡保持、🔴売り）を視覚化

### Step 4: メインアプリへの統合
**ファイル**: `apps/investment-tracker/app.py`

- サイドバーに「バリュエーション分析」リンクを追加
- ページ遷移の設定

## データ更新頻度
- **財務データ**: 四半期ごと（手動更新 or API連携）
- **株価データ**: 日次（移動平均計算用）

## 制約事項
1. **EV/EBITDA**: EBITDAデータなし → 営業利益で代用
2. **DCF Proxy**: WACC固定（10%）、成長率仮定なし（保守的）
3. **データ遅延**: J-Quantsデータは決算発表後に反映（リアルタイムではない）

## 成功基準
- [ ] 4つの分析がすべて実行可能
- [ ] 持ち株リストから自動で銘柄コードを取得
- [ ] 各指標のシグナル（買い/保持/売り）が明確
- [ ] Streamlit UIで結果が視覚的に確認可能
- [ ] エラーハンドリング（データ欠損時の対応）

## 次のステップ（実装後）
1. バックテスト: 過去の分析シグナルの精度検証
2. アラート機能: シグナル変化時の通知
3. レポート出力: PDF/CSV形式でのエクスポート

## 参照
- `analyses/20260415_1100_op_valuation_all_stocks/` - 営業利益×10手法の実装
- `analyses/20260415_1300_fcf_valuation/` - FCF手法の実装
- `docs/knowledges/20260319_0000_adjusted_price_validation.md` - 調整済み株価の正しい計算方法
