"""Google Sheetsデータ永続化モジュール"""
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
import json


class GoogleSheetsClient:
    """Google Sheetsでデータを永続化するクライアント"""

    def __init__(self):
        """Google Sheets接続を初期化"""
        try:
            self.conn = st.connection("gsheets", type=GSheetsConnection)
        except Exception as e:
            raise Exception(
                f"Google Sheets接続に失敗しました: {e}\n"
                "Secretsに connections.gsheets を設定してください。"
            )

    def load_hypotheses(self) -> List[Dict]:
        """
        仮説データをGoogle Sheetsから読み込み

        Returns:
            仮説データのリスト
        """
        try:
            # スプレッドシートからデータフレームを読み込み
            df = self.conn.read(worksheet="hypotheses", ttl=0)

            # 空のシートの場合
            if df.empty or (len(df) == 1 and df.iloc[0].isna().all()):
                return []

            # DataFrameを辞書のリストに変換
            hypotheses = []
            for _, row in df.iterrows():
                # NaN値をスキップ
                if pd.isna(row.get("id")):
                    continue

                # exit_kpiをJSON文字列から辞書に変換
                exit_kpi_str = row.get("exit_kpi", "{}")
                if pd.isna(exit_kpi_str):
                    exit_kpi = {
                        "metric": "operating_margin",
                        "threshold": 10.0,
                        "operator": "less_than"
                    }
                else:
                    try:
                        exit_kpi = json.loads(exit_kpi_str)
                    except:
                        exit_kpi = {
                            "metric": "operating_margin",
                            "threshold": 10.0,
                            "operator": "less_than"
                        }

                hypothesis = {
                    "id": str(row["id"]),
                    "code": str(row["code"]),
                    "name": str(row.get("name", "")),
                    "purchase_date": str(row["purchase_date"]),
                    "purchase_price": float(row["purchase_price"]),
                    "reason": str(row.get("reason", "")),
                    "exit_kpi": exit_kpi,
                    "created_at": str(row.get("created_at", ""))
                }
                hypotheses.append(hypothesis)

            return hypotheses

        except Exception as e:
            # エラー時は空リストを返す（初回アクセス時など）
            st.warning(f"データ読み込みエラー（初回は正常）: {e}")
            return []

    def save_hypotheses(self, hypotheses: List[Dict]) -> None:
        """
        仮説データをGoogle Sheetsに保存

        Args:
            hypotheses: 仮説データのリスト
        """
        try:
            # 辞書のリストをDataFrameに変換
            if not hypotheses:
                # 空の場合はヘッダーのみのDataFrameを作成
                df = pd.DataFrame(columns=[
                    "id", "code", "name", "purchase_date", "purchase_price",
                    "reason", "exit_kpi", "created_at"
                ])
            else:
                # exit_kpiを辞書からJSON文字列に変換
                for hypo in hypotheses:
                    if isinstance(hypo.get("exit_kpi"), dict):
                        hypo["exit_kpi_str"] = json.dumps(hypo["exit_kpi"], ensure_ascii=False)
                    else:
                        hypo["exit_kpi_str"] = "{}"

                df = pd.DataFrame([
                    {
                        "id": h["id"],
                        "code": h["code"],
                        "name": h.get("name", ""),
                        "purchase_date": h["purchase_date"],
                        "purchase_price": h["purchase_price"],
                        "reason": h.get("reason", ""),
                        "exit_kpi": h.get("exit_kpi_str", "{}"),
                        "created_at": h.get("created_at", "")
                    }
                    for h in hypotheses
                ])

            # Google Sheetsに書き込み
            self.conn.update(worksheet="hypotheses", data=df)

        except Exception as e:
            st.error(f"データ保存エラー: {e}")
            raise


def get_gsheets_client() -> Optional[GoogleSheetsClient]:
    """
    Google Sheetsクライアントを取得（セッション状態でキャッシュ）

    Returns:
        GoogleSheetsClientインスタンス、またはNone（エラー時）
    """
    if "gsheets_client" not in st.session_state:
        try:
            st.session_state.gsheets_client = GoogleSheetsClient()
        except Exception as e:
            st.error(f"Google Sheets接続エラー: {e}")
            return None

    return st.session_state.gsheets_client
