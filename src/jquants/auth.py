"""J-Quants API 認証（V2 APIキー方式）。"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def get_api_key() -> str:
    """Windows環境変数からAPIキーを取得する。
    
    Returns:
        APIキー
        
    Raises:
        ValueError: APIキーが設定されていない場合
    """
    api_key = os.environ.get("JQUANTS_API_KEY")
    
    if not api_key:
        raise ValueError(
            "JQUANTS_API_KEY environment variable is not set. "
            "Please set it in Windows environment variables."
        )
    
    # セキュリティ：キーの存在確認のみログ出力（値は出さない）
    logger.info("J-Quants API key loaded from environment variable")
    
    return api_key


def validate_api_key(api_key: str) -> bool:
    """APIキーの形式を簡易検証する。
    
    Args:
        api_key: APIキー
        
    Returns:
        True if valid format
    """
    # 基本的な形式チェック（空でないこと）
    if not api_key or len(api_key) < 10:
        return False
    
    return True
