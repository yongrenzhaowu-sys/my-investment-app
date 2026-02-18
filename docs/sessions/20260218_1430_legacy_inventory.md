# セッションサマリー：legacy/projects 棚卸し

**日時**: 2026-02-18 14:30～15:00
**所要時間**: 約30分
**作業者**: Claude Code + User

---

## やったこと

### 1. 事前準備
- ユーザーに確認事項を質問（3問、選択肢付き）
  - 棚卸しの深さ：メタデータ＋主要ファイルのみ詳細分析
  - 優先基準：ファイル名から推定される機能
  - status判定：自動判定
- 棚卸し計画を `docs/plans/20260218_1430_legacy_inventory/01_first_plan.md` に保存

### 2. メタデータ収集
- legacy/projects 配下の全90ファイルをスキャン
  - ファイル数：90個（全て.ipynb、.pyは0件）
  - 総サイズ：約19.3MB
  - 更新期間：2025-12-03 ～ 2026-02-17
- ファイル名パターンから6カテゴリに分類
  - FF5系（12件）
  - 四半期系（28件）
  - 月足系（7件）
  - ロングオンリー系（9件）
  - データ取得系（8件）
  - その他（26件）

### 3. 再利用候補トップ20抽出
- キーワード優先（バックテスト、モデル、完成、最終等）+ サイズ + 更新日
- 代表ファイル：
  - 最大サイズ：`四半期バックテスト12月28日.ipynb` (1.3MB)
  - 最新：`PBR_ROE_Monthly_Backtest.ipynb` (2026-02-17)
  - 最重要：`FF5モデル1月23日作業中.ipynb` (995KB、2026-02-08)

### 4. 詳細分析（代表ファイル）
- `FF5バックテスト最終稿.ipynb` を読み込んで共通パターンを確認
  - 依存：pandas, numpy, pyarrow, pathlib, glob
  - 処理フロー：データ読み込み → ポート形成 → バックテスト → パフォーマンス計算
  - リスクオフロジック：市場DD -13.5%、3Mトレンド -2%、3Mボラ90%ile
  - バックテスト結果：年率26.69%、Sharpe 1.99、MDD -14.28%

### 5. status判定（自動）
- **keep（6件）**: 2026年1月以降更新 + 大容量 + 現役
- **refactor（8件）**: 2025年12月更新 + 中容量 + 有用ロジック含む
- **archive（6件）**: 古い or 実験的

