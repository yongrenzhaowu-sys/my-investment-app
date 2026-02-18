"""
Legacy J-Quants データ統合スクリプト

legacy/_inbox/jquants_*_10y_parquet/ のパーティションデータを統合し、
data/curated/jquants/ に保存する（初回のみ）。

Usage:
    python scripts/ingest/consolidate_legacy.py [--dry-run] [--prices] [--financials]
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Legacy パス
LEGACY_PRICES_DIR = PROJECT_ROOT / "legacy/_inbox/jquants_daily_bars_10y_parquet/daily_parquet"
LEGACY_FINS_DIR = PROJECT_ROOT / "legacy/_inbox/jquants_fins_summary_10y_parquet/daily_parquet"

# Curated パス
CURATED_PRICES_PATH = PROJECT_ROOT / "data/curated/jquants/prices/daily_quotes_all.parquet"
CURATED_FINS_PATH = PROJECT_ROOT / "data/curated/jquants/financials/statements_all.parquet"


def get_partition_files(legacy_dir: Path, dry_run: bool = False):
    """パーティションファイル一覧を取得"""
    if not legacy_dir.exists():
        raise FileNotFoundError(f"Legacy directory not found: {legacy_dir}")

    all_files = sorted(legacy_dir.glob("date=*.parquet"))

    if dry_run:
        # dry-run: 最新1ヶ月分のみ
        cutoff_date = datetime.now() - timedelta(days=30)
        files = [
            f for f in all_files
            if datetime.strptime(f.stem.replace("date=", ""), "%Y-%m-%d") >= cutoff_date
        ]
        print(f"[DRY-RUN] 最新1ヶ月分のみ統合: {len(files)} files")
    else:
        # 本番: 全ファイル
        files = all_files
        print(f"全期間統合: {len(files)} files")

    return files


def consolidate_prices(dry_run: bool = False):
    """価格データを統合"""
    print("\n=== 価格データ統合開始 ===")

    # 既存チェック
    if CURATED_PRICES_PATH.exists():
        print(f"[WARN]  既存curated発見: {CURATED_PRICES_PATH}")
        print("スキップします（統合は初回のみ）")
        return

    # パーティション取得
    files = get_partition_files(LEGACY_PRICES_DIR, dry_run)
    if not files:
        print("[WARN]  パーティションファイルが見つかりません")
        return

    # 全ファイル読み込み
    print("読み込み中...")
    dfs = []
    for i, file in enumerate(files):
        if i % 100 == 0:
            print(f"  {i}/{len(files)} ...")
        df = pd.read_parquet(file)
        dfs.append(df)

    df_all = pd.concat(dfs, ignore_index=True)
    print(f"統合完了: {len(df_all):,} 行")

    # カラムリネーム（調整済み価格のみ使用）
    rename_map = {
        'Date': 'date',
        'Code': 'code',
        'AdjO': 'open',
        'AdjH': 'high',
        'AdjL': 'low',
        'AdjC': 'close',
        'AdjVo': 'volume'
    }

    df_clean = df_all[list(rename_map.keys())].rename(columns=rename_map)

    # 重複削除（後勝ち）
    before_count = len(df_clean)
    df_clean = df_clean.drop_duplicates(subset=['date', 'code'], keep='last')
    after_count = len(df_clean)
    print(f"重複削除: {before_count - after_count:,} 行削除")

    # ソート
    df_clean = df_clean.sort_values(['code', 'date']).reset_index(drop=True)

    # 統計表示
    print(f"\n統計情報:")
    print(f"  期間: {df_clean['date'].min()} ～ {df_clean['date'].max()}")
    print(f"  銘柄数: {df_clean['code'].nunique():,}")
    print(f"  総行数: {len(df_clean):,}")

    # 保存
    CURATED_PRICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(CURATED_PRICES_PATH, index=False)
    print(f"\n[OK] 保存完了: {CURATED_PRICES_PATH}")


def consolidate_financials(dry_run: bool = False):
    """財務データを統合"""
    print("\n=== 財務データ統合開始 ===")

    # 既存チェック
    if CURATED_FINS_PATH.exists():
        print(f"[WARN]  既存curated発見: {CURATED_FINS_PATH}")
        print("スキップします（統合は初回のみ）")
        return

    # パーティション取得
    files = get_partition_files(LEGACY_FINS_DIR, dry_run)
    if not files:
        print("[WARN]  パーティションファイルが見つかりません")
        return

    # 全ファイル読み込み
    print("読み込み中...")
    dfs = []
    for i, file in enumerate(files):
        if i % 100 == 0:
            print(f"  {i}/{len(files)} ...")
        df = pd.read_parquet(file)
        dfs.append(df)

    df_all = pd.concat(dfs, ignore_index=True)
    print(f"統合完了: {len(df_all):,} 行")

    # カラム選択（主要カラムのみ）
    selected_cols = [
        'DiscDate', 'DiscTime', 'Code', 'DiscNo', 'DocType',
        'CurPerType', 'CurPerSt', 'CurPerEn', 'CurFYSt', 'CurFYEn',
        'Sales', 'OP', 'OdP', 'NP', 'EPS', 'DEPS',
        'TA', 'Eq', 'EqAR', 'BPS',
        'FSales', 'FOP', 'FOdP', 'FNP', 'FEPS',
        'NxFSales', 'NxFOP', 'NxFOdP', 'NxFNP', 'NxFEPS',
        'DivAnn', 'FDivFY', 'NxFDivFY', 'PayoutRatioAnn'
    ]

    # 存在するカラムのみ選択
    available_cols = [c for c in selected_cols if c in df_all.columns]
    df_clean = df_all[available_cols].copy()

    # カラムリネーム
    rename_map = {
        'DiscDate': 'disclosed_date',
        'DiscTime': 'disclosed_time',
        'Code': 'code',
        'DiscNo': 'disclosure_number',
        'DocType': 'document_type',
        'CurPerType': 'fiscal_quarter',
        'CurFYEn': 'fiscal_year_end',
        'Sales': 'net_sales',
        'OP': 'operating_profit',
        'OdP': 'ordinary_profit',
        'NP': 'net_profit',
        'EPS': 'eps',
        'TA': 'total_assets',
        'Eq': 'equity',
        'EqAR': 'equity_ratio',
        'BPS': 'bps'
    }

    df_clean = df_clean.rename(columns={k: v for k, v in rename_map.items() if k in df_clean.columns})

    # 重複削除（後勝ち）
    key_cols = ['code', 'disclosed_date', 'disclosure_number']
    before_count = len(df_clean)
    df_clean = df_clean.drop_duplicates(subset=key_cols, keep='last')
    after_count = len(df_clean)
    print(f"重複削除: {before_count - after_count:,} 行削除")

    # ソート
    df_clean = df_clean.sort_values(['code', 'disclosed_date']).reset_index(drop=True)

    # 統計表示
    print(f"\n統計情報:")
    print(f"  期間: {df_clean['disclosed_date'].min()} ～ {df_clean['disclosed_date'].max()}")
    print(f"  銘柄数: {df_clean['code'].nunique():,}")
    print(f"  総行数: {len(df_clean):,}")

    # 保存
    CURATED_FINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(CURATED_FINS_PATH, index=False)
    print(f"\n[OK] 保存完了: {CURATED_FINS_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Legacy J-Quants データ統合")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run: 最新1ヶ月分のみ統合")
    parser.add_argument("--prices", action="store_true", help="価格データのみ統合")
    parser.add_argument("--financials", action="store_true", help="財務データのみ統合")

    args = parser.parse_args()

    print(f"=== Legacy データ統合 ===")
    print(f"モード: {'DRY-RUN' if args.dry_run else '本番'}")
    print(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # デフォルト: 両方実行
        if not args.prices and not args.financials:
            args.prices = True
            args.financials = True

        if args.prices:
            consolidate_prices(dry_run=args.dry_run)

        if args.financials:
            consolidate_financials(dry_run=args.dry_run)

        print("\n[OK] 統合完了")

    except Exception as e:
        print(f"\n[ERROR] エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
