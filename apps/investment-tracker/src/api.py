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
                # デバッグ: 利用可能な列名を確認
                if len(df) > 0:
                    print(f"[DEBUG {code}] 財務データの列名: {df.columns.tolist()}")
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

    def get_listed_companies(self) -> List[dict]:
        """
        全上場銘柄の情報を取得（セクターコード含む）

        Returns:
            銘柄情報のリスト [{"Code": "72030", "Sector33Code": "5050", ...}, ...]
        """
        # J-Quants API V2では /listed/info エンドポイントを使用
        url = f"{self.BASE_URL}/listed/info"

        try:
            print(f"DEBUG: Fetching listed companies from {url}")
            response = self.session.get(url, timeout=60)

            print(f"DEBUG: Response status code: {response.status_code}")

            response.raise_for_status()

            data = response.json()

            print(f"DEBUG: Response keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")

            # レスポンスキーの候補: "info", "data", "listed_info"
            companies = None
            if "info" in data and data["info"]:
                companies = data["info"]
            elif "data" in data and data["data"]:
                companies = data["data"]
            elif "listed_info" in data and data["listed_info"]:
                companies = data["listed_info"]

            if companies:
                print(f"DEBUG: Found {len(companies)} companies")

                # 最初の1件をサンプル表示
                if companies:
                    sample = companies[0]
                    print(f"DEBUG: Sample company keys: {sample.keys()}")
                    print(f"DEBUG: Sample company data: Code={sample.get('Code')}, Sector33Code={sample.get('Sector33Code')}, Sector17Code={sample.get('Sector17Code')}")

                # Sector33Codeがない場合は、Sector17Codeを使用
                for company in companies:
                    if "Sector33Code" not in company and "Sector17Code" in company:
                        company["Sector33Code"] = company["Sector17Code"]

                return companies
            else:
                print(f"WARNING: No companies found in response")
                print(f"WARNING: Response data: {str(data)[:500]}")  # 最初の500文字のみ
                return []

        except requests.exceptions.RequestException as e:
            error_msg = f"全銘柄情報取得エラー: {e}"
            print(f"ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            # 例外を再度投げて、呼び出し元で処理できるようにする
            raise Exception(f"{error_msg} (URL: {url})")

    def get_price_range(self, code: str, start_date: str, end_date: str) -> List[dict]:
        """
        期間指定で株価データを取得

        Args:
            code: 銘柄コード
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）

        Returns:
            株価データのリスト [{"Date": "2026-04-30", "Close": 1500.0, ...}, ...]
        """
        df = self.get_daily_quotes(code, start_date, end_date)

        if df.empty:
            return []

        # DataFrameをdictのリストに変換
        return df.to_dict('records')

    def get_indices_topix(self, start_date: str, end_date: str) -> List[dict]:
        """
        TOPIXのデータを取得

        Args:
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）

        Returns:
            TOPIXデータのリスト [{"Date": "2026-04-30", "Close": 2800.0}, ...]
        """
        url = f"{self.BASE_URL}/indices/topix"

        params = {
            "start_dt": start_date.replace("-", ""),
            "end_dt": end_date.replace("-", "")
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "topix" in data and data["topix"]:
                topix_data = data["topix"]
            elif "data" in data and data["data"]:
                topix_data = data["data"]
            else:
                return []

            return topix_data

        except requests.exceptions.RequestException as e:
            print(f"TOPIXデータ取得エラー: {e}")
            return []

    def get_topix_17_sectors(self, start_date: str, end_date: str) -> List[dict]:
        """
        TOPIX-17業種指数のデータを取得

        まず全データ一括取得を試し、失敗したら業種コードごとに取得

        Args:
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）

        Returns:
            17業種指数データのリスト
        """
        url = f"{self.BASE_URL}/indices/topix_industry"

        # 方法1: 全データ一括取得を試す
        print(f"DEBUG: Trying to fetch all sectors at once")
        params = {
            "start_dt": start_date.replace("-", ""),
            "end_dt": end_date.replace("-", "")
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            print(f"DEBUG: Response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"DEBUG: Response keys: {list(data.keys())}")

                # データ取得
                sector_data = None
                if "industry" in data and data["industry"]:
                    sector_data = data["industry"]
                    print(f"DEBUG: Found 'industry' key with {len(sector_data)} records")
                elif "data" in data and data["data"]:
                    sector_data = data["data"]
                    print(f"DEBUG: Found 'data' key with {len(sector_data)} records")
                elif "topix_industry" in data and data["topix_industry"]:
                    sector_data = data["topix_industry"]
                    print(f"DEBUG: Found 'topix_industry' key with {len(sector_data)} records")

                if sector_data and len(sector_data) > 0:
                    # サンプルデータを表示
                    print(f"DEBUG: Sample record: {sector_data[0]}")
                    return sector_data

        except Exception as e:
            print(f"DEBUG: Bulk fetch failed: {e}")

        # 方法2: code + date で業種ごとに取得
        print(f"DEBUG: Trying code + date (per sector)")

        # 33業種分類コード
        sector_codes_33 = [
            "0050", "1050", "2050", "3050", "3100", "3150", "3200", "3250",
            "3300", "3350", "3400", "3450", "3500", "3550", "3600", "3650",
            "3700", "3750", "3800", "4050", "5050", "5100", "5150", "5200",
            "5250", "6050", "6100", "7050", "7100", "7150", "7200", "8050",
            "9050", "9999"
        ]

        # まず1業種でテスト（0050: 水産・農林業）
        test_code = sector_codes_33[0]
        params_test = {
            "code": test_code,
            "date": end_date.replace("-", "")
        }

        try:
            response = self.session.get(url, params=params_test, timeout=30)
            print(f"DEBUG: Code {test_code} + date - Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"DEBUG: Response keys: {list(data.keys())}")

                sector_data = None
                if "industry" in data and data["industry"]:
                    sector_data = data["industry"]
                elif "data" in data and data["data"]:
                    sector_data = data["data"]
                elif "topix_industry" in data and data["topix_industry"]:
                    sector_data = data["topix_industry"]

                if sector_data:
                    print(f"DEBUG: Success! Code {test_code}: {len(sector_data)} records")
                    print(f"DEBUG: Sample data: {sector_data[0] if sector_data else 'None'}")

                    # 全業種のデータを取得
                    all_data = []
                    for code in sector_codes_33:
                        # 開始日のデータ
                        params_start = {
                            "code": code,
                            "date": start_date.replace("-", "")
                        }
                        resp_start = self.session.get(url, params=params_start, timeout=30)

                        # 終了日のデータ
                        params_end = {
                            "code": code,
                            "date": end_date.replace("-", "")
                        }
                        resp_end = self.session.get(url, params=params_end, timeout=30)

                        if resp_start.status_code == 200 and resp_end.status_code == 200:
                            data_start = resp_start.json()
                            data_end = resp_end.json()

                            sd_start = data_start.get("industry") or data_start.get("data") or data_start.get("topix_industry")
                            sd_end = data_end.get("industry") or data_end.get("data") or data_end.get("topix_industry")

                            if sd_start and sd_end:
                                all_data.extend(sd_start)
                                all_data.extend(sd_end)

                    if all_data:
                        print(f"DEBUG: Total {len(all_data)} records from {len(sector_codes_33)} sectors")
                        return all_data
                else:
                    print(f"DEBUG: No sector data in response")

        except Exception as e:
            print(f"DEBUG: Error with code + date: {e}")

        print("ERROR: All fetch methods failed")
        return []

    def get_sector_33_indices(self, start_date: str, end_date: str) -> List[dict]:
        """
        東証33業種指数のデータを取得

        J-Quants API の指数四本値API (/v2/indices/bars/daily) を使用
        指数コード: 0040〜0072 (33業種)

        Args:
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）

        Returns:
            33業種指数データのリスト
            [{"Date": "2026-04-30", "Code": "0040", "Close": 123.45, ...}, ...]
        """
        from .sector_33_data import get_all_sector_codes

        url = f"{self.BASE_URL}/indices/bars/daily"

        # 33業種の指数コードを取得（0040〜0072）
        sector_codes = get_all_sector_codes()

        all_data = []

        print(f"DEBUG: Fetching 33 sector indices from {url}")
        print(f"DEBUG: Sector codes: {sector_codes}")

        for code in sector_codes:
            params = {
                "code": code,
                "from": start_date.replace("-", ""),  # YYYYMMDD形式
                "to": end_date.replace("-", "")       # YYYYMMDD形式
            }

            try:
                response = self.session.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()

                    # レスポンスキーの候補: "daily_bars", "data", "indices"
                    sector_data = None
                    if "daily_bars" in data and data["daily_bars"]:
                        sector_data = data["daily_bars"]
                    elif "data" in data and data["data"]:
                        sector_data = data["data"]
                    elif "indices" in data and data["indices"]:
                        sector_data = data["indices"]

                    if sector_data:
                        # 指数コードを追加（レスポンスに含まれていない場合）
                        for record in sector_data:
                            if "Code" not in record:
                                record["Code"] = code
                        all_data.extend(sector_data)
                        print(f"DEBUG: Code {code}: {len(sector_data)} records")
                    else:
                        print(f"WARNING: Code {code}: No data in response. Keys: {list(data.keys())}")

                elif response.status_code == 403:
                    print(f"ERROR: Code {code}: 403 Forbidden (プラン制限)")
                    # 1件でもエラーが出たら全体を中止
                    raise Exception(f"33業種指数の取得に失敗しました（403 Forbidden）。Standardプラン以上が必要です。")
                else:
                    print(f"WARNING: Code {code}: Status {response.status_code}")

            except requests.exceptions.RequestException as e:
                print(f"ERROR: Code {code}: {e}")
                # エラーが出ても継続（次の業種を試す）
                continue

        if not all_data:
            print("ERROR: No sector index data retrieved")
            return []

        print(f"DEBUG: Total {len(all_data)} records from {len(sector_codes)} sectors")

        # サンプルデータを表示
        if all_data:
            print(f"DEBUG: Sample record: {all_data[0]}")

        return all_data
