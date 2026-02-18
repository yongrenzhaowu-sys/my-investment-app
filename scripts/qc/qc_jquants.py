"""
J-Quants データ品質チェック（QC）スクリプト

curated データの品質をチェックし、レポートを出力する。

Usage:
    python scripts/qc/qc_jquants.py [--dry-run] [--prices] [--financials]
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent

# パス
CURATED_PRICES_PATH = PROJECT_ROOT / "data/curated/jquants/prices/daily_quotes_all.parquet"
CURATED_FINS_PATH = PROJECT_ROOT / "data/curated/jquants/financials/statements_all.parquet"


class QCReport:
    """QCレポート"""

    def __init__(self):
        self.issues = []
        self.warnings = []

    def add_issue(self, category: str, message: str):
        """エラー追加"""
        self.issues.append(f"[{category}] {message}")

    def add_warning(self, category: str, message: str):
        """警告追加"""
        self.warnings.append(f"[{category}] {message}")

    def print_report(self):
        """レポート出力"""
        print("\n" + "="*60)
        print("QC レポート")
        print("="*60)

        if self.warnings:
            print(f"\n[WARN]  警告: {len(self.warnings)} 件")
            for w in self.warnings[:10]:  # 最大10件表示
                print(f"  - {w}")
            if len(self.warnings) > 10:
                print(f"  ... 他 {len(self.warnings) - 10} 件")

        if self.issues:
            print(f"\n[ERROR] エラー: {len(self.issues)} 件")
            for i in self.issues[:10]:
                print(f"  - {i}")
            if len(self.issues) > 10:
                print(f"  ... 他 {len(self.issues) - 10} 件")
        else:
            print("\n[OK] エラーなし")

        print("="*60)


def qc_prices(dry_run: bool = False):
    """価格データのQC"""
    print("\n=== 価格データQC ===")
    report = QCReport()

    if not CURATED_PRICES_PATH.exists():
        report.add_issue("FILE", f"Curated not found: {CURATED_PRICES_PATH}")
        return report

    df = pd.read_parquet(CURATED_PRICES_PATH)
    print(f"行数: {len(df):,}")

    # 1. 重複チェック
    duplicates = df.duplicated(subset=['date', 'code'], keep=False)
    if duplicates.any():
        dup_count = duplicates.sum()
        report.add_issue("DUPLICATE", f"{dup_count:,} 行の重複 (date, code)")

    # 2. 必須カラムの欠損チェック
    required_cols = ['date', 'code', 'close', 'volume']
    for col in required_cols:
        if col in df.columns:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                null_pct = (null_count / len(df)) * 100
                # date/codeはエラー、価格/出来高は警告（上場廃止等で正常）
                if col in ['date', 'code']:
                    report.add_issue("NULL", f"{col}: {null_count:,} 行の欠損 ({null_pct:.2f}%)")
                else:
                    report.add_warning("NULL", f"{col}: {null_count:,} 行の欠損 ({null_pct:.2f}%) - 上場廃止等で正常")

    # 3. 異常値チェック
    if 'close' in df.columns:
        invalid_close = (df['close'] <= 0) | (df['close'].isnull())
        if invalid_close.any():
            report.add_warning("ABNORMAL", f"close <= 0: {invalid_close.sum():,} 行")

    if 'volume' in df.columns:
        invalid_volume = (df['volume'] < 0) | (df['volume'].isnull())
        if invalid_volume.any():
            report.add_warning("ABNORMAL", f"volume < 0: {invalid_volume.sum():,} 行")

    # 4. 日付連続性チェック（簡易版）
    df_sorted = df.sort_values(['code', 'date'])
    sample_code = df_sorted['code'].iloc[0] if len(df_sorted) > 0 else None

    if sample_code:
        df_sample = df_sorted[df_sorted['code'] == sample_code].copy()
        df_sample['date'] = pd.to_datetime(df_sample['date'])
        date_diffs = df_sample['date'].diff().dt.days

        # 7日以上の空白を検出
        large_gaps = date_diffs[date_diffs > 7]
        if not large_gaps.empty:
            report.add_warning(
                "GAP",
                f"サンプル銘柄({sample_code})で7日以上の空白: {len(large_gaps)} 箇所"
            )

    # 5. 統計サマリ
    print(f"\n統計:")
    print(f"  期間: {df['date'].min()} ～ {df['date'].max()}")
    print(f"  銘柄数: {df['code'].nunique():,}")
    print(f"  総行数: {len(df):,}")

    if 'close' in df.columns:
        print(f"  close: min={df['close'].min():.2f}, max={df['close'].max():.2f}")

    return report


def qc_financials(dry_run: bool = False):
    """財務データのQC"""
    print("\n=== 財務データQC ===")
    report = QCReport()

    if not CURATED_FINS_PATH.exists():
        report.add_issue("FILE", f"Curated not found: {CURATED_FINS_PATH}")
        return report

    df = pd.read_parquet(CURATED_FINS_PATH)
    print(f"行数: {len(df):,}")

    # 1. 重複チェック
    key_cols = ['code', 'disclosed_date', 'disclosure_number']
    duplicates = df.duplicated(subset=key_cols, keep=False)
    if duplicates.any():
        dup_count = duplicates.sum()
        report.add_issue("DUPLICATE", f"{dup_count:,} 行の重複 ({', '.join(key_cols)})")

    # 2. 必須カラムの欠損チェック
    required_cols = ['code', 'disclosed_date']
    for col in required_cols:
        if col in df.columns:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                report.add_issue("NULL", f"{col}: {null_count:,} 行の欠損")

    # 3. 異常値チェック
    if 'total_assets' in df.columns:
        invalid_ta = df['total_assets'] < 0
        if invalid_ta.any():
            report.add_warning("ABNORMAL", f"total_assets < 0: {invalid_ta.sum():,} 行")

    if 'equity' in df.columns:
        # 自己資本マイナス（債務超過）は正常値として許容
        negative_equity = df['equity'] < 0
        if negative_equity.any():
            report.add_warning(
                "INFO",
                f"equity < 0 (債務超過): {negative_equity.sum():,} 行（正常値として許容）"
            )

    # 4. 未来参照チェック（簡易版）
    if 'disclosed_date' in df.columns and 'fiscal_year_end' in df.columns:
        df_check = df.dropna(subset=['disclosed_date', 'fiscal_year_end']).copy()
        df_check['disclosed_date'] = pd.to_datetime(df_check['disclosed_date'])
        df_check['fiscal_year_end'] = pd.to_datetime(df_check['fiscal_year_end'])

        # 通常は disclosed_date >= fiscal_year_end
        lookahead = df_check['disclosed_date'] < df_check['fiscal_year_end']
        if lookahead.any():
            report.add_warning(
                "LOOKAHEAD",
                f"disclosed_date < fiscal_year_end: {lookahead.sum():,} 行（要確認）"
            )

    # 5. 統計サマリ
    print(f"\n統計:")
    print(f"  期間: {df['disclosed_date'].min()} ～ {df['disclosed_date'].max()}")
    print(f"  銘柄数: {df['code'].nunique():,}")
    print(f"  総行数: {len(df):,}")

    if 'document_type' in df.columns:
        print(f"  文書タイプ:")
        doc_counts = df['document_type'].value_counts().head(5)
        for doc_type, count in doc_counts.items():
            print(f"    - {doc_type}: {count:,}")

    return report


def main():
    parser = argparse.ArgumentParser(description="J-Quants データ品質チェック")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run（現在は本番と同じ）")
    parser.add_argument("--prices", action="store_true", help="価格データのみQC")
    parser.add_argument("--financials", action="store_true", help="財務データのみQC")

    args = parser.parse_args()

    print(f"=== J-Quants データQC ===")
    print(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # デフォルト: 両方実行
        if not args.prices and not args.financials:
            args.prices = True
            args.financials = True

        reports = []

        if args.prices:
            reports.append(qc_prices(dry_run=args.dry_run))

        if args.financials:
            reports.append(qc_financials(dry_run=args.dry_run))

        # レポート出力
        for report in reports:
            report.print_report()

        # エラーがあれば終了コード1
        has_error = any(len(r.issues) > 0 for r in reports)
        if has_error:
            print("\n[ERROR] QC失敗: エラーを修正してください")
            sys.exit(1)
        else:
            print("\n[OK] QC成功")

    except Exception as e:
        print(f"\n[ERROR] エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
