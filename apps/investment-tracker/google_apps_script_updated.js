/**
 * Google Apps Script - 投資判断支援アプリ用
 *
 * 機能：
 * 1. 保有銘柄の保存（既存）
 * 2. 売買履歴の保存（新規追加）
 */

function doPost(e) {
  try {
    // POSTデータを解析
    const params = JSON.parse(e.postData.contents);
    const action = params.action;

    if (action === "overwrite") {
      // 保有銘柄の保存（既存機能）
      return saveHypotheses(params.data);
    } else if (action === "save_trading_history") {
      // 売買履歴の保存（新規機能）
      return saveTradingHistory(params.data);
    } else {
      return ContentService.createTextOutput(JSON.stringify({
        status: "error",
        message: "Unknown action: " + action
      })).setMimeType(ContentService.MimeType.JSON);
    }
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * 保有銘柄を保存（既存機能）
 */
function saveHypotheses(data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("Hypotheses") || ss.getSheets()[0];

  // シートをクリア
  sheet.clear();

  // ヘッダー行
  const headers = ["id", "code", "name", "purchase_date", "purchase_price",
                  "shares", "reason", "exit_kpi", "created_at", "is_nisa"];
  sheet.appendRow(headers);

  // データ行
  data.forEach(function(hypo) {
    sheet.appendRow([
      hypo.id,
      hypo.code,
      hypo.name,
      hypo.purchase_date,
      hypo.purchase_price,
      hypo.shares || 100,
      hypo.reason,
      JSON.stringify(hypo.exit_kpi),
      hypo.created_at,
      hypo.is_nisa || false
    ]);
  });

  return ContentService.createTextOutput(JSON.stringify({
    status: "success",
    message: "保存しました"
  })).setMimeType(ContentService.MimeType.JSON);
}

/**
 * 売買履歴を保存（新規機能）
 */
function saveTradingHistory(data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // TradingHistoryシートを取得（なければ作成）
  let sheet = ss.getSheetByName("TradingHistory");
  if (!sheet) {
    sheet = ss.insertSheet("TradingHistory");
  }

  // シートをクリア
  sheet.clear();

  // ヘッダー行
  const headers = [
    "id", "code", "name", "purchase_date", "purchase_price", "shares",
    "purchase_reason", "sell_date", "sell_price", "sell_reason",
    "realized_profit", "realized_profit_rate", "holding_days",
    "tax_amount", "after_tax_profit", "original_hypothesis_id",
    "created_at", "sold_at", "kpi_threshold", "is_nisa"
  ];
  sheet.appendRow(headers);

  // データ行
  data.forEach(function(record) {
    sheet.appendRow([
      record.id,
      record.code,
      record.name,
      record.purchase_date,
      record.purchase_price,
      record.shares || 100,
      record.purchase_reason || "",
      record.sell_date,
      record.sell_price,
      record.sell_reason || "",
      record.realized_profit,
      record.realized_profit_rate,
      record.holding_days,
      record.tax_amount,
      record.after_tax_profit,
      record.original_hypothesis_id || "",
      record.created_at || "",
      record.sold_at || "",
      record.kpi_threshold || "",
      record.is_nisa || false
    ]);
  });

  return ContentService.createTextOutput(JSON.stringify({
    status: "success",
    message: "売買履歴を保存しました"
  })).setMimeType(ContentService.MimeType.JSON);
}