### 6. 移植先提案
- **src/**: データ取得、リスク管理、フィルター、ファクター計算等の汎用モジュール
- **scripts/**: バックテスト実行、最適化等の単発スクリプト
- **analyses/**: FF5モデル、四半期レバレッジ等の分析プロジェクト

### 7. 成果物作成
- `docs/knowledges/legacy_inventory.md` にカタログを保存
  - プロジェクトカテゴリ一覧（6カテゴリ）
  - 再利用候補トップ20（status + 移植先提案付き）
  - 詳細分析結果
  - 次のアクション（優先度付き）

---

## 決めたこと

### 棚卸し方針
1. **legacy/projects は原本として保管**
   - 編集・移動・削除しない（CLAUDE.md に明記済み）
   - 必要なファイルのみ analyses/ や src/ に移植

2. **再利用の優先順位**
   - 優先度1：keep候補6件を analyses/ に即移植
   - 優先度2：refactor候補8件から汎用モジュールを抽出
   - 優先度3：archive候補6件は参照用に保管

3. **移植フォーマット**
   - analyses/ は `{YYYYMMDD_HHMM}_{topic}/` 単位
   - idea_XX.md（計画/仮説） + analysis_XX.ipynb（実装）の1:1対応

### status判定基準
- **keep**: 最新（2026/1以降） + 大容量（100KB+） + ファイル名に「モデル」「作業中」
- **refactor**: やや古い（2025/12） + 中容量（300KB+） + ファイル名に「完成」「レバ」「最適化」
- **archive**: 古い（2025/12以前） or 小容量（350KB未満） + 実験的

---

## 次にやること

### 即実施推奨（優先度1）
1. **keep候補6件を analyses/ に移植**
   ```
   - FF5モデル1月23日作業中.ipynb → analyses/20260218_xxxx_ff5_model/
   - FF5モデル1月20日作業中.ipynb → 同上
   - FF5モデル1月25日作業中.ipynb → 同上
   - 全上場企業日足4本値取得.ipynb → src/data/fetch_daily_prices.py
   - 1月29日作業中.ipynb → analyses/20260218_xxxx_latest_work/
   - 1月21日作業中.ipynb → 同上
   ```

2. **データ取得モジュールを src/ に抽出**
   - `src/data/fetch_daily_prices.py`: J-Quants API経由でデータ取得
   - エラーハンドリング、キャッシュ機能を含む

### 中期実施（優先度2）
3. **refactor候補8件から汎用モジュールを src/ に抽出**
   ```
   - src/risk/crash_detection.py: 暴落検知ロジック
   - src/risk/market_regime.py: リスクオフ判定
   - src/filters/volatility_filter.py: ボラティリティフィルター
   - src/features/factor_scoring.py: ファクターZスコア計算
   ```

4. **バックテストスクリプトを scripts/ に整備**
   ```
   - scripts/backtest_quarterly_growth.py: 四半期成長率バックテスト
   - scripts/optimize_start_month.py: リバランス月最適化
   ```

### 参照用（優先度3）
5. **archive候補は legacy/projects にそのまま保管**
   - 必要に応じて docs/knowledges/ に知見を抽出

---

## 重要なパス/コマンド

### 作成したファイル
```bash
# 棚卸し計画
docs/plans/20260218_1430_legacy_inventory/01_first_plan.md

# 棚卸しカタログ（成果物）
docs/knowledges/legacy_inventory.md

# 作業サマリ（本ファイル）
docs/sessions/20260218_1430_legacy_inventory.md
```

### legacy/projects の構造確認
```bash
# ファイル一覧（サイズ・更新日付き）
cd "C:\Users\yongr\claude project\workspace\legacy\projects"
find . -name "*.ipynb" -type f -printf "%s\t%TY-%Tm-%Td\t%p\n" | sort -k2 -r

# カテゴリ別ファイル数
ls -1 | wc -l  # 総ファイル数
ls -1 *FF5* | wc -l  # FF5系
ls -1 *四半期* | wc -l  # 四半期系
```

### 次回移植時のコマンド例
```bash
# analyses/配下に新規プロジェクト作成
mkdir -p "analyses/20260218_1500_ff5_model"

# legacy/projects から参照のみ（コピーは手動で確認後）
# ⚠️ 移動・削除は禁止、コピーのみ
```

---

## 📊 統計サマリ

| 項目 | 数値 |
|------|------|
| 総ファイル数 | 90個 |
| 総サイズ | 19.3MB |
| 最大ファイル | 四半期バックテスト12月28日.ipynb (1.3MB) |
| 最新ファイル | PBR_ROE_Monthly_Backtest.ipynb (2026-02-17) |
| トップ20抽出 | 20個 |
| keep候補 | 6個 |
| refactor候補 | 8個 |
| archive候補 | 6個 |
| プロジェクトカテゴリ | 6種類 |

---

## 学んだこと・注意点

### 共通パターン
- **依存**: pandas, numpy, pyarrow が共通（バージョン統一済み）
- **データパス**: `C:\Users\yongr\Project\merged_data_all_stocks` を共通使用
- **バックテスト仮定**: t日引け確定 → t+1日寄り約定（未来参照なし）
- **リスクオフロジック**: 市場DD、3Mトレンド、3Mボラティリティの3指標

### 命名規則の問題
- 日付ベース（12月18日作業中）とテーマベース（FF5モデル）が混在
- 「作業中」「その２」「その３」等の増分命名が多い
- **改善案**: analyses/ 移植時に統一フォーマット適用
  - `analyses/{YYYYMMDD_HHMM}_{topic}/idea_XX.md + analysis_XX.ipynb`

### 環境の制約
- Windows環境でjq、Python直接実行が不可
- ipynbの大容量ファイル（>256KB）は直接読み込み不可
- → メタデータ + 代表ファイルのみ詳細分析でカバー

---

**次回セッション予定**: keep候補6件の移植作業
**推定所要時間**: 60分
