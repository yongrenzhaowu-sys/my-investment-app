"""売買履歴管理"""
import json
import os
from typing import List, Dict
from datetime import datetime
import uuid
from .models import TradingRecord, calculate_tax, calculate_holding_days

# Google Sheets対応のためのインポート
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


def use_gsheets() -> bool:
    """Google Sheetsを使用するか判定"""
    if not STREAMLIT_AVAILABLE:
        return False

    try:
        return st.secrets.get("USE_GSHEETS", False)
    except:
        return False


def get_trading_history_path() -> str:
    """売買履歴ファイルのパスを取得"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(current_dir)
    data_dir = os.path.join(app_dir, "data")

    # dataディレクトリがなければ作成
    os.makedirs(data_dir, exist_ok=True)

    return os.path.join(data_dir, "trading_history.json")


def load_trading_history() -> List[Dict]:
    """
    売買履歴を読み込む（Google Sheets or ローカルJSON）

    Returns:
        売買履歴のリスト
    """
    # Google Sheetsを使用する場合
    if use_gsheets():
        try:
            from .simple_gsheets_client import get_simple_gsheets_client
            client = get_simple_gsheets_client()
            if client:
                return client.load_trading_history()
            else:
                # Google Sheetsが使えない場合はローカルにフォールバック
                return load_trading_history_local()
        except Exception as e:
            print(f"Google Sheetsからの読み込みエラー: {e}")
            return load_trading_history_local()
    else:
        # ローカルJSONから読み込み
        return load_trading_history_local()


def load_trading_history_local() -> List[Dict]:
    """
    ローカルJSONファイルから売買履歴を読み込む

    Returns:
        売買履歴のリスト
    """
    file_path = get_trading_history_path()

    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"売買履歴の読み込みエラー: {e}")
        return []


def save_trading_history(history: List[Dict]) -> bool:
    """
    売買履歴を保存（Google Sheets or ローカルJSON）

    Args:
        history: 売買履歴のリスト

    Returns:
        成功時True
    """
    # Google Sheetsを使用する場合
    if use_gsheets():
        try:
            from .simple_gsheets_client import get_simple_gsheets_client
            client = get_simple_gsheets_client()
            if client:
                client.save_trading_history(history)
                # ローカルにもバックアップ保存
                save_trading_history_local(history)
                return True
            else:
                # Google Sheetsが使えない場合はローカルに保存
                return save_trading_history_local(history)
        except Exception as e:
            print(f"Google Sheetsへの保存エラー: {e}")
            return save_trading_history_local(history)
    else:
        # ローカルJSONに保存
        return save_trading_history_local(history)


def save_trading_history_local(history: List[Dict]) -> bool:
    """
    ローカルJSONファイルに売買履歴を保存

    Args:
        history: 売買履歴のリスト

    Returns:
        成功時True
    """
    file_path = get_trading_history_path()

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"売買履歴の保存エラー: {e}")
        return False


def add_sell_record(
    hypothesis: Dict,
    sell_date: str,
    sell_price: float,
    sell_reason: str,
    sell_shares: int = None
) -> TradingRecord:
    """
    売却記録を追加

    Args:
        hypothesis: 仮説データ（保持中の銘柄）
        sell_date: 売却日（YYYY-MM-DD）
        sell_price: 売却価格（円/株）
        sell_reason: 売却理由
        sell_shares: 売却数量（株）。Noneの場合は全株売却

    Returns:
        TradingRecord オブジェクト
    """
    # 株数を取得（デフォルト100株）
    total_shares = hypothesis.get("shares", 100)

    # 売却数量（Noneの場合は全株）
    shares = sell_shares if sell_shares is not None else total_shares

    # NISA口座フラグを取得
    is_nisa = hypothesis.get("is_nisa", False)

    # 実現損益を計算（株数を考慮）
    purchase_price = hypothesis["purchase_price"]
    realized_profit_per_share = sell_price - purchase_price
    realized_profit = realized_profit_per_share * shares
    realized_profit_rate = (realized_profit_per_share / purchase_price) * 100 if purchase_price > 0 else 0

    # 税金を計算（NISA口座の場合は0%）
    tax_amount = calculate_tax(realized_profit, is_nisa=is_nisa)
    after_tax_profit = realized_profit - tax_amount

    # 保有日数を計算
    holding_days = calculate_holding_days(hypothesis["purchase_date"], sell_date)

    # TradingRecordを作成
    record = TradingRecord(
        id=str(uuid.uuid4()),
        code=hypothesis["code"],
        name=hypothesis.get("name", f"銘柄{hypothesis['code']}"),
        purchase_date=hypothesis["purchase_date"],
        purchase_price=purchase_price,
        shares=shares,
        purchase_reason=hypothesis["reason"],
        sell_date=sell_date,
        sell_price=sell_price,
        sell_reason=sell_reason,
        realized_profit=realized_profit,
        realized_profit_rate=realized_profit_rate,
        holding_days=holding_days,
        tax_amount=tax_amount,
        after_tax_profit=after_tax_profit,
        original_hypothesis_id=hypothesis["id"],
        created_at=hypothesis.get("created_at", datetime.now().isoformat()),
        sold_at=datetime.now().isoformat(),
        kpi_threshold=hypothesis.get("kpi_threshold"),
        is_nisa=is_nisa
    )

    # 履歴を読み込み、追加、保存
    history = load_trading_history()
    history.append(record.to_dict())
    save_trading_history(history)

    return record


def get_trading_history_by_year(year: int) -> List[Dict]:
    """
    指定年の売買履歴を取得

    Args:
        year: 年（例: 2026）

    Returns:
        指定年の売買履歴
    """
    history = load_trading_history()
    return [
        record for record in history
        if record["sell_date"].startswith(str(year))
    ]


def delete_trading_record(record_id: str) -> bool:
    """
    売買履歴を削除

    Args:
        record_id: レコードID

    Returns:
        成功時True
    """
    history = load_trading_history()
    updated_history = [r for r in history if r["id"] != record_id]

    if len(updated_history) == len(history):
        return False  # 削除対象が見つからなかった

    return save_trading_history(updated_history)
