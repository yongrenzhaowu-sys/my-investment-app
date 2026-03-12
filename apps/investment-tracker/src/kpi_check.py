"""KPI自動チェックモジュール"""
import pandas as pd
from typing import Dict, Optional
from .api import JQuantsClient


def check_exit_kpi(
    client: JQuantsClient,
    code: str,
    kpi_config: dict
) -> Dict[str, any]:
    """
    撤退KPIをチェック

    Args:
        client: J-Quants APIクライアント
        code: 銘柄コード（例: "72030"）
        kpi_config: KPI設定
            {
                "metric": "operating_margin",  # 営業利益率
                "threshold": 10.0,
                "operator": "less_than"  # or "greater_than"
            }

    Returns:
        {
            "triggered": bool,  # 警告発動フラグ
            "current_value": float,  # 現在値
            "threshold": float,  # 閾値
            "message": str,  # メッセージ
            "latest_fiscal_period": str  # 最新決算期
        }
    """
    # 財務データ取得
    fin_df = client.get_financial_statements(code, limit=1)

    if fin_df.empty:
        return {
            "triggered": False,
            "current_value": None,
            "threshold": kpi_config["threshold"],
            "message": "財務データが取得できませんでした",
            "latest_fiscal_period": None
        }

    latest = fin_df.iloc[0]

    # KPI計算
    metric = kpi_config["metric"]
    current_value = None

    if metric == "operating_margin":
        # 営業利益率 = 営業利益 / 売上高 * 100
        # V2 API: OP (営業利益), Sales (売上高)
        if "OP" in latest and "Sales" in latest:
            # 文字列型の可能性があるため数値に変換
            operating_profit = pd.to_numeric(latest["OP"], errors='coerce')
            net_sales = pd.to_numeric(latest["Sales"], errors='coerce')

            if net_sales and net_sales != 0 and not pd.isna(operating_profit) and not pd.isna(net_sales):
                current_value = (operating_profit / net_sales) * 100

    # 閾値判定
    threshold = kpi_config["threshold"]
    operator = kpi_config["operator"]
    triggered = False

    if current_value is not None:
        if operator == "less_than":
            triggered = current_value < threshold
        elif operator == "greater_than":
            triggered = current_value > threshold

    # メッセージ生成
    # V2 API: CurPerEn (会計期間終了日)
    fiscal_period = latest.get("CurPerEn", "不明")

    if current_value is None:
        message = "⚠️ 営業利益率を計算できませんでした（データ不足）"
    elif triggered:
        message = f"🚨 警告: 営業利益率 {current_value:.2f}% が閾値 {threshold}% を下回っています"
    else:
        message = f"✅ 正常: 営業利益率 {current_value:.2f}%"

    return {
        "triggered": triggered,
        "current_value": current_value,
        "threshold": threshold,
        "message": message,
        "latest_fiscal_period": fiscal_period
    }
