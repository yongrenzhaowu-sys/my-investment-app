"""シンプルなGoogle Sheetsクライアント（認証不要）"""
import streamlit as st
import pandas as pd
import requests
from typing import List, Dict, Optional
import json


class SimpleGSheetsClient:
    """
    Google Sheetsをシンプルに扱うクライアント

    読み込み: スプレッドシートをCSVとして公開 → pandasで読み込み
    書き込み: Google Apps Script（ウェブアプリ）にPOSTリクエスト
    """

    def __init__(self, read_url: str, write_url: Optional[str] = None):
        """
        初期化

        Args:
            read_url: スプレッドシートのCSV公開URL
            write_url: Google Apps ScriptのウェブアプリURL（書き込み用）
        """
        self.read_url = read_url
        self.write_url = write_url

    def load_hypotheses(self) -> List[Dict]:
        """
        仮説データをGoogle Sheetsから読み込み

        Returns:
            仮説データのリスト
        """
        try:
            # pandasでCSVとして読み込み
            df = pd.read_csv(self.read_url)

            # 空のシートの場合
            if df.empty:
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
            st.warning(f"データ読み込みエラー: {e}")
            return []

    def save_hypotheses(self, hypotheses: List[Dict]) -> None:
        """
        仮説データをGoogle Sheetsに保存

        Args:
            hypotheses: 仮説データのリスト
        """
        if not self.write_url:
            st.error("書き込み用URLが設定されていません")
            return

        try:
            # 全データをJSON形式でPOST
            payload = {
                "action": "overwrite",
                "data": hypotheses
            }

            response = requests.post(
                self.write_url,
                json=payload,
                timeout=10
            )

            if response.status_code != 200:
                st.error(f"データ保存エラー: {response.status_code}")
            else:
                st.success("データを保存しました")

        except Exception as e:
            st.error(f"データ保存エラー: {e}")


def get_simple_gsheets_client() -> Optional[SimpleGSheetsClient]:
    """
    シンプルなGoogle Sheetsクライアントを取得

    Returns:
        SimpleGSheetsClientインスタンス、またはNone
    """
    if "simple_gsheets_client" not in st.session_state:
        try:
            read_url = st.secrets.get("SPREADSHEET_READ_URL")
            write_url = st.secrets.get("SPREADSHEET_WRITE_URL")

            if not read_url:
                st.error("SPREADSHEET_READ_URL が設定されていません")
                return None

            st.session_state.simple_gsheets_client = SimpleGSheetsClient(
                read_url=read_url,
                write_url=write_url
            )

        except Exception as e:
            st.error(f"Google Sheets接続エラー: {e}")
            return None

    return st.session_state.simple_gsheets_client
