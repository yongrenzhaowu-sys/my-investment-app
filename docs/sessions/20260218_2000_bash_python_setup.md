# セッションサマリー：bash環境でPython実行を有効化

**日時**: 2026-02-18 20:00～20:30
**所要時間**: 約30分
**目的**: bash環境からPythonとJupyter Notebookを実行できるようにする

---

## やったこと

### 1. 問題の特定
**初期状態**:
- PowerShell: ✅ `py`コマンドでPython実行可能（Python 3.13.12）
- bash: ❌ `python`コマンドが見つからない

**原因**:
- Microsoft Store版Pythonがインストールされていたが、bash環境から実行できない制限あり
- WindowsのPATHがbash環境に正しく継承されていない

### 2. python.org版のインストール
**実施内容**:
- https://www.python.org/ から Python 3.13.12 インストーラーをダウンロード
- インストール時に「Add Python to PATH」にチェック
- インストール場所: `C:\Users\yongr\AppData\Local\Programs\Python\Python313\`

**インストールされたパス**:
```
C:\Users\yongr\AppData\Local\Programs\Python\Python313\python.exe
C:\Users\yongr\AppData\Local\Programs\Python\Python313\Scripts\
C:\Users\yongr\AppData\Local\Programs\Python\Launcher\
C:\Users\yongr\AppData\Local\Python\bin
```

### 3. bash設定ファイルの作成
**作成したファイル**:
- `~/.bashrc`（bash設定ファイル）
- `~/.bash_profile`（ログイン時に`.bashrc`を読み込む）

**`.bashrc`の内容**:
```bash
# Python.org版のPATH追加（優先）
export PATH="/c/Users/yongr/AppData/Local/Programs/Python/Python313:$PATH"
export PATH="/c/Users/yongr/AppData/Local/Programs/Python/Python313/Scripts:$PATH"

# その他のPython関連パス
export PATH="/c/Users/yongr/AppData/Local/Python/bin:$PATH"

# 確認メッセージ（初回ログイン時のみ表示）
if [ -z "$BASHRC_LOADED" ]; then
    echo "✅ Python環境設定完了 (python.org版)"
    export BASHRC_LOADED=1
fi
```

**`.bash_profile`の内容**:
```bash
# .bashrcが存在すれば読み込む
if [ -f ~/.bashrc ]; then
    source ~/.bashrc
fi
```

### 4. 必要なパッケージのインストール
**インストールコマンド**:
```bash
pip install pandas pyarrow requests python-dotenv jupyter notebook matplotlib
```

**インストールされた主要パッケージ**:
- pandas 3.0.1
- numpy 2.4.2
- pyarrow 23.0.1
- requests 2.32.5
- python-dotenv 1.2.1
- jupyter 1.1.1
- notebook 7.5.3
- matplotlib 3.10.8
- ipykernel 7.2.0
- jupyterlab 4.5.4

### 5. 動作確認
**確認項目**:
- [x] `python --version` → Python 3.13.12
- [x] `pip --version` → pip 25.3
- [x] `jupyter --version` → Jupyter 7.5.3
- [x] `python scripts/fetch_jquants_data.py --help` → 正常動作
- [x] pandas, numpy, matplotlib のインポート → 成功

---

## 決めたこと

### Python環境の選択
**選択**: python.org版（標準版）をインストール

**理由**:
- bash環境からの実行互換性が高い
- 開発ツールとの互換性が良好
- Microsoft Store版の制限を回避

**共存**:
- Microsoft Store版: そのまま残す（PowerShellから利用可能）
- python.org版: bash環境で優先的に使用

### PATH設定の方針
**優先順位**:
1. python.org版のPython (`/c/Users/.../Python313`)
2. python.org版のScripts (`/c/Users/.../Python313/Scripts`)
3. その他のPythonパス

**理由**: bash環境では python.org版を優先、PowerShell環境では既存の設定を維持

### パッケージ管理
**方針**: python.org版のpipで管理

**インストール済みパッケージ**:
- データ分析: pandas, numpy, pyarrow
- API通信: requests, python-dotenv
- 可視化: matplotlib
- ノートブック: jupyter, notebook, jupyterlab

---

## 次にやること

### Phase 2の続き（完了確認）
Phase 2（資格情報移行）で設定した環境変数が、python.org版でも正常に読み込まれるか確認:
```bash
cd "C:\Users\yongr\claude project\workspace"
python scripts/fetch_jquants_data.py --days 1
```

### Phase 3（来週以降）：Git導入
- `git init`でリポジトリ初期化
- `.gitignore`作成
- 初回コミット

### 分析作業の再開
- 修正版Notebookの実行（週次vs月次バックテスト）
- データ更新スクリプトの定期実行

---

## 重要なパス/コマンド

### 作成・更新したファイル
```bash
# bash設定ファイル
~/.bashrc
~/.bash_profile

