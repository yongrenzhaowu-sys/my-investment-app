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

    def __init__(
        self,
        read_url: str,
        write_url: Optional[str] = None,
        trading_history_read_url: Optional[str] = None,
        additional_investments_read_url: Optional[str] = None,
        option_trades_read_url: Optional[str] = None
    ):
        """
        初期化

        Args:
            read_url: 保有銘柄シートのCSV公開URL
            write_url: Google Apps ScriptのウェブアプリURL（書き込み用）
            trading_history_read_url: 売買履歴シートのCSV公開URL
            additional_investments_read_url: 追加資金シートのCSV公開URL
            option_trades_read_url: オプション取引シートのCSV公開URL
        """
        self.read_url = read_url
        self.write_url = write_url
        self.trading_history_read_url = trading_history_read_url
        self.additional_investments_read_url = additional_investments_read_url
        self.option_trades_read_url = option_trades_read_url

    def load_hypotheses(self) -> List[Dict]:
        """
        仮説データをGoogle Sheetsから読み込み

        Returns:
            仮説データのリスト
        """
        try:
            # キャッシュ回避のため、URLにタイムスタンプを追加
            import time
            cache_buster = f"?_={int(time.time() * 1000)}"
            url_with_cache_buster = self.read_url + ("&" if "?" in self.read_url else "?") + f"_={int(time.time() * 1000)}"

            # pandasでCSVとして読み込み
            df = pd.read_csv(url_with_cache_buster)

            # 空のシートの場合
            if df.empty:
                return []

            # DataFrameを辞書のリストに変換
            hypotheses = []
            for idx, row in df.iterrows():
                try:
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
                        except Exception as e:
                            st.warning(f"行{idx}: exit_kpi解析エラー: {e}")
                            exit_kpi = {
                                "metric": "operating_margin",
                                "threshold": 10.0,
                                "operator": "less_than"
                            }

                    # sharesフィールドの処理（NaNチェック）
                    shares_value = row.get("shares", 100)
                    if pd.isna(shares_value):
                        shares_value = 100

                    hypothesis = {
                        "id": str(row["id"]),
                        "code": str(row["code"]),
                        "name": str(row.get("name", "")),
                        "purchase_date": str(row["purchase_date"]),
                        "purchase_price": float(row["purchase_price"]),
                        "shares": int(shares_value),
                        "reason": str(row.get("reason", "")),
                        "exit_kpi": exit_kpi,
                        "created_at": str(row.get("created_at", ""))
                    }
                    hypotheses.append(hypothesis)

                except Exception as e:
                    # 個別行のエラーをログに記録してスキップ
                    st.warning(f"行{idx}のデータ読み込みエラー（スキップ）: {e}")
                    continue

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

    def load_trading_history(self) -> List[Dict]:
        """
        売買履歴をGoogle Sheetsから読み込み

        Returns:
            売買履歴のリスト
        """
        if not self.trading_history_read_url:
            st.warning("売買履歴のURL（TRADING_HISTORY_READ_URL）が設定されていません")
            return []

        try:
            # キャッシュ回避のため、URLにタイムスタンプを追加
            import time
            url_with_cache_buster = self.trading_history_read_url + ("&" if "?" in self.trading_history_read_url else "?") + f"_={int(time.time() * 1000)}"

            # pandasでCSVとして読み込み
            df = pd.read_csv(url_with_cache_buster)

            # 空のシートの場合
            if df.empty:
                return []

            # DataFrameを辞書のリストに変換
            history = []
            for idx, row in df.iterrows():
                try:
                    # NaN値をスキップ
                    if pd.isna(row.get("id")):
                        continue

                    # is_nisaフィールドの処理
                    is_nisa_value = row.get("is_nisa", False)
                    if pd.isna(is_nisa_value):
                        is_nisa_value = False
                    elif isinstance(is_nisa_value, str):
                        is_nisa_value = is_nisa_value.lower() in ['true', '1', 'yes']

                    record = {
                        "id": str(row["id"]),
                        "code": str(row["code"]),
                        "name": str(row.get("name", "")),
                        "purchase_date": str(row["purchase_date"]),
                        "purchase_price": float(row["purchase_price"]),
                        "shares": int(row.get("shares", 100)),
                        "purchase_reason": str(row.get("purchase_reason", "")),
                        "sell_date": str(row["sell_date"]),
                        "sell_price": float(row["sell_price"]),
                        "sell_reason": str(row.get("sell_reason", "")),
                        "realized_profit": float(row["realized_profit"]),
                        "realized_profit_rate": float(row["realized_profit_rate"]),
                        "holding_days": int(row["holding_days"]),
                        "tax_amount": float(row["tax_amount"]),
                        "after_tax_profit": float(row["after_tax_profit"]),
                        "original_hypothesis_id": str(row.get("original_hypothesis_id", "")),
                        "created_at": str(row.get("created_at", "")),
                        "sold_at": str(row.get("sold_at", "")),
                        "kpi_threshold": float(row["kpi_threshold"]) if not pd.isna(row.get("kpi_threshold")) else None,
                        "is_nisa": is_nisa_value
                    }
                    history.append(record)

                except Exception as e:
                    # 個別行のエラーをログに記録してスキップ
                    st.warning(f"売買履歴の行{idx}のデータ読み込みエラー（スキップ）: {e}")
                    continue

            return history

        except Exception as e:
            st.warning(f"売買履歴の読み込みエラー: {e}")
            return []

    def save_trading_history(self, history: List[Dict]) -> None:
        """
        売買履歴をGoogle Sheetsに保存

        Args:
            history: 売買履歴のリスト
        """
        if not self.write_url:
            st.error("書き込み用URLが設定されていません")
            return

        try:
            # 売買履歴をJSON形式でPOST
            payload = {
                "action": "save_trading_history",
                "data": history
            }

            response = requests.post(
                self.write_url,
                json=payload,
                timeout=10
            )

            if response.status_code != 200:
                st.error(f"売買履歴の保存エラー: {response.status_code}")
            # 成功時はメッセージを表示しない（頻繁に保存されるため）

        except Exception as e:
            st.error(f"売買履歴の保存エラー: {e}")

    def load_additional_investments(self) -> List[Dict]:
        """
        追加資金をGoogle Sheetsから読み込み

        Returns:
            追加資金のリスト [{"date": "YYYY-MM-DD", "amount": 金額}, ...]
        """
        if not self.additional_investments_read_url:
            st.warning("追加資金のURL（ADDITIONAL_INVESTMENTS_READ_URL）が設定されていません")
            return []

        try:
            # キャッシュ回避のため、URLにタイムスタンプを追加
            import time
            url_with_cache_buster = self.additional_investments_read_url + ("&" if "?" in self.additional_investments_read_url else "?") + f"_={int(time.time() * 1000)}"

            # pandasでCSVとして読み込み
            df = pd.read_csv(url_with_cache_buster)

            # 空のシートの場合
            if df.empty:
                return []

            # DataFrameを辞書のリストに変換
            investments = []
            for idx, row in df.iterrows():
                try:
                    # NaN値をスキップ
                    if pd.isna(row.get("date")):
                        continue

                    investment = {
                        "date": str(row["date"]),
                        "amount": float(row["amount"])
                    }
                    investments.append(investment)

                except Exception as e:
                    # 個別行のエラーをログに記録してスキップ
                    st.warning(f"追加資金の行{idx}のデータ読み込みエラー（スキップ）: {e}")
                    continue

            # 日付順にソート
            return sorted(investments, key=lambda x: x["date"])

        except Exception as e:
            st.warning(f"追加資金の読み込みエラー: {e}")
            return []

    def save_additional_investments(self, investments: List[Dict]) -> None:
        """
        追加資金をGoogle Sheetsに保存

        Args:
            investments: 追加資金のリスト [{"date": "YYYY-MM-DD", "amount": 金額}, ...]
        """
        if not self.write_url:
            st.error("書き込み用URLが設定されていません")
            return

        try:
            # 追加資金をJSON形式でPOST
            payload = {
                "action": "save_additional_investments",
                "data": investments
            }

            response = requests.post(
                self.write_url,
                json=payload,
                timeout=10
            )

            if response.status_code != 200:
                st.error(f"追加資金の保存エラー: {response.status_code}")
            else:
                st.success("追加資金を保存しました")

        except Exception as e:
            st.error(f"追加資金の保存エラー: {e}")

    def load_option_trades(self) -> List[Dict]:
        """
        オプション取引をGoogle Sheetsから読み込み

        Returns:
            オプション取引のリスト
        """
        if not self.option_trades_read_url:
            st.warning("オプション取引のURL（OPTION_TRADES_READ_URL）が設定されていません")
            return []

        try:
            # キャッシュ回避のため、URLにタイムスタンプを追加
            import time
            url_with_cache_buster = self.option_trades_read_url + ("&" if "?" in self.option_trades_read_url else "?") + f"_={int(time.time() * 1000)}"

            # pandasでCSVとして読み込み
            df = pd.read_csv(url_with_cache_buster)

            # 空のシートの場合
            if df.empty:
                return []

            # DataFrameを辞書のリストに変換
            trades = []
            for idx, row in df.iterrows():
                try:
                    # NaN値をスキップ
                    if pd.isna(row.get("id")):
                        continue

                    trade = {
                        "id": str(row["id"]),
                        "date": str(row["date"]),
                        "description": str(row["description"]),
                        "profit": float(row["profit"]),
                        "created_at": str(row.get("created_at", ""))
                    }
                    trades.append(trade)

                except Exception as e:
                    # 個別行のエラーをログに記録してスキップ
                    st.warning(f"オプション取引の行{idx}のデータ読み込みエラー（スキップ）: {e}")
                    continue

            # 日付順にソート（新しい順）
            return sorted(trades, key=lambda x: x["date"], reverse=True)

        except Exception as e:
            st.warning(f"オプション取引の読み込みエラー: {e}")
            return []

    def save_option_trades(self, trades: List[Dict]) -> None:
        """
        オプション取引をGoogle Sheetsに保存

        Args:
            trades: オプション取引のリスト
        """
        if not self.write_url:
            st.error("書き込み用URLが設定されていません")
            return

        try:
            # オプション取引をJSON形式でPOST
            payload = {
                "action": "save_option_trades",
                "data": trades
            }

            response = requests.post(
                self.write_url,
                json=payload,
                timeout=10
            )

            if response.status_code != 200:
                st.error(f"オプション取引の保存エラー: {response.status_code}")
            # 成功時はメッセージを表示しない（頻繁に保存されるため）

        except Exception as e:
            st.error(f"オプション取引の保存エラー: {e}")


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
            trading_history_read_url = st.secrets.get("TRADING_HISTORY_READ_URL")
            additional_investments_read_url = st.secrets.get("ADDITIONAL_INVESTMENTS_READ_URL")
            option_trades_read_url = st.secrets.get("OPTION_TRADES_READ_URL")

            if not read_url:
                st.error("SPREADSHEET_READ_URL が設定されていません")
                return None

            st.session_state.simple_gsheets_client = SimpleGSheetsClient(
                read_url=read_url,
                write_url=write_url,
                trading_history_read_url=trading_history_read_url,
                additional_investments_read_url=additional_investments_read_url,
                option_trades_read_url=option_trades_read_url
            )

        except Exception as e:
            st.error(f"Google Sheets接続エラー: {e}")
            return None

    return st.session_state.simple_gsheets_client
