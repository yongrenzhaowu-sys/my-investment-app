"""設定管理モジュール"""
import json
import os
from typing import Dict, Any


DEFAULT_SETTINGS = {
    "initial_capital": 1_000_000,  # デフォルト: 100万円
}


def get_settings_file_path() -> str:
    """設定ファイルのパスを取得"""
    return os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")


def load_settings() -> Dict[str, Any]:
    """
    設定を読み込み

    Returns:
        設定辞書
    """
    file_path = get_settings_file_path()

    # ファイルが存在しない場合はデフォルト値を返す
    if not os.path.exists(file_path):
        return DEFAULT_SETTINGS.copy()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            settings = json.load(f)

        # デフォルト値とマージ（新しい設定項目が追加された場合に対応）
        merged_settings = DEFAULT_SETTINGS.copy()
        merged_settings.update(settings)

        return merged_settings

    except Exception as e:
        print(f"WARNING: 設定ファイルの読み込みに失敗: {e}")
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict[str, Any]) -> bool:
    """
    設定を保存

    Args:
        settings: 設定辞書

    Returns:
        保存成功したかどうか
    """
    file_path = get_settings_file_path()

    # dataディレクトリが存在しない場合は作成
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True

    except Exception as e:
        print(f"WARNING: 設定ファイルの保存に失敗: {e}")
        return False


def get_initial_capital() -> int:
    """
    初期資金を取得（Streamlit Secrets優先、フォールバックでファイル読み込み）

    Returns:
        初期資金（円）
    """
    # Streamlit Secretsを試す（Streamlit Cloud用）
    try:
        import streamlit as st
        initial_capital = st.secrets.get("initial_capital", None)
        if initial_capital is not None:
            return int(initial_capital)
    except Exception:
        pass

    # Secretsがない場合は、settings.jsonから読み込み（ローカル開発用）
    settings = load_settings()
    return int(settings.get("initial_capital", DEFAULT_SETTINGS["initial_capital"]))


def set_initial_capital(capital: float) -> bool:
    """
    初期資金を設定

    Args:
        capital: 初期資金（円）

    Returns:
        保存成功したかどうか
    """
    settings = load_settings()
    settings["initial_capital"] = capital
    return save_settings(settings)
