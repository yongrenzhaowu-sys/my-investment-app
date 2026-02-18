# Claude Code 再開ガイド

**作成日**: 2026-02-18
**目的**: 安全にClaude Codeセッションを再開するための手順書

---

## 再開手順

### 1. 前回の作業内容を確認

```powershell
# workspaceに移動
cd "C:\Users\yongr\claude project\workspace"

# 最新のセッションログを確認
Get-ChildItem -Path .\docs\sessions\ -Filter *.md | Sort-Object LastWriteTime -Descending | Select-Object -First 3
```

### 2. Claude Codeを安全モードで起動

```powershell
# 安全な起動（パーミッション確認あり）
claude

# ❌ 非推奨: 危険な起動（使用禁止）
# claude --dangerously-skip-permissions
```

### 3. 最初のプロンプト

```
docs/sessions/ の最新ファイルを読んで、前回の続きから再開してください。
```

または、特定のセッションから再開する場合:

```
docs/sessions/20260218_1730_weekly_strategy_fix.md を読んで、前回の続きから再開してください。
```

---

## 安全運用ルール

### 原則1: パーミッションモードで運用
- ✅ `claude` のみで起動
- ❌ `--dangerously-skip-permissions` は使用禁止
- 理由: 全てのコマンド実行前に内容を確認できる

### 原則2: npm系コマンドは禁止
以下のコマンドは提案されても拒否:
- `npm install`
- `npm run`
- `npx`
- `yarn`
- `pnpm`
- `bun`

**理由**: Python中心の環境のため、Node.js関連は不要

**代替案**:
- パッケージ管理: `pip install`（Python）
- スクリプト実行: `python script.py`

### 原則3: コマンド実行前の確認
Claude Codeがコマンドを提案したら:
1. コマンドの内容を確認
2. 意図を理解
3. 安全性を判断
4. 問題なければ承認

**危険なコマンド例**:
- `rm -rf` / `Remove-Item -Recurse`（削除）
- `git push --force`（強制プッシュ）
- `npm install`（npm系）
- `curl ... | bash`（パイプ実行）

### 原則4: 秘密情報の管理
- ❌ `.env`ファイルに保存（Git誤コミットリスク）
- ✅ Windows環境変数に保存

**設定方法**:
```powershell
# システム環境変数に設定（管理者権限必要）
[System.Environment]::SetEnvironmentVariable("JQUANTS_EMAIL", "your@email.com", "User")
[System.Environment]::SetEnvironmentVariable("JQUANTS_PASSWORD", "yourpassword", "User")
[System.Environment]::SetEnvironmentVariable("JQUANTS_API_KEY", "yourapikey", "User")
```

**コードからの参照**:
```python
import os
email = os.environ.get('JQUANTS_EMAIL')
password = os.environ.get('JQUANTS_PASSWORD')
api_key = os.environ.get('JQUANTS_API_KEY')
```

### 原則5: legacy/ は読み取り専用
```
legacy/
├─ projects/（元のノートブック、編集禁止）
└─ _inbox/（J-Quants過去データ、編集禁止）
```

**禁止操作**:
- ❌ `Edit`（編集）
- ❌ `Write`（上書き）
- ❌ `Bash rm`（削除）
- ❌ `Bash mv`（移動）

**許可操作**:
- ✅ `Read`（参照）
- ✅ `Glob`（ファイル検索）
- ✅ `Grep`（内容検索）

---

## ファイル構成ルール

### プランニング
```
docs/plans/{YYYYMMDD_HHMM}_{topic}/
├─ 01_first_plan.md（初回計画）
├─ 02_{short_title}.md（追加・変更）
└─ 03_...（必要に応じて増分）
```

### セッションログ
```
docs/sessions/{YYYYMMDD_HHMM}_{summary}.md
```

**記載内容**:
- やったこと
- 決めたこと
- 次にやること
- 重要なパス/コマンド

### 知見の蓄積
```
docs/knowledges/
├─ {topic}_schema.md（データ定義）
├─ {topic}_runbook.md（運用手順）
└─ {topic}_notes.md（注意点）
```

### 分析プロジェクト
```
analyses/{YYYYMMDD_HHMM}_{topic}/
├─ idea_XX.md（計画/仮説）
└─ analysis_XX.ipynb（実装）
```

**対応関係**: idea_XX.md と analysis_XX.ipynb は1:1対応

---

## トラブルシューティング

### Q1: 前回の作業が思い出せない
**A**: セッションログを確認
```powershell
# 最新5件のセッションログを表示
Get-ChildItem .\docs\sessions\ -Filter *.md | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | ForEach-Object { Write-Host $_.Name; Get-Content $_.FullName | Select-Object -First 10; Write-Host "---`n" }
```

### Q2: 修正したはずのファイルが元に戻っている
**A**: NotebookEditの反映確認
```bash
# 修正が反映されているか確認
grep "検索ワード" path/to/notebook.ipynb
```

### Q3: パーミッションプロンプトが出ない
**A**: `--dangerously-skip-permissions` で起動していないか確認
```powershell
# プロセスを確認
Get-Process -Name claude* | Select-Object CommandLine
```

### Q4: 環境変数が読み込めない
**A**: PowerShellを再起動
```powershell
# 環境変数を確認
$env:JQUANTS_EMAIL
$env:JQUANTS_PASSWORD
$env:JQUANTS_API_KEY
```

---

## チェックリスト（セッション開始時）

- [ ] `claude` のみで起動（`--dangerously-skip-permissions` なし）
- [ ] 最新のセッションログを確認
- [ ] 前回の「次にやること」を把握
- [ ] 必要なファイルパスを確認
- [ ] npm系コマンドが提案されたら拒否する準備

---

## チェックリスト（セッション終了時）

- [ ] セッションログを `docs/sessions/` に保存
- [ ] やったこと・決めたこと・次にやることを記載
- [ ] 重要なパス・コマンドを記載
- [ ] 新しい知見があれば `docs/knowledges/` に保存
- [ ] Git commit（必要に応じて）

---

## 参考リンク

- **CLAUDE.md**: `C:\Users\yongr\claude project\workspace\CLAUDE.md`
- **セッションログ**: `C:\Users\yongr\claude project\workspace\docs\sessions\`
- **ナレッジベース**: `C:\Users\yongr\claude project\workspace\docs\knowledges\`
- **プラン**: `C:\Users\yongr\claude project\workspace\docs\plans\`

---

**最終更新**: 2026-02-18
**ステータス**: 運用中
