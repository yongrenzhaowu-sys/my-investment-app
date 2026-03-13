# シンプルなGoogle Sheetsセットアップガイド（認証不要）

## 概要

Google Cloudの複雑な設定を避けて、シンプルにGoogle Sheetsをデータベースとして使用します。

**セキュリティ**: アプリ側で `APP_PASSWORD` による認証があるため、スプレッドシートは公開設定でも実用上問題ありません。

## 所要時間

約10分

## セットアップ手順

### 1. Google Spreadsheetsを作成

1. https://sheets.google.com/ にアクセス
2. 新しいスプレッドシートを作成
3. スプレッドシート名: `investment-tracker-data`（任意）
4. シート名を「**hypotheses**」に変更（重要）
5. ヘッダー行を作成（A1〜I1に以下を入力）:

| A | B | C | D | E | F | G | H | I |
|---|---|---|---|---|---|---|---|---|
| id | code | name | purchase_date | purchase_price | shares | reason | exit_kpi | created_at |

### 2. スプレッドシートをウェブに公開（読み込み用）

1. 「ファイル」→「共有」→「ウェブに公開」
2. 「リンク」タブを選択
3. 公開範囲:
   - **シート**: hypotheses
   - **形式**: カンマ区切り形式（.csv）
4. 「公開」をクリック
5. 表示されるURLをコピー

例: `https://docs.google.com/spreadsheets/d/e/2PACX-1vS.../pub?gid=0&single=true&output=csv`

→ これが `SPREADSHEET_READ_URL` になります

### 3. Google Apps Scriptを作成（書き込み用）

#### 3-1. Apps Script エディタを開く

1. スプレッドシートで「拡張機能」→「Apps Script」
2. 新しいプロジェクトが開く

#### 3-2. コードを貼り付け

`Code.gs` の内容を全て削除し、以下をコピー＆ペースト：

```javascript
/**
 * Google Apps Script: スプレッドシート書き込み用ウェブアプリ
 */

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName("hypotheses");

    if (!sheet) {
      sheet = ss.insertSheet("hypotheses");
      sheet.appendRow([
        "id", "code", "name", "purchase_date", "purchase_price", "shares",
        "reason", "exit_kpi", "created_at"
      ]);
    }

    if (data.action === "overwrite") {
      overwriteData(sheet, data.data);
    }

    return ContentService.createTextOutput(
      JSON.stringify({ "status": "success" })
    ).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(
      JSON.stringify({ "status": "error", "message": error.toString() })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}

function overwriteData(sheet, hypotheses) {
  var lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.deleteRows(2, lastRow - 1);
  }

  hypotheses.forEach(function(hypo) {
    var exitKpiStr = typeof hypo.exit_kpi === 'object'
      ? JSON.stringify(hypo.exit_kpi)
      : hypo.exit_kpi;

    sheet.appendRow([
      hypo.id, hypo.code, hypo.name || "",
      hypo.purchase_date, hypo.purchase_price, hypo.shares || 100,
      hypo.reason || "", exitKpiStr, hypo.created_at || ""
    ]);
  });
}
```

#### 3-3. デプロイ

1. 右上の「デプロイ」→「新しいデプロイ」
2. 「タイプの選択」→「ウェブアプリ」
3. 設定:
   - **説明**: investment-tracker-write（任意）
   - **次のユーザーとして実行**: 自分
   - **アクセスできるユーザー**: **全員**（重要）
4. 「デプロイ」をクリック
5. 承認画面が表示されたら「アクセスを承認」
6. Googleアカウントを選択 → 「詳細」→「プロジェクト名（安全ではないページ）に移動」→「許可」
7. 表示される「ウェブアプリURL」をコピー

例: `https://script.google.com/macros/s/AKfycby.../exec`

→ これが `SPREADSHEET_WRITE_URL` になります

### 4. Streamlit Secretsの設定

#### ローカル環境（.streamlit/secrets.toml）

```toml
# Google Sheetsを使用
USE_GSHEETS = false  # ローカル開発時はfalse

# Google Sheets URL（Streamlit Cloud用）
SPREADSHEET_READ_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS.../pub?gid=0&single=true&output=csv"
SPREADSHEET_WRITE_URL = "https://script.google.com/macros/s/AKfycby.../exec"
```

#### Streamlit Cloud

```toml
# J-Quants API
JQUANTS_API_KEY = "あなたのAPIキー"
APP_PASSWORD = "あなたのパスワード"

# Google Sheetsを使用
USE_GSHEETS = true

# Google Sheets URL
SPREADSHEET_READ_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS.../pub?gid=0&single=true&output=csv"
SPREADSHEET_WRITE_URL = "https://script.google.com/macros/s/AKfycby.../exec"
```

## 動作確認

### ローカル環境（JSONファイル）

1. `.streamlit/secrets.toml` で `USE_GSHEETS = false`
2. アプリ起動
3. 仮説登録
4. `data/hypotheses.json` にデータが保存されることを確認

### Streamlit Cloud（Google Sheets）

1. Streamlit CloudのSecretsで `USE_GSHEETS = true`
2. アプリ起動
3. 仮説登録
4. Google Spreadsheetsを開いて、データが保存されていることを確認

## トラブルシューティング

### エラー: "データ読み込みエラー"

**原因**: SPREADSHEET_READ_URLが正しくない

**対処法**:
1. スプレッドシートが「ウェブに公開」されているか確認
2. URLの末尾が `output=csv` になっているか確認
3. シート名が「hypotheses」になっているか確認

### エラー: "データ保存エラー"

**原因**: SPREADSHEET_WRITE_URLが正しくない、またはApps Scriptが公開されていない

**対処法**:
1. Apps Scriptが「ウェブアプリとして公開」されているか確認
2. 「アクセスできるユーザー」が「全員」になっているか確認
3. URLが `https://script.google.com/macros/s/.../exec` 形式か確認

### Apps Script承認画面が表示されない

**対処法**:
1. ブラウザのポップアップブロックを無効化
2. シークレットモードでやり直す
3. 別のGoogleアカウントで試す

## セキュリティに関する注意

### なぜ公開設定で問題ないか

1. **読み取り専用のデータ**: 個人の投資仮説データは公開されても実害が少ない
2. **アプリ側で認証**: `APP_PASSWORD` で保護されているため、URL知らなければアクセス不可
3. **書き込みもURL必要**: Apps ScriptのURLを知らなければ書き込み不可

### より安全にしたい場合

- Googleアカウントでログイン機能を追加（OAuth）
- Google Cloud Platformのサービスアカウント認証を使用（複雑）
- データを暗号化して保存

## メリット

✅ **設定が超シンプル** - Google Cloudの設定不要
✅ **無料** - Google Sheetsの無料枠で十分
✅ **リアルタイム同期** - スプレッドシートを直接編集してもアプリに反映
✅ **可視性が高い** - Excelライクに直接データを確認・編集可能

## デメリット

⚠️ **公開設定** - URLを知っていれば誰でも読み取り可能
⚠️ **同時編集に弱い** - 複数ユーザーが同時に書き込むと競合の可能性
⚠️ **API制限** - Apps Scriptは1日20,000リクエストまで

## 参考リンク

- Google Sheetsをウェブに公開: https://support.google.com/docs/answer/183965
- Google Apps Script: https://developers.google.com/apps-script
