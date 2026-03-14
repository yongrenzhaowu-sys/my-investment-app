# セキュアなAPIキー管理ガイド

**作成日**: 2026-03-04 16:00
**目的**: J-Quants APIキーを安全に管理するためのベストプラクティス

---

## 🔒 セキュリティレイヤー

### レイヤー1: Windows環境変数（最推奨）

**メリット**:
- ファイルに保存しない（漏洩リスク最小）
- ユーザー単位で管理
- アプリケーション間で共有可能

**設定方法**:

#### 方法A: GUI（推奨）
1. Windowsキー → "環境変数" で検索
2. "システム環境変数の編集" を選択
3. "環境変数" ボタンをクリック
4. **ユーザー環境変数**（推奨）または システム環境変数 の "新規" をクリック
5. 変数名: `JQUANTS_API_KEY`
6. 変数値: `your-actual-api-key-here`
7. OK で保存
8. **重要**: コマンドプロンプト/PowerShellを再起動

#### 方法B: PowerShell（一時的、セッションのみ）
```powershell
$env:JQUANTS_API_KEY = "your-actual-api-key-here"
```

#### 方法C: PowerShell（永続化、ユーザーレベル）
```powershell
# ユーザー環境変数に設定
[System.Environment]::SetEnvironmentVariable('JQUANTS_API_KEY', 'your-actual-api-key-here', 'User')

# 確認
[System.Environment]::GetEnvironmentVariable('JQUANTS_API_KEY', 'User')
```

#### 確認方法
```bash
# コマンドプロンプト
echo %JQUANTS_API_KEY%

# PowerShell
echo $env:JQUANTS_API_KEY

# Git Bash
echo $JQUANTS_API_KEY
```

---

### レイヤー2: .env ファイル（次善策）

Windows環境変数が設定できない場合のフォールバック。

#### .env ファイルの作成

```bash
cd "C:\Users\yongr\claude project\workspace"

# テンプレートからコピー
cp .env.example .env

# 編集（実際のAPIキーを入力）
code .env
```

**内容**:
```env
# J-Quants API V2
JQUANTS_API_KEY=your-actual-api-key-here

# タイムゾーン
TZ=Asia/Tokyo
```

#### ⚠️ セキュリティ注意事項

1. **パーミッション設定**（Git Bashで）:
   ```bash
   # 所有者のみ読み取り可能に
   chmod 600 .env
   ```

2. **絶対に.envをコミットしない**:
   ```bash
   # .gitignoreで除外されているか確認
   grep "^\.env$" .gitignore

   # もし含まれていなければ追加
   echo ".env" >> .gitignore
   ```

3. **バックアップに注意**:
   - クラウドストレージ（Dropbox、OneDrive）に自動同期しない
   - USBメモリ等に平文でコピーしない

---

### レイヤー3: コード内の保護

#### APIキーの検証と保護

現在の`JQuantsDataProvider`を改善：

**問題点**:
```python
# 現在: エラーメッセージでAPIキーが漏洩する可能性
if not api_key:
    raise ValueError(
        "環境変数 JQUANTS_API_KEY が設定されていません。\n"
        "Windowsシステム環境変数に設定してください。"
    )
```

**改善案**: マスク処理を追加

---

## 🛡️ セキュリティベストプラクティス

### 1. APIキーの検証

```python
import os
import re

def validate_api_key(api_key: str) -> bool:
    """APIキーの形式を検証（実際の形式に合わせて調整）"""
    # 例: 最低長チェック
    if len(api_key) < 20:
        return False
    # 英数字のみ許可（実際の形式に合わせる）
    if not re.match(r'^[A-Za-z0-9_-]+$', api_key):
        return False
    return True
```

### 2. ログ出力の防止

```python
def mask_api_key(api_key: str) -> str:
    """APIキーをマスク表示"""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"

# 使用例
print(f"APIキー: {mask_api_key(api_key)}")
# 出力: APIキー: abcd...xyz9
```

### 3. 環境変数の優先順位

