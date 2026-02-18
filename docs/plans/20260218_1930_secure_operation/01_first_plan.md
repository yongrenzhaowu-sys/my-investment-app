# セキュアな運用への移行計画

**作成日**: 2026-02-18 19:30
**目的**: npm系リスクゼロ確認後、残る課題（権限・秘密情報・Git管理）への対応
**優先度**: 高（セキュリティ・安全性確保）

---

## 1. 現状確認（完了済み）

### ✅ npm系リスク調査結果
**調査日**: 2026-02-18 19:00
**調査ファイル**: `docs/sessions/20260218_1900_npm_investigation.md`

| 調査項目 | 結果 | リスク評価 |
|---------|------|-----------|
| npm/node実行ファイル | なし | ✅ 安全 |
| package.json | なし | ✅ 安全 |
| node_modules/ | なし | ✅ 安全 |
| .npmrc設定ファイル | なし | ✅ 安全 |
| シェル履歴（npm関連） | なし | ✅ 安全 |
| npmグローバルディレクトリ | なし | ✅ 安全 |

**結論**: npm/nodeツールは一切インストールされておらず、使用履歴もなし。**リスクゼロ**。

### 現在の作業内容
- **環境**: 純粋なPython環境（pip管理）
- **データソース**: J-Quants API
- **分析ツール**: pandas, Jupyter Notebook
- **制約遵守**: CLAUDE.mdの「npm系は禁止」が**完全に守られている**

---

## 2. 残る課題（優先順）

### ❶ `--dangerously-skip-permissions` の常用（高リスク）
**問題**:
- Claude Codeを `--dangerously-skip-permissions` フラグ付きで起動している可能性
- すべてのコマンド（削除、上書き、ネットワークアクセス等）が確認なしで実行される
- **事故リスク**: 意図しないファイル削除、データ破損、情報漏洩

**影響範囲**:
- ファイルシステム全体（workspace外も含む）
- ネットワーク通信
- 環境変数・システム設定

**リスクレベル**: 🔴 **高**

---

### ❷ `.env` に email+password 保存（中リスク）
**問題**:
- J-Quants認証情報（メールアドレス、パスワード、APIキー）が平文で保存
- 保存場所: `legacy/_inbox/.env`
- **漏洩リスク**: バックアップ、誤共有、マルウェア等で情報が外部流出

**現在の.env内容（推測）**:
```
JQUANTS_MAIL_ADDRESS=user@example.com
JQUANTS_PASSWORD=plaintext_password
JQUANTS_API_KEY=api_key_string
```

**リスクレベル**: 🟠 **中**

---

### ❸ Git管理未導入（中リスク）
**問題**:
- ワークスペースがGit管理されていない（`git status` → "Not a git repository"）
- **復旧手段不足**: 誤削除・誤編集時にロールバック不可
- **変更履歴なし**: いつ何を変更したか追跡できない
- **コラボレーション困難**: 複数環境での同期が手動

**影響範囲**:
- analyses/（分析プロジェクト）
- scripts/（Pythonスクリプト）
- docs/（ドキュメント）
- CLAUDE.md（重要な制約ファイル）

**リスクレベル**: 🟡 **中**

---

## 3. 対応計画

### Phase 1（今週実施）：権限の正常化

#### 目的
`--dangerously-skip-permissions` フラグを使わない安全な運用に移行

#### 実施内容
1. **次回起動から通常モードで起動**:
   ```bash
   # ❌ 現在（危険）
   claude --dangerously-skip-permissions

   # ✅ 変更後（安全）
   claude
   ```

2. **危険コマンドは毎回確認**:
   - ファイル削除（rm, Remove-Item）
   - ファイル上書き（>, Write）
   - Git操作（push, reset --hard）
   - ネットワークアクセス（curl, wget）

3. **自動許可リストの活用**（任意）:
   - Read, Glob, Grep等の読み取り専用操作は自動許可
   - 書き込み操作は確認プロンプト表示

