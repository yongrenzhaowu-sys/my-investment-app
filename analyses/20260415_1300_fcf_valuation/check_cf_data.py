"""
キャッシュフローデータの確認

J-Quants APIの財務データにCFO, CFI, CashEq列が存在するか確認
"""

import pandas as pd
from pathlib import Path

# データパス
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "jquants_historical_6years"

FINANCIALS_PATH = DATA_DIR / "financials_2021_2026.parquet"

def check_cf_data():
    """CFデータの確認"""
    print("=" * 80)
    print("キャッシュフローデータの確認")
    print("=" * 80)

    # 財務データ読み込み
    financials = pd.read_parquet(FINANCIALS_PATH)

    print(f"\n財務データ: {len(financials):,}レコード")
    print(f"銘柄数: {financials['Code'].nunique()}")

    # 列の確認
    print(f"\n利用可能な列:")
    print(financials.columns.tolist())

    # CFデータの確認
    cf_columns = {
        'CFO': '営業キャッシュフロー',
        'CFI': '投資キャッシュフロー',
        'CFF': '財務キャッシュフロー',
        'CashEq': '現金及び現金同等物',
    }

    print(f"\n{'='*80}")
    print("CFデータの存在確認")
    print(f"{'='*80}")

    available_cf_cols = []

    for col, desc in cf_columns.items():
        if col in financials.columns:
            print(f"[OK] {col} ({desc}): 存在")
            available_cf_cols.append(col)
        else:
            print(f"[NG] {col} ({desc}): 存在しない")

    if len(available_cf_cols) == 0:
        print("\nERROR: CFデータが存在しません")
        return

    # データの欠損率
    print(f"\n{'='*80}")
    print("データの欠損率")
    print(f"{'='*80}")

    for col in available_cf_cols:
        null_rate = financials[col].isnull().mean()
        print(f"{col}: {null_rate:.2%}")

    # 数値型への変換確認
    print(f"\n{'='*80}")
    print("データ型確認")
    print(f"{'='*80}")

    for col in available_cf_cols:
        print(f"{col}: {financials[col].dtype}")

    # 数値に変換
    for col in available_cf_cols:
        financials[col] = pd.to_numeric(financials[col], errors='coerce')

    # 変換後の欠損率
    print(f"\n数値変換後の欠損率:")
    for col in available_cf_cols:
        null_rate = financials[col].isnull().mean()
        print(f"{col}: {null_rate:.2%}")

    # FCF計算可能か確認
    if 'CFO' in available_cf_cols and 'CFI' in available_cf_cols:
        print(f"\n{'='*80}")
        print("FCF計算")
        print(f"{'='*80}")

        # FCF = CFO - CFI
        financials['FCF'] = financials['CFO'] - financials['CFI']

        # FCFの欠損率
        fcf_null_rate = financials['FCF'].isnull().mean()
        print(f"FCF欠損率: {fcf_null_rate:.2%}")

        # FCF > 0の割合
        fcf_positive_rate = (financials['FCF'] > 0).mean()
        print(f"FCF > 0の割合: {fcf_positive_rate:.2%}")

        # FCF統計
        print(f"\nFCF統計:")
        print(financials['FCF'].describe())

        # サンプルデータ（FCF > 0）
        print(f"\nFCF > 0のサンプルデータ（10件）:")
        fcf_positive = financials[financials['FCF'] > 0].copy()
        print(fcf_positive[['Code', 'CFO', 'CFI', 'FCF', 'CashEq']].head(10).to_string(index=False))

    else:
        print("\nERROR: FCF計算に必要なデータ（CFO, CFI）が存在しません")

    # 現金データの確認
    if 'CashEq' in available_cf_cols:
        print(f"\n{'='*80}")
        print("現金データ")
        print(f"{'='*80}")

        # 現金 > 0の割合
        cash_positive_rate = (financials['CashEq'] > 0).mean()
        print(f"現金 > 0の割合: {cash_positive_rate:.2%}")

        # 現金統計
        print(f"\n現金統計:")
        print(financials['CashEq'].describe())

    # 最新データ（2026年3月時点）の確認
    print(f"\n{'='*80}")
    print("最新データ（2026-03-31以前）")
    print(f"{'='*80}")

    financials['DiscDate'] = pd.to_datetime(financials['DiscDate'])
    latest_data = financials[financials['DiscDate'] <= '2026-03-31']

    print(f"最新データ件数: {len(latest_data):,}レコード")
    print(f"銘柄数: {latest_data['Code'].nunique()}")

    if 'FCF' in latest_data.columns:
        fcf_positive_latest = latest_data[latest_data['FCF'] > 0]
        print(f"FCF > 0の銘柄数: {fcf_positive_latest['Code'].nunique()}")

    print(f"\n{'='*80}")
    print("完了")
    print(f"{'='*80}")

if __name__ == "__main__":
    check_cf_data()
