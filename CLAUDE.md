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