#### 完了条件
- Claude Codeが通常権限で正常に動作する
- 危険な操作時に確認プロンプトが表示される
- 誤操作による事故リスクが大幅に低減

#### 所要時間
- 初回設定: 5分
- 慣れるまで: 1-2日

---

### Phase 2（今週実施）：J-Quants資格情報の移行

#### 目的
平文パスワードをディスクから削除し、Windows環境変数に移行

#### 実施内容

##### ステップ1：Windows環境変数への登録
```powershell
# PowerShellで実行（管理者権限不要、ユーザー環境変数）
[System.Environment]::SetEnvironmentVariable('JQUANTS_MAIL_ADDRESS', 'user@example.com', 'User')
[System.Environment]::SetEnvironmentVariable('JQUANTS_PASSWORD', 'your_password', 'User')
[System.Environment]::SetEnvironmentVariable('JQUANTS_API_KEY', 'your_api_key', 'User')
```

##### ステップ2：Pythonスクリプトの修正
**対象ファイル**:
- `scripts/fetch_jquants_data.py`
- `legacy/_inbox/`配下のスクリプト（参照のみ、編集しない）

**変更内容**:
```python
# ❌ 変更前（.envファイル読み込み）
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv('JQUANTS_API_KEY')

# ✅ 変更後（環境変数から直接読み込み）
import os
api_key = os.environ.get('JQUANTS_API_KEY')
# または
api_key = os.getenv('JQUANTS_API_KEY')  # .envなしでもOK
```

**注意**:
- `python-dotenv`は削除せず、フォールバック用に残す（オプション）
- `legacy/_inbox/.env`は**読み取り専用**なので編集しない

##### ステップ3：.envファイルの退避
```bash
# legacy/_inbox/.env は原本なので移動・削除しない（CLAUDE.md遵守）
# 代わりに、新規スクリプトが.envを読まないことを確認

# 確認方法
python scripts/fetch_jquants_data.py --help
# 環境変数から読み込めることを確認
```

#### 完了条件
- Windows環境変数に資格情報が登録されている
- Pythonスクリプトが環境変数から資格情報を読み込める
- `.env`ファイルを読み込まなくてもスクリプトが動作する

#### 所要時間
- 環境変数設定: 5分
- スクリプト修正: 10分
- 動作確認: 5分
- **合計**: 約20分

---

### Phase 3（来週以降）：Git管理の導入

#### 目的
ファイル変更履歴の追跡と復旧手段の確保

#### 実施内容

##### ステップ1：Git初期化
```bash
cd "C:\Users\yongr\claude project\workspace"
git init
git config user.name "Your Name"
git config user.email "your@email.com"
```

##### ステップ2：.gitignore作成
```gitignore
# 機密情報
.env
*.env
credentials.json
secrets.yaml

# 大容量データ（Gitで管理しない）
data/raw/
data/curated/
data/fetched/
legacy/_inbox/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/

# Jupyter
.ipynb_checkpoints/
*.ipynb_checkpoints

# OS
.DS_Store
Thumbs.db
desktop.ini

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
```

