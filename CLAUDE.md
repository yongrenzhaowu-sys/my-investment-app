# Workspace Constitution (Claude Code must follow)

## Language
- 日本語で回答する（私が英語指定した場合のみ英語）。

## Do NOT use Plan mode
- Claude Code標準のPlan modeは使わない。
- 代わりに、作業計画は必ず docs/plans 配下にMarkdownで保存する。

## Output locations (must write files)
### Plans
- docs/plans/{YYYYMMDD_HHMM}_{topic}/01_first_plan.md
- 追加/変更は docs/plans/{同フォルダ}/02_{short_title}.md, 03_... のように増分で保存

### Session summaries
- ひと段落ごとに docs/sessions/{YYYYMMDD_HHMM}_{summary}.md に
  「やったこと」「決めたこと」「次にやること」「重要なパス/コマンド」を要約して保存

### Knowledge base (context control)
- 再利用できる知見（データ定義、前処理ルール、バックテスト仮定、命名規則、注意点）は docs/knowledges/ にMarkdownで蓄積
- 参照が必要な場合は docs/knowledges/ を最優先で確認し、他フォルダの広範囲スキャンは必要時のみ（事前に理由と範囲を宣言）

## Naming conventions
- analyses/{YYYYMMDD_HHMM}_{topic}/ を分析プロジェクトの単位とする
- idea_XX.md（計画/仮説）と analysis_XX.ipynb（実装）は1:1対応

## Legacy files (read-only)
- legacy/projects/ 配下は原本として扱う
- 編集・移動・削除は禁止（参照のみ）

## Default trading assumption (JP equities swing)
- デフォルト：t日「引け」でシグナル確定 → t+1日「寄り」で売買（約定）
- 未来参照（lookahead）を禁止：t時点の特徴量は t+1 以降を参照しない
- 作業開始前に「今回作る plan/sessions/knowledges のファイルパス」を最初に宣言してから作業すること。

## 🚨 Lookahead bias prevention (CRITICAL)
**背景**: 2026-02-25にルックアヘッドバイアスにより年率リターンが2.7倍（+35.17%）に水増しされていた事例を発見。バイアスチェックは最優先事項。

### 必須チェック項目（バックテスト実装時）

#### 1. データの利用可能性
**必ず問う**: 「この時点で、このデータは本当に利用可能か？」

```python
# ❌ 間違い: その月の決算データを月初に使用
disclosed_this_month = df[df['year_month'] == current_month]
latest_data = disclosed_this_month.groupby('code').last()
entry_date = current_month_start  # ← 決算発表より前！

# ✅ 正しい: 月初時点で利用可能なデータのみ
available_data = df[df['disclosed_date'] < current_month_start]
latest_data = available_data.groupby('code').last()
entry_date = current_month_start
```

#### 2. 実務での実行可能性
**必ず問う**: 「実務で同じ操作ができるか？」

- 決算発表日当日に決算データを使って購入 → ❌ 不可能（翌営業日のみ可能）
- t日終値でシグナル → t日終値で購入 → ❌ 不可能（t+1日のみ可能）
- その月の全データで四分位計算 → 月初にエントリー → ❌ 未来参照

#### 3. 典型的なバイアスパターン

**パターン1: 同時点データの使用**
```python
# ❌ t日終値でシグナル → t日終値で購入
signal = df[df['date'] == today]
entry_price = df.loc[today, 'close']

# ✅ t日終値でシグナル → t+1日始値で購入
signal = df[df['date'] == today]
entry_price = df.loc[tomorrow, 'open']
```

**パターン2: 全期間データでの統計計算**
```python
# ❌ 全期間で四分位計算
df['quartile'] = pd.qcut(df['value'], q=4)
selected = df[(df['date'] == today) & (df['quartile'] == 'Q1')]

# ✅ その時点で利用可能なデータのみで計算
available = df[df['date'] <= today]
available['quartile'] = pd.qcut(available['value'], q=4)
selected = available[available['date'] == today]
```

**パターン3: イベント日のデータ使用**
```python
# ❌ 決算発表月のデータで月初にスクリーニング
disclosed_this_month = df[df['year_month'] == current_month]
entry_date = month_start

# ✅ 月初より前のデータのみでスクリーニング
available_data = df[df['disclosed_date'] < month_start]
entry_date = month_start
```

### バックテスト実装の標準フロー

1. **計画段階**
   - [ ] タイミング図を作成（いつ何のデータが利用可能か）
   - [ ] データの利用可能性を明示

2. **実装段階**
   - [ ] `available_data = df[df['date'] < decision_time]` パターンを徹底
   - [ ] 各時点ごとに四分位・ランキングを再計算
   - [ ] コメントでタイミングを明記

3. **検証段階**
   - [ ] 最初の数ヶ月を手動で確認
   - [ ] 「この時点で、このデータは利用可能か？」を各ステップで確認
   - [ ] 「実務で同じ操作ができるか？」を確認

4. **ドキュメント段階**
   - [ ] タイミングを明記（「t日終値でシグナル → t+1日始値でエントリー」など）
   - [ ] 未来参照がないことを明示
   - [ ] 検証方法を記録

### 参考資料
- `docs/knowledges/20260225_1900_lookahead_bias_correction.md`: 詳細なチェックリストと事例
- `docs/knowledges/20260222_0300_lookahead_bias_prevention.md`: 過去の教訓

## Daily automation (RSS-driven analysis)
### Workflow priority
- **docs中心の運用**：作業の記憶を外部化する
  - まず docs/knowledges と直近 docs/reports を優先参照
  - 成果物は必ず docs/ と analyses/ に保存
  - Plan mode標準保存に頼らず、docs/plans と docs/sessions に必ず保存

### Data locations
- **data/raw/**：外部ソースの生データ（RSS、J-Quants APIレスポンス等）
  - data/raw/rss/{YYYYMMDD}/*.json
  - data/raw/jquants/{YYYYMMDD}/*.json
- **data/processed/**：前処理済みデータ
- **analyses/00_to_be_started/**：アイデアキュー（ideas.jsonl）
- **analyses/{YYYYMMDD_HHMM}_{topic}/**：個別分析プロジェクト

### Security and safety
- **秘密情報はWindows環境変数のみ**
  - リポジトリに .env を置かない
  - .env.example（値なし）は作成OK
  - os.environ から読み、値を絶対にprintしない
- **危険フラグ原則禁止**
  - --dangerously-skip-permissions 等は使わない
  - 必要な操作は最小権限・確認ベース
- **npm系は使わない**
  - Pythonのみで完結させる

### Output requirements
- **docs/knowledges/{YYYYMMDD_HHMM}_{topic}.md**：必須
  - 成功・失敗問わず、全ての分析から学びを抽出
- **docs/reports/{YYYYMMDD}.md**：日次レポート必須
  - RSS取得件数、処理件数、成功/失敗、主要結果、明日のTODO
- **analyses/{YYYYMMDD_HHMM}_{topic}/idea_01.md**：アイデア計画
- **analyses/{YYYYMMDD_HHMM}_{topic}/backtest_metrics.json**：機械可読な結果

### Data sources
- **RSSのみ**：外部ソースはRSSフィードのみ
  - Webスクレイピングは追加しない
  - RSS解析不可ならスキップ（無理に取得しない）
- **J-Quants API**：日本株データ取得
  - キャッシュ優先（data/raw/jquants/）
  - 同日再実行でAPIを叩き直さない
