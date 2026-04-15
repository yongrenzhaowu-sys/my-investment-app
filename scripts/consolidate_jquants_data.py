#!/usr/bin/env python3
"""
J-Quantsデータ統合スクリプト（AdjustmentClose対応版）

data/fetched/ から data/curated/jquants/ へデータを統合
- 日足データ: AdjustmentClose（調整後終値）を含める
- 財務データ: 必要な列を抽出・正規化

使用例:
    python scripts/consolidate_jquants_data.py
"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
FETCHED_DIR = PROJECT_ROOT / "data" / "fetched"
CURATED_DIR = PROJECT_ROOT / "data" / "curated" / "jquants"

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def consolidate_daily_bars():
    """
    日足データを統合（AdjustmentClose含む）

    重要：
    - AdjustmentClose（調整後終値）を使用することで、株式分割・併合の影響を除去
    - バックテスト時は必ずAdjustmentCloseを使用すること
    """
    logger.info("=== 日足データ統合開始 ===")

    # legacy/_inboxから読み込む（約10年分のデータ）
    daily_dir = PROJECT_ROOT / "legacy" / "_inbox" / "jquants_daily_bars_10y_parquet" / "daily_parquet"
    if not daily_dir.exists():
        logger.error(f"データディレクトリが存在しません: {daily_dir}")
        return

    # 全parquetファイルを読み込み
    parquet_files = sorted(daily_dir.glob("*.parquet"))
    logger.info(f"対象ファイル数: {len(parquet_files)}")

    if not parquet_files:
        logger.warning("parquetファイルが見つかりません")
        return

    dfs = []
    for i, file in enumerate(parquet_files):
        if i % 100 == 0:
            logger.info(f"読み込み進捗: {i}/{len(parquet_files)}")

        df = pd.read_parquet(file)
        dfs.append(df)

    # 統合
    df_all = pd.concat(dfs, ignore_index=True)
    logger.info(f"統合完了: {len(df_all):,} 行")

    # 列名を小文字に正規化（分析コードとの整合性のため）
    # legacy/_inboxとdata/fetchedの両方に対応
    column_map = {
        'Date': 'date',
        'Code': 'code',
        'O': 'open',
        'Open': 'open',
        'H': 'high',
        'High': 'high',
        'L': 'low',
        'Low': 'low',
        'C': 'close',
        'Close': 'close',
        'Vo': 'volume',
        'Volume': 'volume',
        'AdjO': 'adjusted_open',
        'AdjustedOpen': 'adjusted_open',
        'AdjustmentOpen': 'adjusted_open',
        'AdjH': 'adjusted_high',
        'AdjustedHigh': 'adjusted_high',
        'AdjustmentHigh': 'adjusted_high',
        'AdjL': 'adjusted_low',
        'AdjustedLow': 'adjusted_low',
        'AdjustmentLow': 'adjusted_low',
        'AdjC': 'adjusted_close',
        'AdjustedClose': 'adjusted_close',  # ← 重要！
        'AdjustmentClose': 'adjusted_close',  # ← 重要！
        'AdjVo': 'adjusted_volume',
        'AdjustedVolume': 'adjusted_volume',
        'AdjustmentVolume': 'adjusted_volume',
        'AdjFactor': 'adjustment_factor',
        'AdjustmentFactor': 'adjustment_factor'
    }

    # 利用可能な列のみ変換
    rename_dict = {k: v for k, v in column_map.items() if k in df_all.columns}
    df_all = df_all.rename(columns=rename_dict)

    # 重複列の処理（複数のソースから同じ名前にマッピングされた場合）
    # 最初の列を優先して残す
    df_all = df_all.loc[:, ~df_all.columns.duplicated()]

    # 必要な列のみ抽出
    # 重要：adjusted_close（調整後終値）を含める
    required_columns = ['date', 'code', 'open', 'high', 'low', 'close',
                       'volume', 'adjusted_close', 'adjustment_factor']

    available_columns = [col for col in required_columns if col in df_all.columns]
    df_all = df_all[available_columns].copy()

    logger.info(f"抽出列: {available_columns}")

    # データ型変換
    df_all['date'] = pd.to_datetime(df_all['date'])
    df_all['code'] = df_all['code'].astype(str)

    # ソート
    df_all = df_all.sort_values(['date', 'code']).reset_index(drop=True)

    # 保存
    output_dir = CURATED_DIR / "prices"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "daily_quotes_all.parquet"

    df_all.to_parquet(output_file, engine="pyarrow", index=False)
    logger.info(f"保存完了: {output_file}")
    logger.info(f"期間: {df_all['date'].min()} ~ {df_all['date'].max()}")
    logger.info(f"銘柄数: {df_all['code'].nunique():,}")
    logger.info(f"総レコード数: {len(df_all):,}")

    # adjusted_closeとcloseの比較サンプル
    if 'adjusted_close' in df_all.columns and 'close' in df_all.columns:
        logger.info("\n=== Close vs AdjustedClose サンプル ===")
        sample = df_all[df_all['code'] == df_all['code'].iloc[0]].head(10)
        logger.info(f"\n{sample[['date', 'code', 'close', 'adjusted_close', 'adjustment_factor']]}")

        # 調整率の統計
        if 'adjustment_factor' in df_all.columns:
            df_all['adjust_ratio'] = df_all['adjusted_close'] / df_all['close']
            logger.info(f"\n調整率の統計:")
            logger.info(f"{df_all['adjust_ratio'].describe()}")

            # 調整が行われている銘柄数
            adjusted_stocks = df_all[df_all['adjust_ratio'] != 1.0]['code'].nunique()
            logger.info(f"調整が行われている銘柄数: {adjusted_stocks:,}")

    logger.info("=== 日足データ統合完了 ===\n")


def consolidate_fins_data():
    """
    財務データを統合
    """
    logger.info("=== 財務データ統合開始 ===")

    # legacy/_inboxから読み込む（約10年分のデータ）
    # 正規化済みディレクトリを優先
    fins_dir = PROJECT_ROOT / "legacy" / "_inbox" / "jquants_fins_summary_10y_parquet" / "daily_parquet_norm"
    if not fins_dir.exists():
        # フォールバック: 通常のディレクトリ
        fins_dir = PROJECT_ROOT / "legacy" / "_inbox" / "jquants_fins_summary_10y_parquet" / "daily_parquet"

    if not fins_dir.exists():
        logger.error(f"データディレクトリが存在しません: {fins_dir}")
        return

    # 全parquetファイルを読み込み
    parquet_files = sorted(fins_dir.glob("*.parquet"))
    logger.info(f"対象ファイル数: {len(parquet_files)}")

    if not parquet_files:
        logger.warning("parquetファイルが見つかりません")
        return

    dfs = []
    for i, file in enumerate(parquet_files):
        if i % 100 == 0:
            logger.info(f"読み込み進捗: {i}/{len(parquet_files)}")

        df = pd.read_parquet(file)
        dfs.append(df)

    # 統合
    df_all = pd.concat(dfs, ignore_index=True)
    logger.info(f"統合完了: {len(df_all):,} 行")

    # 列名を小文字に正規化
    column_map = {
        'Date': 'disclosed_date',
        'Code': 'code',
        'DisclosedDate': 'disclosed_date',
        'DisclosedTime': 'disclosed_time',
        'DisclosureNumber': 'disclosure_number',
        'TypeOfDocument': 'document_type',
        'TypeOfCurrentPeriod': 'fiscal_quarter',
        'CurrentPeriodStartDate': 'CurPerSt',
        'CurrentPeriodEndDate': 'CurPerEn',
        'CurrentFiscalYearStartDate': 'CurFYSt',
        'CurrentFiscalYearEndDate': 'fiscal_year_end',
        'NetSales': 'net_sales',
        'OperatingProfit': 'operating_profit',
        'OrdinaryProfit': 'ordinary_profit',
        'Profit': 'net_profit',
        'EarningsPerShare': 'eps',
        'DilutedEarningsPerShare': 'DEPS',
        'TotalAssets': 'total_assets',
        'NetAssets': 'equity',
        'EquityToAssetRatio': 'equity_ratio',
        'BookValuePerShare': 'bps',
        'ForecastNetSales': 'FSales',
        'ForecastOperatingProfit': 'FOP',
        'ForecastOrdinaryProfit': 'FOdP',
        'ForecastProfit': 'FNP',
        'ForecastEarningsPerShare': 'FEPS',
        'NextYearForecastNetSales': 'NxFSales',
        'NextYearForecastOperatingProfit': 'NxFOP',
        'NextYearForecastOrdinaryProfit': 'NxFOdP',
        'NextYearForecastEarningsPerShare': 'NxFEPS',
        'AnnualDividendPerShare': 'DivAnn',
        'ForecastDividendPerShare': 'FDivFY',
        'NextYearForecastDividendPerShare': 'NxFDivFY',
        'AnnualDividendPayoutRatio': 'PayoutRatioAnn'
    }

    # 利用可能な列のみ変換
    rename_dict = {k: v for k, v in column_map.items() if k in df_all.columns}
    df_all = df_all.rename(columns=rename_dict)

    # データ型変換
    if 'disclosed_date' in df_all.columns:
        df_all['disclosed_date'] = pd.to_datetime(df_all['disclosed_date'])
    df_all['code'] = df_all['code'].astype(str)

    # ソート
    df_all = df_all.sort_values(['disclosed_date', 'code']).reset_index(drop=True)

    # 保存
    output_dir = CURATED_DIR / "financials"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "statements_all.parquet"

    df_all.to_parquet(output_file, engine="pyarrow", index=False)
    logger.info(f"保存完了: {output_file}")

    if 'disclosed_date' in df_all.columns:
        logger.info(f"期間: {df_all['disclosed_date'].min()} ~ {df_all['disclosed_date'].max()}")
    logger.info(f"銘柄数: {df_all['code'].nunique():,}")
    logger.info(f"総レコード数: {len(df_all):,}")

    # fiscal_quarter分布
    if 'fiscal_quarter' in df_all.columns:
        logger.info(f"\nfiscal_quarter分布:")
        logger.info(f"{df_all['fiscal_quarter'].value_counts().sort_index()}")

    logger.info("=== 財務データ統合完了 ===\n")


def main():
    """メイン処理"""
    logger.info("=" * 80)
    logger.info("J-Quantsデータ統合スクリプト（AdjustmentClose対応版）")
    logger.info("=" * 80)
    logger.info(f"実行日時: {datetime.now()}")
    logger.info(f"入力: {FETCHED_DIR}")
    logger.info(f"出力: {CURATED_DIR}")
    logger.info("=" * 80)
    logger.info("")

    # 日足データ統合
    consolidate_daily_bars()

    # 財務データ統合
    consolidate_fins_data()

    logger.info("=" * 80)
    logger.info("全ての統合処理が完了しました")
    logger.info("=" * 80)
    logger.info("")
    logger.info("次のステップ:")
    logger.info("1. Notebookで 'close' → 'adjusted_close' に変更")
    logger.info("2. バックテストを再実行")
    logger.info("3. パフォーマンスを比較")


if __name__ == "__main__":
    main()
