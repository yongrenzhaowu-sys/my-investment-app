# 複数バリュエーション手法の統合分析ガイド

**作成日**: 2026-04-15
**カテゴリ**: バリュエーション分析、投資判断支援
**関連**: 営業利益×10手法、FCF手法、PEG Ratio、移動平均分析

---

## 概要

個別銘柄のバリュエーション分析において、単一の指標だけでなく複数の異なる視点からの分析を組み合わせることで、より堅牢な投資判断が可能になる。

本ガイドでは、4つのバリュエーション手法を統合した分析フレームワークを提供する。

---

## 4つのバリュエーション手法

### 1. PEG Ratio（株価収益成長率）

#### 計算式
```python
PEG = PER / (成長率 × 100)
```

#### データ要件
- 純利益（NP）: 最新5期分以上
- 時価総額: 最新の株価×発行済株式数

#### 実装上の注意点
```python
# 成長率はCAGRで計算
years = len(np_values) - 1
growth_rate = (np_values[-1] / np_values[0]) ** (1 / years) - 1

# 成長率がマイナスまたはゼロの場合はPEG計算不可
if growth_rate <= 0:
    return {'error': '成長率マイナス'}
```

#### 判定基準
- **PEG < 1.0**: 🟢 BUY（成長性に対して株価が低い）
- **PEG 1.0-2.0**: 🟡 HOLD（適正）
- **PEG > 2.0**: 🔴 SELL（割高）

#### 有効性
- グロース株の評価に適している
- 成長率が安定している企業で精度が高い
- 成長率がマイナスやゼロの企業には適用不可

---

### 2. Moving Average Divergence（移動平均乖離）

#### 計算対象
- **短期**: 25日移動平均線（MA_25）
- **中期**: 75日移動平均線（MA_75）

#### データ要件
- 日次株価データ: 最低75日分以上（バッファ含め100日推奨）

#### 実装上の注意点
```python
# 移動平均計算
price_history['MA_25'] = price_history['Price'].rolling(window=25).mean()
price_history['MA_75'] = price_history['Price'].rolling(window=75).mean()

# ゴールデンクロス/デッドクロス判定
# 直近2日分でクロスを判定
prev_ma_25 < prev_ma_75 and ma_25 > ma_75  # ゴールデンクロス
prev_ma_25 > prev_ma_75 and ma_25 < ma_75  # デッドクロス
```

#### 判定基準
- **ゴールデンクロス**（25日MAが75日MAを上抜け）: 🟢 BUY
- **デッドクロス**（25日MAが75日MAを下抜け）: 🔴 SELL
- **現在価格が両MAより上**: 🟡 HOLD（強気トレンド）
- **現在価格が両MAより下**: 🔴 SELL（弱気トレンド）

#### 有効性
- トレンド判定に有効
- テクニカル分析の基本指標
- ファンダメンタルズとの組み合わせで精度向上

---

### 3. EV/EBITDA（簡易版）

#### 計算式
```python
EV = 時価総額 + 純負債
純負債 = (総資産 - 自己資本) - 現金
EBITDA ≈ 営業利益（OP）  # 簡易版
```

#### データ要件（J-Quantsの場合）
- 営業利益（OP）: EBITDAの代用
- 総資産（TA）、自己資本（Eq）、現金（CashEq）
- 時価総額

#### 実装上の注意点
```python
# 純負債計算
total_debt = ta - eq
net_debt = total_debt - cash_eq if not pd.isna(cash_eq) else total_debt

# EV計算
ev = market_cap + net_debt

# CRITICAL: J-QuantsにはEBITDAデータがない
# → 営業利益（OP）で代用
ebitda = op
```

#### 判定基準
- **EV/EBITDA < 10**: 🟢 BUY（割安）
- **EV/EBITDA 10-15**: 🟡 HOLD（適正）
- **EV/EBITDA > 15**: 🔴 SELL（割高）

#### 制約事項
- EBITDAデータがないため営業利益で代用
- 減価償却費の多い業種では実際のEBITDAと乖離
- 異常値が発生する可能性あり（例: EV/EBITDA 445.4）

---

### 4. DCF Proxy（簡易版）

#### 計算式
```python
FCF = CFO - CFI
理論企業価値 = FCF / WACC
理論株価 = 理論企業価値 / 発行済株式数
```

#### データ要件
- 営業CF（CFO）、投資CF（CFI）
- 時価総額、株価
- WACC（固定値: 10%と仮定）

#### 実装上の注意点
```python
# CRITICAL: CFデータの欠損率が高い（約56%）
cfo = pd.to_numeric(latest_fin['CFO'], errors='coerce')
cfi = pd.to_numeric(latest_fin['CFI'], errors='coerce')

if pd.isna(cfo) or pd.isna(cfi):
    return {'error': 'キャッシュフローデータ欠損'}

# FCF計算
fcf = cfo - cfi

# FCFがマイナスの場合は計算不可
if fcf <= 0:
    return {'error': 'FCFマイナス'}

# WACC固定（簡易版）
wacc = 0.10  # 10%

# 発行済株式数（簡易推定）
shares_outstanding = latest_price['Vo'] * 100
```

