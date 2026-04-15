"""J-Quants APIクライアント"""
import requests
import pandas as pd
from typing import Optional, List
from datetime import datetime, timedelta
from .auth import JQuantsAuth


class JQuantsClient:
    """J-Quants API V2 クライアント"""

    BASE_URL = "https://api.jquants.com/v2"

    def __init__(self, auth: JQuantsAuth):
        self.auth = auth
        self.session = requests.Session()
        self.session.headers.update(self.auth.get_headers())

    def get_daily_quotes(
        self,
        code: str,
        from_date: str,
        to_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        日次株価を取得（J-Quants API V2）

        Args:
            code: 銘柄コード（例: "72030"）
            from_date: 開始日（YYYY-MM-DD）
            to_date: 終了日（YYYY-MM-DD）、Noneなら今日

        Returns:
            日次株価データフレーム（Date, Close列含む）
        """
        url = f"{self.BASE_URL}/equities/bars/daily"

        # 5桁コードの場合は4桁に変換（例: "72030" -> "7203"）
        code_param = code[:4] if len(code) == 5 else code

        params = {
            "code": code_param,
            "start_dt": from_date.replace("-", ""),  # YYYYMMDD形式
        }

        # to_dateが指定されている場合のみend_dtを追加
        if to_date is not None:
            params["end_dt"] = to_date.replace("-", "")

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # データ取得の判定
            if "daily_bars" in data and data["daily_bars"]:
                df = pd.DataFrame(data["daily_bars"])
            elif "data" in data and data["data"]:
                # 別のキー名の可能性
                df = pd.DataFrame(data["data"])
            else:
                return pd.DataFrame()

            # 日付列を変換
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"])
            elif "date" in df.columns:
                df["Date"] = pd.to_datetime(df["date"])
                df = df.drop(columns=["date"])

            # 終値列を確認（AdjC or Close or close）
            if "AdjC" in df.columns:
                df["Close"] = df["AdjC"]
            elif "close" in df.columns:
                df["Close"] = df["close"]

            # 銘柄コードでフィルタリング（5桁でも4桁でも対応）
            if "Code" in df.columns:
                # 5桁コード（例: "72030"）と4桁コード（例: "7203"）の両方に対応
                code_5digit = code if len(code) == 5 else code + "0"
                code_4digit = code[:4] if len(code) == 5 else code
                df = df[df["Code"].isin([code, code_5digit, code_4digit])].copy()

            # 日付範囲でフィルタリング
            if "Date" in df.columns and not df.empty:
                from_dt = pd.to_datetime(from_date)
                if to_date is not None:
                    to_dt = pd.to_datetime(to_date)
                    df = df[(df["Date"] >= from_dt) & (df["Date"] <= to_dt)].copy()
                else:
                    # to_dateが指定されていない場合は、from_date以降のデータすべて
                    df = df[df["Date"] >= from_dt].copy()

            df = df.sort_values("Date")
            return df

        except requests.exceptions.RequestException as e:
            raise Exception(f"株価取得に失敗: {e}")

    def get_financial_statements(
        self,
        code: str,
        limit: int = 5
    ) -> pd.DataFrame:
        """
        財務諸表データを取得（J-Quants API V2）

        Args:
            code: 銘柄コード（例: "72030"）
            limit: 取得件数（直近N件）

        Returns:
            財務データフレーム
        """
        # V2では /fins/statements → /fins/summary に変更
        url = f"{self.BASE_URL}/fins/summary"

        # 銘柄コードは5桁のまま渡す（J-Quants API V2は5桁を期待）
        params = {"code": code}

        try:
            response = self.session.get(url, params=params, timeout=30)

            # 403エラーの場合、パラメータなしで試す
            if response.status_code == 403:
                response = self.session.get(url, timeout=30)

            response.raise_for_status()

            data = response.json()

            # V2では "data" キーに統一
            if "data" in data and data["data"]:
                df = pd.DataFrame(data["data"])
            elif "statements" in data and data["statements"]:
                # 旧形式（V1互換）
                df = pd.DataFrame(data["statements"])
            else:
                return pd.DataFrame()

            # 最新N件のみ取得
            if not df.empty:
                # 日付列を探す（DiscDate, DisclosedDate, disclosed_date, etc.）
                date_col = None
                for col in ["DiscDate", "DisclosedDate", "disclosed_date", "DisclosureDate", "CurPerEn", "CurrentPeriodEndDate"]:
                    if col in df.columns:
                        date_col = col
                        break

                if date_col:
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                    df = df.sort_values(date_col, ascending=False).head(limit)
                else:
                    # 日付列が見つからない場合、警告を出す
                    print(f"警告: 銘柄{code}の財務データに日付列が見つかりません。列名: {df.columns.tolist()}")
                    df = df.head(limit)

            return df

        except requests.exceptions.RequestException as e:
            raise Exception(f"財務データ取得に失敗: {e}")

    def get_company_info(self, code: str) -> dict:
        """
        銘柄情報を取得（J-Quants API V2）

        Args:
            code: 銘柄コード（例: "72030"）

        Returns:
            銘柄情報辞書（CompanyName含む）
        """
        # V2では /listed/info → /equities/master に変更
        url = f"{self.BASE_URL}/equities/master"

        # 銘柄コードは5桁のまま渡す
        params = {"code": code}

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # V2のレスポンス形式: {"data": [...]}
            if "data" in data and len(data["data"]) > 0:
                company_data = data["data"][0]
                # V2では CoName が会社名（CompanyName に正規化）
                if "CoName" in company_data and "CompanyName" not in company_data:
                    company_data["CompanyName"] = company_data["CoName"]
                return company_data
            # V1互換のレスポンス形式
            elif "info" in data and len(data["info"]) > 0:
                return data["info"][0]
            elif "listed_info" in data and len(data["listed_info"]) > 0:
                return data["listed_info"][0]
            elif isinstance(data, list) and len(data) > 0:
                return data[0]

            # データが見つからない場合
            print(f"WARNING: 銘柄情報が見つかりません（コード: {code}）")
            return {"Code": code, "CompanyName": f"銘柄{code}"}

        except requests.exceptions.RequestException as e:
            # エラー時
            print(f"WARNING: 銘柄情報取得エラー（コード: {code}）: {e}")
            return {"Code": code, "CompanyName": f"銘柄{code}"}

    def get_earnings_forecast(self, code: str) -> pd.DataFrame:
        """
        業績予想データを取得（J-Quants API V2）

        Args:
            code: 銘柄コード（5桁文字列）

        Returns:
            業績予想データフレーム（会社発表の予想値）
        """
        url = f"{self.BASE_URL}/fins/announcement"
        params = {"code": code}

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "data" in data and data["data"]:
                df = pd.DataFrame(data["data"])

                # 日付列を変換
                if "Date" in df.columns:
                    df["Date"] = pd.to_datetime(df["Date"], errors='coerce')

                # 最新の予想データを優先（日付降順）
                if "Date" in df.columns:
                    df = df.sort_values("Date", ascending=False)

                return df
            else:
                return pd.DataFrame()

        except requests.exceptions.RequestException as e:
            print(f"業績予想データ取得エラー（{code}）: {e}")
            return pd.DataFrame()