##### ステップ3：初回コミット
```bash
git add .
git commit -m "Initial commit: workspace setup

- analyses/: 分析プロジェクト
- scripts/: データ取得スクリプト
- docs/: ドキュメント・計画・セッション記録
- CLAUDE.md: プロジェクト制約

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

##### ステップ4：定期的なコミット（ルール化）
- **タイミング**: 各セッション終了時
- **コミットメッセージ**: `docs/sessions/`ファイル名を参照
- **除外**: data/, legacy/_inbox/（.gitignoreで除外済み）

#### 完了条件
- ワークスペースがGit管理されている
- .gitignoreで機密情報・大容量データを除外
- 変更履歴が`git log`で確認できる

#### 所要時間
- Git初期化: 10分
- .gitignore作成: 10分
- 初回コミット: 5分
- **合計**: 約25分

---

## 4. 完了条件（全体）

### Phase 1
- [ ] Claude Codeが通常権限（`--dangerously-skip-permissions`なし）で起動できる
- [ ] 危険なコマンド実行時に確認プロンプトが表示される
- [ ] 誤操作による事故が発生していない

### Phase 2
- [ ] Windows環境変数に`JQUANTS_*`が設定されている
- [ ] `scripts/fetch_jquants_data.py`が環境変数から資格情報を読み込める
- [ ] `.env`ファイルを読み込まなくてもスクリプトが正常動作する

### Phase 3
- [ ] ワークスペースが`git status`で管理状態になっている
- [ ] `.gitignore`が機密情報・大容量データを除外している
- [ ] 初回コミットが完了している
- [ ] セッション終了時にコミットする習慣がついている

---

## 5. 次のアクション

### 優先度1（即実施）：Phase 1 - 権限の正常化
1. **Claude Codeの再起動**:
   ```bash
   # 現在のセッションを終了
   exit

   # 通常モードで再起動
   claude
   ```

2. **動作確認**:
   - 読み取り操作（Read, Glob, Grep）が自動実行される
   - 書き込み操作（Write, Edit, Bash）で確認プロンプトが表示される

3. **完了報告**:
   - `docs/sessions/20260218_2000_phase1_done.md` を作成
   - 動作確認結果を記録

### 優先度2（今週中）：Phase 2 - 資格情報の移行
- Phase 1完了後に実施
- 環境変数設定 → スクリプト修正 → 動作確認

### 優先度3（来週以降）：Phase 3 - Git導入
- Phase 2完了後に実施
- git init → .gitignore → 初回コミット

---

## 6. リスク管理

### Phase 1 のリスク
**リスク**: 権限確認が煩わしくなる
**対策**: 自動許可リストを活用（読み取り専用操作は自動許可）

**リスク**: Claude Codeが動作しなくなる
**対策**: 問題があれば一時的に`--dangerously-skip-permissions`に戻す（ただし長期利用は避ける）

### Phase 2 のリスク
**リスク**: 環境変数が読み込めない
**対策**: PowerShellを再起動、または`$env:JQUANTS_API_KEY`で確認

**リスク**: スクリプト修正ミスでAPIアクセス失敗
**対策**: 修正前にバックアップ、段階的にテスト

### Phase 3 のリスク
**リスク**: .gitignoreの設定ミスで機密情報をコミット
**対策**: `git status`で必ず確認、`git add`は個別ファイル指定を推奨

**リスク**: 大容量データをコミットしてリポジトリが肥大化
**対策**: .gitignoreで`data/`, `legacy/`を除外、`git add`前に確認

---

## 7. 参考資料

### 関連ドキュメント
- `docs/sessions/20260218_1900_npm_investigation.md`（npm系リスク調査）
- `docs/knowledges/data_update_howto.md`（J-Quants APIの使い方）
- `CLAUDE.md`（プロジェクト制約）

### 外部リンク
- [J-Quants API ドキュメント](https://jpx-jquants.com/)
- [Windows環境変数の設定方法](https://learn.microsoft.com/ja-jp/windows/win32/procthread/environment-variables)
- [Git公式ドキュメント](https://git-scm.com/doc)

---

## 8. 進捗管理

| Phase | タスク | ステータス | 期限 | 完了日 |
|-------|--------|-----------|------|--------|
| 1 | 権限正常化 | 🟡 計画中 | 今週中 | - |
| 2 | 資格情報移行 | ⚪ 未着手 | 今週中 | - |
| 3 | Git導入 | ⚪ 未着手 | 来週以降 | - |

---

**次のステップ**: Phase 1（権限正常化）を実施し、`docs/sessions/20260218_2000_phase1_done.md` に報告
