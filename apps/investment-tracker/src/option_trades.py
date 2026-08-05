"""オプション取引管理モジュール"""
import json
import os
from typing import List, Dict
from datetime import datetime
import uuid


def get_option_trades_file_path() -> str:
    """オプション取引ファイルのパスを取得"""
    return os.path.join(os.path.dirname(__file__), "..", "data", "option_trades.json")


def load_option_trades_local() -> List[Dict]:
    """
    オプション取引をローカルJSONから読み込み

    Returns:
        オプション取引のリスト
    """
    file_path = get_option_trades_file_path()

    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"WARNING: オプション取引の読み込みに失敗: {e}")
        return []


def save_option_trades_local(trades: List[Dict]) -> bool:
    """
    オプション取引をローカルJSONに保存

    Args:
        trades: オプション取引のリスト

    Returns:
        保存成功したかどうか
    """
    file_path = get_option_trades_file_path()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(trades, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"WARNING: オプション取引の保存に失敗: {e}")
        return False


def load_option_trades() -> List[Dict]:
    """
    オプション取引を読み込み（Google Sheets優先、フォールバックでローカルJSON）

    Returns:
        オプション取引のリスト
    """
    # Google Sheetsを試す
    try:
        import streamlit as st
        from src.simple_gsheets_client import get_simple_gsheets_client

        if st.secrets.get("USE_GSHEETS", False):
            client = get_simple_gsheets_client()
            if client:
                trades = client.load_option_trades()
                if trades:
                    return trades
    except Exception:
        pass

    # フォールバック: ローカルJSON
    return load_option_trades_local()


def add_option_trade(date: str, description: str, profit: float) -> bool:
    """
    オプション取引を追加

    Args:
        date: 取引日（YYYY-MM-DD）
        description: 取引内容
        profit: 損益（円）

    Returns:
        成功時True
    """
    trades = load_option_trades_local()

    trade = {
        "id": str(uuid.uuid4()),
        "date": date,
        "description": description,
        "profit": profit,
        "created_at": datetime.now().isoformat()
    }

    trades.append(trade)

    # 日付順にソート（新しい順）
    trades = sorted(trades, key=lambda x: x["date"], reverse=True)

    success = save_option_trades_local(trades)

    # Google Sheetsにも保存
    try:
        import streamlit as st
        from src.simple_gsheets_client import get_simple_gsheets_client

        if st.secrets.get("USE_GSHEETS", False):
            client = get_simple_gsheets_client()
            if client:
                client.save_option_trades(trades)
    except Exception as e:
        print(f"Google Sheetsへの保存に失敗: {e}")

    return success


def delete_option_trade(trade_id: str) -> bool:
    """
    オプション取引を削除

    Args:
        trade_id: 取引ID

    Returns:
        成功時True
    """
    trades = load_option_trades_local()
    trades = [t for t in trades if t["id"] != trade_id]

    success = save_option_trades_local(trades)

    # Google Sheetsにも保存
    try:
        import streamlit as st
        from src.simple_gsheets_client import get_simple_gsheets_client

        if st.secrets.get("USE_GSHEETS", False):
            client = get_simple_gsheets_client()
            if client:
                client.save_option_trades(trades)
    except Exception as e:
        print(f"Google Sheetsへの保存に失敗: {e}")

    return success


def calculate_option_profit() -> float:
    """
    オプション損益合計を計算

    Returns:
        損益合計（円）
    """
    trades = load_option_trades()
    return sum(t["profit"] for t in trades)
