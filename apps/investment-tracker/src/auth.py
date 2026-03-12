"""J-Quants API認証モジュール"""
import os
from typing import Optional


class JQuantsAuth:
    """J-Quants API V2 認証クラス（APIキーベース）"""

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
        if len(api_key) < 20:
            return False
        if ' ' in api_key or '\t' in api_key or '\n' in api_key:
            return False
        return True

    def __init__(self, secrets: Optional[dict] = None):
        """
        初期化（Streamlit Secrets または環境変数から取得）

        Args:
            secrets: Streamlit secrets辞書（st.secrets）
        """
        # 優先順位: 1. Streamlit Secrets, 2. 環境変数
        if secrets and "JQUANTS_API_KEY" in secrets:
            self.api_key = secrets["JQUANTS_API_KEY"]
        else:
            self.api_key = os.environ.get("JQUANTS_API_KEY")

        if not self.api_key:
            raise ValueError(
                "APIキーが設定されていません。\n"
                "以下のいずれかの方法で設定してください:\n"
                "1. .streamlit/secrets.toml に JQUANTS_API_KEY を設定\n"
                "2. Windows環境変数 JQUANTS_API_KEY を設定"
            )

        # APIキーの簡易検証
        if not self._validate_api_key(self.api_key):
            masked = self._mask_api_key(self.api_key)
            raise ValueError(
                f"APIキーの形式が不正です: {masked}\n"
                f"長さ: {len(self.api_key)}文字（最低20文字必要）"
            )

    def get_headers(self) -> dict:
        """APIリクエスト用のヘッダーを取得"""
        return {"x-api-key": self.api_key}