#### 判定基準
- **株価/理論株価 < 0.8**: 🟢 BUY（割安）
- **株価/理論株価 0.8-1.2**: 🟡 HOLD（適正）
- **株価/理論株価 > 1.2**: 🔴 SELL（割高）

#### 制約事項
- **CFデータ欠損率が高い**（約56%）→ 計算不可の銘柄が多い
- WACC固定（10%）→ 業種・企業の実態と乖離
- 成長率を考慮していない（保守的な評価）

---

## 総合シグナル判定ロジック

### 実装
```python
def calculate_overall_signal(signals):
    """
    4つの指標のシグナルを多数決で判定

    Args:
        signals: [peg_signal, ma_signal, ev_signal, dcf_signal]

    Returns:
        'BUY'/'HOLD'/'SELL'/None
    """
    # Noneを除外
    valid_signals = [s for s in signals if s is not None]

    if len(valid_signals) == 0:
        return None

    # BUY/HOLD/SELLの数を集計
    buy_count = valid_signals.count('BUY')
    sell_count = valid_signals.count('SELL')
    hold_count = valid_signals.count('HOLD')

    # 多数決
    if buy_count > sell_count and buy_count >= hold_count:
        return 'BUY'
    elif sell_count > buy_count and sell_count >= hold_count:
        return 'SELL'
    else:
        return 'HOLD'
```

### 判定例
| PEG | MA | EV/EBITDA | DCF | 総合判定 |
|-----|----|-----------|----|---------|
| BUY | BUY | HOLD | SELL | BUY (2票) |
| BUY | SELL | SELL | None | SELL (2票 vs 1票) |
| HOLD | HOLD | HOLD | HOLD | HOLD (4票) |
| BUY | None | None | None | BUY (1票) |

---

## データ品質と制約

### J-Quantsデータの制約

#### 1. CFデータ欠損率が高い
- **欠損率**: 約56%（FCF分析時に確認）
- **影響**: DCF Proxy計算不可の銘柄が多い
- **対処**: エラーハンドリングで欠損を明示

#### 2. EBITDAデータがない
- **代用**: 営業利益（OP）を使用
- **影響**: 減価償却費の多い業種で乖離
- **対処**: 異常値の検出・除外

#### 3. 調整済み株価の計算（CRITICAL）
```python
# CRITICAL: AdjC列は調整されていない！
# 正しい調整済み株価の計算
if 'AdjFactor' in prices.columns:
    prices['Price'] = prices['C'] * prices['AdjFactor']
else:
    prices['Price'] = prices['C']
```

参照: `docs/knowledges/20260319_0000_adjusted_price_validation.md`

---

## 実装例

### ディレクトリ構成
```
apps/investment-tracker/
├── src/
│   ├── valuation_analysis.py    # バリュエーション分析モジュール
│   └── ...
├── pages/
│   ├── 3_Valuation.py            # Streamlitページ
│   └── ...
├── test_valuation.py             # テストスクリプト
└── ...
```

### 使用例
```python
from src.valuation_analysis import analyze_stock

# 銘柄分析
result = analyze_stock("62330")

# 結果
print(f"総合判定: {result['overall_signal']}")
print(f"PEG Ratio: {result['peg_ratio']}")
print(f"移動平均: {result['ma_divergence']}")
print(f"EV/EBITDA: {result['ev_ebitda']}")
print(f"DCF Proxy: {result['dcf_proxy']}")
```

---

## ベストプラクティス

### 1. 複数の視点を組み合わせる
- 単一の指標だけで判断しない
- ファンダメンタルズ（PEG、EV/EBITDA、DCF）とテクニカル（MA）の組み合わせ

### 2. データ品質を確認する
- エラーハンドリングで欠損を明示
- 異常値の検出・除外
- データの利用可能性を事前確認

### 3. 業種特性を考慮する
- EV/EBITDA: 減価償却費の多い業種では注意
- PEG: 成長率が安定している業種で有効
- DCF: CFが安定している業種で有効

### 4. 定期的な見直し
- 四半期ごとに財務データを更新
- 移動平均は日次で更新
- シグナル変化をトラッキング

---

## 今後の拡張

### 優先度: 高
1. **過去のシグナル精度検証**
   - バックテスト実施
   - シグナルの的中率計算

2. **データ品質改善**
   - CFデータ補完の検討
   - 異常値の自動検出・除外

### 優先度: 中
3. **アラート機能**
   - シグナル変化時の通知
   - 閾値超過時のアラート

4. **セクター別分析**
   - 業種平均との比較
   - 業種特性の考慮

### 優先度: 低
5. **レポート出力**
   - PDF/CSV形式でのエクスポート
   - 時系列変化の可視化

---

## 参照
- `docs/sessions/20260415_1400_holdings_valuation_system.md` - 実装セッション
- `docs/plans/20260415_1400_holdings_analysis/01_plan.md` - 実装計画
- `analyses/20260415_1100_op_valuation_all_stocks/` - 営業利益×10手法
- `analyses/20260415_1300_fcf_valuation/` - FCF手法
- `docs/knowledges/20260319_0000_adjusted_price_validation.md` - 調整済み株価検証