```python
import os

def get_api_key() -> str:
    """
    優先順位でAPIキーを取得:
    1. Windows環境変数 (JQUANTS_API_KEY)
    2. .env ファイル（docker-composeが自動読み込み）
    3. エラー
    """
    api_key = os.environ.get("JQUANTS_API_KEY")

    if not api_key:
        raise ValueError(
            "APIキーが設定されていません。\n"
            "以下のいずれかの方法で設定してください:\n"
            "1. Windows環境変数 JQUANTS_API_KEY（推奨）\n"
            "2. .env ファイル（プロジェクトルート）"
        )

    # 簡易検証
    if len(api_key) < 20:
        raise ValueError(
            f"APIキーの形式が不正です（長さ: {len(api_key)}）"
        )

    return api_key
```

---

## 🔄 APIキーのローテーション

### 定期的な更新（推奨: 3〜6ヶ月ごと）

1. **J-Quantsダッシュボード**で新しいAPIキーを発行
2. **新旧並行運用期間**を設ける（1週間程度）
3. **Windows環境変数を更新**
4. **動作確認**
5. **旧APIキーを無効化**

### 更新手順

```powershell
# 現在のAPIキーをバックアップ（メモ帳等に一時保存）
$old_key = [System.Environment]::GetEnvironmentVariable('JQUANTS_API_KEY', 'User')
Write-Host "Old key: $($old_key.Substring(0,4))..."

# 新しいAPIキーを設定
[System.Environment]::SetEnvironmentVariable('JQUANTS_API_KEY', 'new-api-key-here', 'User')

# 確認
$new_key = [System.Environment]::GetEnvironmentVariable('JQUANTS_API_KEY', 'User')
Write-Host "New key: $($new_key.Substring(0,4))..."

# 動作確認（コンテナで）
docker compose run --rm analysis-network sh -c "cd jquants-sector-momo && python -c 'from src.momo.providers import JQuantsDataProvider; p = JQuantsDataProvider(); print(\"OK\")'"
```

---

## 🚨 緊急時の対応

### APIキーが漏洩した場合

1. **即座にJ-Quantsダッシュボードで無効化**
2. **新しいAPIキーを発行**
3. **Windows環境変数を更新**
4. **Gitコミット履歴を確認**（誤ってコミットしていないか）
5. **必要に応じてリポジトリをクリーン**

### Gitコミット履歴からAPIキーを削除

```bash
# ⚠️ 危険な操作: 必ずバックアップを取ってから実行

# 全履歴から.envファイルを削除（BFG Repo-Cleaner推奨）
# https://rtyley.github.io/bfg-repo-cleaner/

# または、git filter-repo（新しい方法）
pip install git-filter-repo
git filter-repo --path .env --invert-paths
```

---

## 📋 チェックリスト

### 初期設定

- [ ] Windows環境変数に`JQUANTS_API_KEY`を設定
- [ ] `.env`ファイルが`.gitignore`に含まれているか確認
- [ ] `.env.example`には実際の値を含めない
- [ ] コンテナでAPIキーが正しく読み込まれるか確認

### 定期チェック（月次）

- [ ] `.env`ファイルがGit管理下にないか確認（`git status`）
- [ ] ログファイルにAPIキーが出力されていないか確認
- [ ] 不要なバックアップファイルを削除

### 定期更新（3〜6ヶ月ごと）

- [ ] APIキーをローテーション
- [ ] 動作確認
- [ ] 旧APIキーを無効化

---

## 🔗 関連リソース

### J-Quants公式
- API V2ドキュメント: https://jpx.gitbook.io/j-quants-ja/api-reference/
- ダッシュボード: https://jpx-jquants.com/

### セキュリティベストプラクティス
- OWASP API Security: https://owasp.org/www-project-api-security/
- 12 Factor App（環境変数の管理）: https://12factor.net/config

---

## 💡 まとめ

1. **最優先**: Windows環境変数でAPIキーを管理
2. **次善策**: `.env`ファイル（厳格なパーミッション）
3. **絶対NG**: コード内にハードコード、Gitにコミット
4. **定期的**: 3〜6ヶ月ごとにAPIキーをローテーション
5. **常に**: ログ出力を監視、マスク処理を実装

---

**作成日**: 2026-03-04 16:00
**更新日**: 2026-03-04 16:00
