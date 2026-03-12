/**
 * Google Apps Script: スプレッドシート書き込み用ウェブアプリ
 *
 * デプロイ: ウェブアプリとして公開 → URLを取得 → Streamlit SecretsのSPREADSHEET_WRITE_URLに設定
 */

function doPost(e) {
  try {
    // リクエストボディを解析
    var data = JSON.parse(e.postData.contents);

    // スプレッドシートを開く
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName("hypotheses");

    // シートが存在しない場合は作成
    if (!sheet) {
      sheet = ss.insertSheet("hypotheses");
      // ヘッダー行を作成
      sheet.appendRow([
        "id", "code", "name", "purchase_date", "purchase_price",
        "reason", "exit_kpi", "created_at"
      ]);
    }

    // アクションに応じて処理
    if (data.action === "overwrite") {
      // 全データを上書き
      overwriteData(sheet, data.data);
    } else if (data.action === "append") {
      // 1行追加
      appendRow(sheet, data.hypothesis);
    }

    return ContentService.createTextOutput(
      JSON.stringify({
        "status": "success",
        "message": "データを保存しました"
      })
    ).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(
      JSON.stringify({
        "status": "error",
        "message": error.toString()
      })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * 全データを上書き
 */
function overwriteData(sheet, hypotheses) {
  // 既存データを削除（ヘッダー行以外）
  var lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.deleteRows(2, lastRow - 1);
  }

  // 新しいデータを追加
  hypotheses.forEach(function(hypo) {
    var exitKpiStr = typeof hypo.exit_kpi === 'object'
      ? JSON.stringify(hypo.exit_kpi)
      : hypo.exit_kpi;

    sheet.appendRow([
      hypo.id,
      hypo.code,
      hypo.name || "",
      hypo.purchase_date,
      hypo.purchase_price,
      hypo.reason || "",
      exitKpiStr,
      hypo.created_at || ""
    ]);
  });
}

/**
 * 1行追加
 */
function appendRow(sheet, hypothesis) {
  var exitKpiStr = typeof hypothesis.exit_kpi === 'object'
    ? JSON.stringify(hypothesis.exit_kpi)
    : hypothesis.exit_kpi;

  sheet.appendRow([
    hypothesis.id,
    hypothesis.code,
    hypothesis.name || "",
    hypothesis.purchase_date,
    hypothesis.purchase_price,
    hypothesis.reason || "",
    exitKpiStr,
    hypothesis.created_at || ""
  ]);
}

/**
 * テスト用GET
 */
function doGet(e) {
  return ContentService.createTextOutput(
    JSON.stringify({
      "status": "ok",
      "message": "Google Apps Script is running"
    })
  ).setMimeType(ContentService.MimeType.JSON);
}