# セッションサマリー（本ファイル）
docs/sessions/20260218_2000_bash_python_setup.md
```

### Python実行コマンド（bash環境）
```bash
# Pythonバージョン確認
python --version

# スクリプト実行
cd "C:\Users\yongr\claude project\workspace"
python scripts/fetch_jquants_data.py --help

# Jupyter Notebook起動
jupyter notebook

# パッケージインストール
pip install package_name
```

### 環境変数確認（bash環境）
```bash
# PATH確認
echo $PATH

# Python実行パス確認
which python

# 環境変数確認（Phase 2で設定）
echo $JQUANTS_API_KEY
```

---

## 学んだこと・注意点

### 1. Microsoft Store版 vs python.org版
**Microsoft Store版**:
- ✅ PowerShellから簡単に利用可能
- ✅ 自動更新
- ❌ bash環境からの実行に制限あり
- ❌ 一部のツールとの互換性問題

**python.org版**:
- ✅ bash環境から直接実行可能
- ✅ 開発ツールとの互換性が高い
- ✅ フルコントロール
- ❌ 手動更新が必要

### 2. bash設定ファイルの役割
**.bashrc**:
- 対話型シェル起動時に読み込まれる
- エイリアス、環境変数、関数などを定義
- bash --login -c で実行するコマンドにも適用

**.bash_profile**:
- ログイン時に読み込まれる
- 通常は`.bashrc`を読み込むだけ

### 3. WindowsとbashのPATH変換
**Windows形式**:
```
C:\Users\yongr\AppData\Local\Programs\Python\Python313
```

**bash形式**:
```
/c/Users/yongr/AppData/Local/Programs/Python/Python313
```

### 4. 日本語エンコーディングの問題
**問題**: bash環境でcp932エンコーディングによる日本語の文字化け

**影響**: ヘルプメッセージやエラーメッセージが文字化け（機能的には問題なし）

**対処**: 必要に応じて環境変数で UTF-8 を設定
```bash
export PYTHONIOENCODING=utf-8
```

### 5. パッケージのバージョン管理
**ベストプラクティス**:
- `requirements.txt`を作成して管理
- 仮想環境（venv）の利用を検討（将来）

**現在の状態**: グローバルにインストール（シンプル、学習・個人開発向け）

### 6. 複数Python環境の共存
**現在の構成**:
- Microsoft Store版: `C:\Users\...\WindowsApps\PythonSoftwareFoundation.Python.3.13_...`
- python.org版: `C:\Users\...\Programs\Python\Python313`

**選択方法**:
- PowerShell: `py`コマンドが自動選択
- bash: `.bashrc`のPATH順で python.org版が優先

---

## 📊 環境構成サマリ

| 環境 | Python | バージョン | パッケージ | 用途 |
|------|--------|-----------|-----------|------|
| PowerShell | Microsoft Store版 / python.org版 | 3.13.12 | 最小限 / フル | 既存作業 / 新規作業 |
| bash | python.org版 | 3.13.12 | フル | Claude Code作業 |

**パッケージ状態**:
- pandas, numpy, pyarrow: データ分析
- requests, python-dotenv: API通信
- jupyter, notebook: ノートブック環境
- matplotlib: 可視化

---

## 📈 次回セッション候補

### 即実施推奨
1. **環境変数テスト**:
   - Phase 2で設定した`JQUANTS_API_KEY`がpython.org版で読み込まれるか確認
   - スクリプトの初回実行

2. **修正版Notebookの実行**:
   - 週次vs月次バックテストの比較
   - Cell 26→25→24→23→22の順で実行

### 今週中
3. **Phase 3（Git導入）**:
   - リポジトリ初期化
   - .gitignore作成
   - 初回コミット

### 来週以降
4. **分析作業の本格化**:
   - 最新データで既存戦略を再検証
   - 新規戦略開発

---

**ステータス**: bash環境でPython実行が可能になった ✅
**次のアクション**: 環境変数テストとスクリプト初回実行、またはNotebook実行サポート
**推定所要時間**: 各5～15分
