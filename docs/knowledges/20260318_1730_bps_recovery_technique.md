# BPS代替計算テクニック

**作成日**: 2026-03-18 18:00
**カテゴリ**: データ処理、欠損値補完
**関連プロジェクト**: FF5ファクターモデル

---

## 問題

### BPS（1株あたり純資産）の欠損が銘柄カバレッジを大幅に制限

**発見**:
- J-Quants APIの財務データで、BPS（Book value Per Share）が欠損している銘柄が多い
- 18,719レコード中、BPS有効は6,640レコード（35.5%のみ）
- MarketCap計算（`MarketCap = Price * (Eq / BPS)`）でBPSが必須のため、多くの銘柄が除外される

**影響**:
- FF5ファクター計算の対象銘柄数が約1,000銘柄に制限された（日本株全体の約20%）
- 統計的検出力が不足し、ファクターリターンの精度が低下

---

## 解決策

### BPS代替計算: 発行済株式数データを活用

**原理**:
```
BPS = Equity（自己資本） / Shares Outstanding（発行済株式数）
```

**実装**:
```python
# 発行済株式数（優先順位: ShOutFY > TrShFY > AvgSh）
df_fins['SharesOut'] = df_fins['ShOutFY'].fillna(df_fins['TrShFY']).fillna(df_fins['AvgSh'])

# BPS計算（Eq / 発行済株式数）
df_fins['BPS_Calc'] = df_fins['Eq'] / df_fins['SharesOut']

# BPS最終値（元のBPSがあればそれを、なければ計算値を使用）
df_fins['BPS_Final'] = df_fins['BPS'].fillna(df_fins['BPS_Calc'])
```

**データソース**:
- `ShOutFY`: 会計年度末の発行済株式数（優先）
- `TrShFY`: 会計年度末の発行済株式数（代替）
- `AvgSh`: 平均発行済株式数（最終代替）

---

## 結果

### 銘柄カバレッジが3.5倍に増加

| 指標 | 前回 | 今回 | 改善率 |
|------|------|------|--------|
| **BPS有効数** | 6,640 | **16,267** | **+245%** |
| **対象銘柄数（月平均）** | ~1,000 | **~3,500** | **+350%** |
| **INV_Growth有効数（月平均）** | ~780 | **~3,000** | **+385%** |

### 復活率
- BPS欠損銘柄: 12,079レコード
- 発行済株式数データで復活: **9,627レコード**（79.7%）
- 復活後のBPS有効数: **16,267レコード**（86.9%）

---

## 適用条件

### このテクニックが有効なケース

1. **BPSが欠損しているが、自己資本（Eq）と発行済株式数（ShOutFY等）は利用可能**
   - J-Quants APIではこのケースが多い
   - 財務データの列によって提供状況が異なる

2. **MarketCap計算にBPSが必須**
   - `MarketCap = Price * (Eq / BPS)` の形式
   - BPS欠損時に代替計算が必要

3. **時価総額の精度が重要**
   - ファクター計算（SMB、HML等）で時価総額が必須
   - 精度が低いと誤った銘柄選択につながる

---

## 注意点

### データ品質の確認

1. **発行済株式数の単位**
   - J-Quants APIでは「株」単位
   - データソースによっては「千株」や「百万株」の場合もあるので要確認

2. **異常値のチェック**
   ```python
   # BPS計算後に異常値を除外
   df_fins.loc[df_fins['BPS_Calc'] <= 0, 'BPS_Calc'] = np.nan
   df_fins.loc[df_fins['BPS_Calc'] > 10000, 'BPS_Calc'] = np.nan  # 例: 10,000円以上は異常
   ```

3. **元のBPSとの整合性確認**
   ```python
   # 元のBPSと計算したBPSの差分を確認
   df_check = df_fins[df_fins['BPS'].notna() & df_fins['BPS_Calc'].notna()].copy()
   df_check['BPS_Diff'] = (df_check['BPS_Calc'] - df_check['BPS']) / df_check['BPS']
   print(df_check['BPS_Diff'].describe())  # 差分が±10%以内なら妥当
   ```

---

## 応用例

### 他の財務指標への適用

**PER（株価収益率）の代替計算**:
```python
# PER = Price / EPS
# EPS = Net Income / Shares Outstanding
df['EPS_Calc'] = df['NP'] / df['SharesOut']
df['PER_Calc'] = df['Price'] / df['EPS_Calc']
```

**ROE（自己資本利益率）の代替計算**:
```python
# ROE = Net Income / Equity * 100
df['ROE'] = df['NP'] / df['Eq'] * 100
```

---

## 参考資料

- **セッション記録**: `docs/sessions/20260318_1730_bps_recovery_complete.md`
- **実装スクリプト**: `analyses/20260315_1600_jquants_latest_ff5/calculate_ff5_momentum_complete.py`
- **データソース**: J-Quants API V2 `/fins/summary`

---

## 教訓

1. **データの欠損は必ずしも利用不可能を意味しない**
   - 他の列から代替計算できる場合が多い
   - 基本的な財務関係式（BPS = Eq / Shares）を活用

2. **データ品質の段階的確認**
   - 元データ → 代替計算 → 異常値除外 → 最終値
   - 各段階で有効数を確認し、ボトルネックを特定

3. **ドキュメント化の重要性**
   - 代替計算のロジックを明記
   - 復活率、異常値除外の基準を記録
   - 再現性を確保

---

**このテクニックを使うことで、データ欠損による銘柄カバレッジの制限を大幅に緩和できます。**
