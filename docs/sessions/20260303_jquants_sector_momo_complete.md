# セッション記録: J-Quants Sector Momentum プロジェクト完全生成

**日時:** 2026-03-03
**作業内容:** J-Quants API V2を使用したセクターモメンタム戦略の完全実装

---

## やったこと

### 1. プロジェクト構造作成
- `jquants-sector-momo/` ディレクトリ構造を作成
- 以下のファイルを実装:
  - `requirements.txt`: 依存パッケージ定義
  - `run_pipeline.py`: メインパイプライン
  - `src/momo/providers/jquants_provider.py`: J-Quants APIクライアント
  - `src/momo/strategies/sector_momentum.py`: モメンタム戦略ロジック
  - `src/momo/utils/sector33.py`: 33業種マッピング
  - `src/momo/utils/risk.py`: ポジションサイジング
  - `src/momo/utils/reporting.py`: レポート生成
  - `src/momo/utils/anthropic_client.py`: Claude連携

### 2. 主要機能実装
- **データ取得**: J-Quants API V2から調整済み四本値（AdjO/AdjH/AdjL/AdjC/AdjVo）取得
- **特徴量計算**: Ret_5/10/20, SMA20, VolRatio, ATR14, Volatility20等
- **フィルタリング**: 流動性、出来高、トレンド条件
- **スコアリング**: robust z-score（中央値/IQR）で合成
- **セクターランキング**: 33業種別に平均スコア・breadth計算
- **銘柄選択**: 上位セクターから推奨銘柄20を抽出
- **ポジションサイジング**: ボラティリティ逆相関ウェイト
- **レポート生成**: JSON + Markdown（ディスクレーマー付き）
- **Claude解説**: オプションで条件付き解説を追加

### 3. セキュリティ対応
- Windows環境変数からAPIキー読み込み（`.env`は使用しない）
- データ配布禁止に配慮（推奨銘柄のみ保存）

---

## 決めたこと

### データソース
- J-Quants API V2の `get_price_range` で日次バー取得
- 調整済み列（AdjustmentOpen/High/Low/Close/Volume）を優先
- 列がない場合は `AdjustmentFactor` でフォールバック計算

### 戦略パラメータ
- モメンタム期間: 5/10/20日
- ATR期間: 14日
- ボラティリティ: 20日
- スコア重み: Ret5(40%) / Ret10(35%) / Ret20(15%) / VolRatio(10%)

### フィルタ条件
- 最低価格: 200円
- 最低流動性: 30M円/日
- 最低出来高比率: 1.1
- トレンド: AdjC >= SMA20

### ポジションサイジング
- 総エクスポージャー: 100%
- 最小ウェイト: 2%
- 最大ウェイト: 8%
- リスク指標: Volatility20（またはATR/Close）

---

## 次にやること

### ユーザー側で実施
1. **環境変数設定**
   - `JQUANTS_REFRESH_TOKEN` または `JQUANTS_MAIL_ADDRESS` + `JQUANTS_PASSWORD`
   - `ANTHROPIC_API_KEY` (Claude解説使用時)

2. **依存パッケージインストール**
   ```powershell
   cd jquants-sector-momo
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **実行**
   ```powershell
   python run_pipeline.py --days 400 --top-sectors 5 --top-stocks 20
   ```

### 拡張候補
- バックテスト機能追加
- 日次自動実行スケジューラー
- ダッシュボード（Streamlit/Dash）
- 複数戦略の比較
- リバランス通知機能

---

## 重要なパス/コマンド

### ファイルパス
- メインスクリプト: `jquants-sector-momo/run_pipeline.py`
- 戦略ロジック: `jquants-sector-momo/src/momo/strategies/sector_momentum.py`
- レポート出力: `jquants-sector-momo/reports/report_latest.json`, `report_latest.md`

### 実行コマンド例
```powershell
# 基本実行
python run_pipeline.py

# プライム市場のみ、Claude解説付き
python run_pipeline.py --prime-only --use-claude --days 600

# 基準日指定
python run_pipeline.py --asof 2024-12-31 --top-stocks 30
```

### トラブルシューティング
- J-Quants認証エラー → 環境変数を確認
- 調整済み列エラー → J-Quantsプラン確認、AdjustmentFactor使用
- Claude解説エラー → `ANTHROPIC_API_KEY` 確認、`--use-claude` を外す

---

## 備考

- **ルックアヘッドバイアス防止**: `asof_date`時点で利用可能なデータのみ使用
- **投資助言ではない**: レポートにディスクレーマー必須
- **データ配布禁止**: 推奨銘柄のみ保存（全銘柄時系列は保存しない）
- **Windows専用**: 環境変数を使用（`.env`ファイルは不使用）
