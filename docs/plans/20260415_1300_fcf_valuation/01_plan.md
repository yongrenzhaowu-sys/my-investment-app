# 現金+FCF×10バリュエーション検証

## 検証目的

「現金 + FCF×10」バリュエーション手法が、「営業利益×10」手法と比較して有効かを検証する。

## バリュエーション手法

### 現金+FCF×10

```
理論的価値 = 現金 + (FCF × 10)

FCF (Free Cash Flow) = 営業CF - 投資CF
現金 = 現金及び現金同等物
```

### 割安度スコア

```
割安度スコア = (理論的価値 - 時価総額) / 時価総額
```

### 営業利益×10との違い

| 項目 | 現金+FCF×10 | 営業利益×10 |
|-----|-----------|-----------|
| **ベース** | キャッシュフロー（C/F） | 損益（P/L） |
| **評価対象** | 現金創出力 | 本業の収益力 |
| **安定性** | 低い（投資タイミングで変動） | 高い |
| **会計操作** | 影響小 | 影響中 |
| **成長企業** | 不利（FCFマイナス） | 有利 |

## データソース

### J-Quants API財務データ

- **CFO**: 営業キャッシュフロー（Operating Cash Flow）
- **CFI**: 投資キャッシュフロー（Investing Cash Flow）
- **CashEq**: 現金及び現金同等物（Cash and Cash Equivalents）

### データ確認項目

1. CFO, CFI, CashEq列が存在するか
2. データの欠損率
3. 数値の妥当性（極端な値がないか）

## スクリーニング条件

### 基本条件（営業利益×10と同様）

1. 時価総額 > 100億円
2. 自己資本比率 > 20%
3. 株式併合銘柄を除外

### FCF特有の条件

4. **FCF > 0**（必須）
   - FCFがマイナスの企業は除外
   - 理由: FCFマイナス = キャッシュを消費している

5. **現金 > 0**
   - 現金データが欠損している企業は除外

6. **FCF増加基調**（オプション）
   - 直近3年でFCFが増加傾向
   - または、直近FCFが過去平均を上回る

## バックテスト設計

### 対象

- **時価総額グループ**: 中型株（25.5億円～144.5億円）
- **銘柄数**: 上位10銘柄
- **期間**: 2022-2025年（4年間）
- **リバランス**: 年次（毎年4月）

### 比較対象

1. **現金+FCF×10戦略**（今回検証）
2. **営業利益×10戦略**（前回分析）
3. **ベンチマーク**: TOPIX、日経225

### 評価指標

- 累積リターン
- 年率リターン（CAGR）
- シャープレシオ
- 最大ドローダウン
- 勝率

## 期待される発見

### 仮説1: FCFの方が安定性が低い

- FCFは投資タイミングで大きく変動
- 営業利益の方が安定的

### 仮説2: 成長企業を除外してしまう

- FCF > 0の条件で、成長企業が除外される
- 結果として、低成長・高配当銘柄に偏る

### 仮説3: 財務安全性が高い銘柄を選定

- 現金を考慮するため、財務安全性が高い
- 下落相場で強い可能性

## 実装ステップ

### Step 1: データ確認

```python
# CFO, CFI, CashEq列の確認
financials[['Code', 'CFO', 'CFI', 'CashEq']].head()

# 欠損率
financials[['CFO', 'CFI', 'CashEq']].isnull().mean()
```

### Step 2: FCF計算

```python
# FCF = CFO - CFI
financials['FCF'] = financials['CFO'] - financials['CFI']

# FCF > 0でフィルタ
financials = financials[financials['FCF'] > 0]
```

### Step 3: 理論的価値計算

```python
# 理論的価値 = 現金 + FCF×10
financials['TheoreticalValue'] = financials['CashEq'] + financials['FCF'] * 10

# 割安度スコア
financials['ValuationGap'] = (
    (financials['TheoreticalValue'] - market_cap) / market_cap
)
```

### Step 4: スクリーニング

```python
# 割安度スコア上位10銘柄
top_stocks = financials.nlargest(10, 'ValuationGap')
```

### Step 5: バックテスト

- 営業利益×10と同じロジック
- 年次リバランス、4年間

### Step 6: 比較

```python
# パフォーマンス比較
comparison_df = pd.DataFrame({
    '手法': ['現金+FCF×10', '営業利益×10'],
    'CAGR': [fcf_cagr, op_cagr],
    'シャープレシオ': [fcf_sharpe, op_sharpe],
    '最大DD': [fcf_dd, op_dd],
})
```

## 注意事項

### 🚨 データ品質

J-Quants APIのCFデータは不完全な可能性：
- CFO, CFI, CashEq列が存在しない
- データの欠損率が高い
- 数値の妥当性に問題がある

→ データ確認を最優先

### 🚨 ルックアヘッドバイアス防止

- 各年3月末時点で公開済みのCFデータのみ使用
- CFデータは決算発表日以降のみ利用可能

### 🚨 調整済み株価

- `AdjC_Correct = C × AdjFactor`を使用
- 株式併合銘柄を除外

## 成果物

### コード

- `analyses/20260415_1300_fcf_valuation/screening_fcf.py`
- `analyses/20260415_1300_fcf_valuation/backtest_fcf.py`
- `analyses/20260415_1300_fcf_valuation/compare_fcf_vs_op.py`

### 結果ファイル

- `screening_results_fcf_20260331.csv`: FCF手法の選定銘柄
- `backtest_results_fcf.csv`: FCF手法のバックテスト結果
- `comparison_fcf_vs_op.csv`: FCF vs 営業利益の比較

### ドキュメント

- `results.md`: 結果サマリー
- `docs/knowledges/20260415_1300_fcf_valuation_method.md`: FCF手法の知見

## スケジュール

1. **データ確認**: 5分
2. **FCF計算・スクリーニング**: 10分
3. **バックテスト実装**: 10分
4. **比較分析**: 10分
5. **ドキュメント作成**: 5分

**合計**: 約40分
