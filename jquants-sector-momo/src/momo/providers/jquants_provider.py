"""
J-Quants API データプロバイダー

調整済み日次バー（AdjO/AdjH/AdjL/AdjC/AdjVo）と銘柄マスター（sector33含む）を取得

参考:
- J-Quants API V2:
  https://jpx.gitbook.io/j-quants-ja/api-reference/
- 調整済み列: AdjO, AdjH, AdjL, AdjC, AdjVo (V2の短縮形式)
"""
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
import pandas as pd
import requests


class JQuantsDataProvider:
    """J-Quants API V2 クライアント（既存の認証方式互換）"""

    BASE_URL = "https://api.jquants.com/v2"

    @staticmethod
    def _mask_api_key(api_key: str) -> str:
        """APIキーをマスク表示（セキュリティ保護）"""
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:4]}...{api_key[-4:]}"

    @staticmethod
    def _validate_api_key(api_key: str) -> bool:
        """APIキーの基本的な検証"""
        # 最低限の長さチェック
        if len(api_key) < 20:
            return False
        # 空白文字を含まない
        if ' ' in api_key or '\t' in api_key or '\n' in api_key:
            return False
        return True

    def __init__(self):
        """初期化（環境変数 JQUANTS_API_KEY から取得）"""
        # 優先順位: 1. 環境変数、2. .envファイル（docker-composeが読み込み）
        api_key = os.environ.get("JQUANTS_API_KEY")

        if not api_key:
            raise ValueError(
                "APIキーが設定されていません。\n"
                "以下のいずれかの方法で設定してください:\n"
                "1. Windows環境変数 JQUANTS_API_KEY（推奨）\n"
                "2. .env ファイル（プロジェクトルート）\n"
                "詳細: docs/knowledges/20260304_1600_secure_api_key_management.md"
            )

        # APIキーの簡易検証
        if not self._validate_api_key(api_key):
            masked = self._mask_api_key(api_key)
            raise ValueError(
                f"APIキーの形式が不正です: {masked}\n"
                f"長さ: {len(api_key)}文字（最低20文字必要）"
            )

        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": self.api_key})

        # 初期化ログ（APIキーはマスク）
        masked_key = self._mask_api_key(self.api_key)
        print(f"[INFO] APIキー設定完了: {masked_key}")

    def _request(self, endpoint: str, params: Optional[Dict] = None, max_retries: int = 3) -> Dict:
        """APIリクエスト送信（セキュアなエラーハンドリング）"""
        url = f"{self.BASE_URL}{endpoint}"

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=60)
                response.raise_for_status()
                return response.json()

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt
                    print(f"  [WAIT] レート制限、{wait_time}秒待機中...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 401:  # Unauthorized
                    masked_key = self._mask_api_key(self.api_key)
                    raise RuntimeError(
                        f"認証エラー（APIキー無効）: {masked_key}\n"
                        "APIキーを確認してください。"
                    )
                elif response.status_code == 403:  # Forbidden
                    raise RuntimeError(
                        "アクセス権限エラー。APIキーの権限を確認してください。"
                    )
                else:
                    # エラーレスポンスからAPIキーを除去
                    error_msg = str(e).replace(self.api_key, self._mask_api_key(self.api_key))
                    raise RuntimeError(f"HTTPエラー: {error_msg}")

            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    # エラーメッセージからAPIキーを除去
                    error_msg = str(e).replace(self.api_key, self._mask_api_key(self.api_key))
                    raise RuntimeError(f"リクエストエラー: {error_msg}")
                time.sleep(2 ** attempt)

        raise RuntimeError(f"{max_retries}回のリトライ後に失敗")

    def fetch_master(self, prime_only: bool = False) -> pd.DataFrame:
        """
        銘柄マスター取得（sector33含む）

        Args:
            prime_only: Trueの場合、プライム市場のみに絞る

        Returns:
            pd.DataFrame: 銘柄マスター（Code, CompanyName, Sector33Code等）
        """
        print("[INFO] 銘柄マスター取得中...")

        # ローカルマスターファイルを読み込み
        import os
        # jquants-sector-momo/ から workspace/ にさかのぼる
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        master_path = os.path.join(
            project_root,
            "legacy", "_inbox", "merged_data_all_stocks", "jquants_data", "listed_info.parquet"
        )

        if not os.path.exists(master_path):
            raise FileNotFoundError(
                f"銘柄マスターファイルが見つかりません: {master_path}\n"
                "legacy/_inbox/merged_data_all_stocks/jquants_data/listed_info.parquet を配置してください。"
            )

        df = pd.read_parquet(master_path)

        # 列名を統一（S33 -> Sector33Code, CoName -> CompanyName）
        df = df.rename(columns={
            "S33": "Sector33Code",
            "CoName": "CompanyName",
        })

        # 最新日付のデータのみ
        latest_date = df["Date"].max()
        df = df[df["Date"] == latest_date].copy()

        # プライム市場のみに絞る
        if prime_only:
            if "Mkt" in df.columns:
                df = df[df["Mkt"].str.contains("Prime|プライム", na=False)].copy()
                print(f"  [OK] プライム市場のみに絞り込み: {len(df)}銘柄")
            else:
                print("  [WARN] Mkt列が存在しないため、prime_onlyを無視します")

        # Code列を文字列型に統一
        df["Code"] = df["Code"].astype(str)

        print(f"  [OK] 銘柄マスター取得完了: {len(df)}銘柄")
        return df[["Code", "CompanyName", "Sector33Code"]]

    def fetch_daily_bars(
        self,
        start_date: str,
        end_date: str,
        codes: Optional[list] = None,
        use_api: bool = True,
    ) -> pd.DataFrame:
        """
        日次バー取得（調整済み価格）

        Args:
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）
            codes: 銘柄コードリスト（Noneの場合は全銘柄）
            use_api: TrueならAPIから取得、FalseならローカルファイルからX取得

        Returns:
            pd.DataFrame: 日次バー（Date, Code, AdjO, AdjH, AdjL, AdjC, AdjVo含む）
        """
        print(f"[INFO] 日次バー取得中: {start_date} 〜 {end_date}")

        if use_api:
            # APIから取得
            print(f"  [INFO] J-Quants APIから取得中...")
            return self._fetch_daily_bars_from_api(start_date, end_date, codes)
        else:
            # ローカルファイルから取得
            print(f"  [INFO] ローカルファイルから取得中...")
            return self._fetch_daily_bars_from_local(start_date, end_date, codes)

    def _fetch_daily_bars_from_api(
        self,
        start_date: str,
        end_date: str,
        codes: Optional[list] = None,
    ) -> pd.DataFrame:
        """APIから日次バーを取得"""
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        date_range = pd.date_range(start=start_dt, end=end_dt, freq='B')  # 営業日

        all_data = []
        total_dates = len(date_range)

        for i, date in enumerate(date_range):
            date_str = date.strftime('%Y-%m-%d')

            if i % 5 == 0:  # 進捗表示（5日ごと）
                print(f"  進捗: {i+1}/{total_dates} 日付")

            try:
                params = {"date": date_str}
                data = self._request("/equities/bars/daily", params=params)

                if "data" in data and data["data"]:
                    all_data.extend(data["data"])

            except Exception as e:
                # 休日等でデータがない日は無視
                continue

        if not all_data:
            raise ValueError(f"APIからデータを取得できませんでした（期間: {start_date} 〜 {end_date}）")

        df = pd.DataFrame(all_data)

        # Date列をdatetimeに変換
        df["Date"] = pd.to_datetime(df["Date"])

        # Code列を文字列型に統一
        df["Code"] = df["Code"].astype(str)

        # 銘柄コード絞り込み
        if codes:
            codes_str = [str(c) for c in codes]
            df = df[df["Code"].isin(codes_str)].copy()
            print(f"  [OK] 銘柄絞り込み: {len(df)}レコード")

        # 必要な列を確認（AdjO, AdjH, AdjL, AdjC, AdjVo）
        required_cols = ["Date", "Code", "AdjO", "AdjH", "AdjL", "AdjC", "AdjVo"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            raise ValueError(f"必要な列が不足: {missing_cols}")

        print(f"  [OK] 日次バー取得完了: {len(df)}レコード")
        return df[required_cols]

    def _fetch_daily_bars_from_local(
        self,
        start_date: str,
        end_date: str,
        codes: Optional[list] = None,
    ) -> pd.DataFrame:
        """ローカルファイルから日次バーを取得"""
        import os
        import glob
        # jquants-sector-momo/ から workspace/ にさかのぼる
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        daily_bars_dir = os.path.join(
            project_root,
            "legacy", "_inbox", "jquants_daily_bars_10y_parquet", "daily_parquet"
        )

        if not os.path.exists(daily_bars_dir):
            raise FileNotFoundError(
                f"日次バーディレクトリが見つかりません: {daily_bars_dir}"
            )

        # 全parquetファイルを読み込み
        parquet_files = sorted(glob.glob(os.path.join(daily_bars_dir, "*.parquet")))
        if not parquet_files:
            raise FileNotFoundError(f"parquetファイルが見つかりません: {daily_bars_dir}")

        print(f"  [INFO] {len(parquet_files)}個のparquetファイルを読み込み中...")
        df = pd.concat([pd.read_parquet(f) for f in parquet_files], ignore_index=True)

        # Date列をdatetimeに変換
        df["Date"] = pd.to_datetime(df["Date"])

        # Code列を文字列型に統一
        df["Code"] = df["Code"].astype(str)

        # 日付範囲でフィルタ
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df["Date"] >= start_dt) & (df["Date"] <= end_dt)].copy()

        # 銘柄コード絞り込み
        if codes:
            codes_str = [str(c) for c in codes]
            df = df[df["Code"].isin(codes_str)].copy()
            print(f"  [OK] 銘柄絞り込み: {len(df)}レコード")

        # 必要な列を確認（AdjO, AdjH, AdjL, AdjC, AdjVo）
        required_cols = ["Date", "Code", "AdjO", "AdjH", "AdjL", "AdjC", "AdjVo"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            raise ValueError(f"必要な列が不足: {missing_cols}")

        print(f"  [OK] 日次バー取得完了: {len(df)}レコード")
        return df[required_cols]

    def fetch_data(
        self,
        days: int = 400,
        asof_date: Optional[str] = None,
        prime_only: bool = False,
        use_api: bool = True,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
        """
        データ一括取得（マスター + 日次バー）

        Args:
            days: 遡る日数
            asof_date: 基準日（YYYY-MM-DD）、未指定なら最新
            prime_only: プライム市場のみに絞るか
            use_api: TrueならAPIから取得、Falseならローカルファイル

        Returns:
            tuple: (master, daily_bars, actual_asof_date)
        """
        # 1. 銘柄マスター取得
        master = self.fetch_master(prime_only=prime_only)

        # 2. 基準日の決定
        if asof_date:
            end_date = asof_date
        else:
            # 最新データの日付を取得（簡易版: 今日-1日）
            end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        start_date = (
            datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        # 3. 日次バー取得
        daily_bars = self.fetch_daily_bars(
            start_date=start_date,
            end_date=end_date,
            codes=master["Code"].tolist(),
            use_api=use_api,
        )

        # 実際のasof_dateを取得（データの最大日付）
        if not daily_bars.empty and "Date" in daily_bars.columns:
            actual_asof = daily_bars["Date"].max().strftime("%Y-%m-%d")
        else:
            actual_asof = end_date

        print(f"OK データ取得完了: asof={actual_asof}, 期間={days}日")
        return master, daily_bars, actual_asof
