"""セクター情報取得モジュール"""
from typing import Dict, List
import pandas as pd


# 33業種分類マスター
SECTOR_NAMES = {
    "0050": "水産・農林業",
    "1050": "鉱業",
    "2050": "建設業",
    "3050": "食料品",
    "3100": "繊維製品",
    "3150": "パルプ・紙",
    "3200": "化学",
    "3250": "医薬品",
    "3300": "石油・石炭製品",
    "3350": "ゴム製品",
    "3400": "ガラス・土石製品",
    "3450": "鉄鋼",
    "3500": "非鉄金属",
    "3550": "金属製品",
    "3600": "機械",
    "3650": "電気機器",
    "3700": "輸送用機器",
    "3750": "精密機器",
    "3800": "その他製品",
    "4050": "電気・ガス業",
    "5050": "情報・通信業",
    "5100": "運輸・郵便業",
    "5150": "卸売業",
    "5200": "小売業",
    "5250": "銀行業",
    "5300": "証券、商品先物取引業",
    "5350": "保険業",
    "5400": "その他金融業",
    "5450": "不動産業",
    "6050": "サービス業",
}


def get_sector_master(client) -> Dict[str, Dict]:
    """
    全銘柄のセクター情報を取得

    Args:
        client: J-Quants APIクライアント

    Returns:
        {
            "72030": {
                "code": "72030",
                "name": "スプリックス",
                "sector_code": "5050",
                "sector_name": "情報・通信業"
            },
            ...
        }
    """
    # 全銘柄の情報を取得
    companies = client.get_listed_companies()

    sector_master = {}

    for company in companies:
        code = company.get("Code")
        sector_code = company.get("Sector33Code")

        if code and sector_code:
            sector_master[code] = {
                "code": code,
                "name": company.get("CompanyName", ""),
                "sector_code": sector_code,
                "sector_name": SECTOR_NAMES.get(sector_code, "不明")
            }

    return sector_master


def get_stocks_by_sector(sector_master: Dict[str, Dict]) -> Dict[str, List[str]]:
    """
    セクターごとの銘柄コードリストを取得

    Args:
        sector_master: get_sector_master()の戻り値

    Returns:
        {
            "5050": ["72030", "43900", ...],  # 情報・通信業
            "6050": ["46890", ...],  # サービス業
            ...
        }
    """
    stocks_by_sector = {}

    for code, info in sector_master.items():
        sector_code = info["sector_code"]

        if sector_code not in stocks_by_sector:
            stocks_by_sector[sector_code] = []

        stocks_by_sector[sector_code].append(code)

    return stocks_by_sector


def get_sector_info(sector_code: str) -> Dict[str, str]:
    """
    セクター情報を取得

    Args:
        sector_code: セクターコード（例: "5050"）

    Returns:
        {
            "code": "5050",
            "name": "情報・通信業"
        }
    """
    return {
        "code": sector_code,
        "name": SECTOR_NAMES.get(sector_code, "不明")
    }
