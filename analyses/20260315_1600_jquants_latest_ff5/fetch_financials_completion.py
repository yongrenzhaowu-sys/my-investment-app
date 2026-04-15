"""
財務データの完全取得（2025-07-26 ~ 2026-03-15）

CMAファクター計算のため、不足している財務データを取得する。
レート制限対策: 1リクエスト/秒、100リクエストごとに60秒休憩
推定所要時間: 250日分 × 1秒 + 休憩 ≈ 5分
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import requests
from typing import Dict, Optional, List

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class JQuantsFinancialsClient:
    """J-Quants API V2財務データクライアント"""

    BASE_URL = "https://api.jquants.com/v2"

    def __init__(self):
        api_key = os.environ.get("JQUANTS_API_KEY")
        if not api_key:
            raise ValueError("環境変数 JQUANTS_API_KEY が設定されていません。")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": self.api_key})
        print(f"[INFO] APIキー設定完了")

    def get_financials_by_date(self, date: str) -> Optional[List[Dict]]:
        """指定日に開示された財務データを取得"""
        url = f"{self.BASE_URL}/fins/summary"
        params = {"date": date}

        try:
            response = self.session.get(url, params=params, timeout=60)

            if response.status_code == 429:
                print(f"  [WARNING] レート制限（429）。60秒待機...")
                time.sleep(60)
                # 再試行
                response = self.session.get(url, params=params, timeout=60)

            response.raise_for_status()

            data = response.json()
            if data.get("data"):
                return data["data"]
            return None

        except Exception as e:
            print(f"  [ERROR] 財務データ取得失敗: {e}")
            return None

    def close(self):
        """セッションを閉じる"""
        self.session.close()


def load_existing_financials() -> pd.DataFrame:
    """既存の財務データを読み込み"""
    parquet_path = PROJECT_ROOT / "data" / "processed" / "jquants_latest_full" / "financials_full.parquet"

    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        print(f"[INFO] 既存データ読み込み: {len(df)}件")
        print(f"[INFO] 期間: {df['DiscDate'].min()} ~ {df['DiscDate'].max()}")
        return df
    else:
        print(f"[WARNING] 既存データが見つかりません: {parquet_path}")
        return pd.DataFrame()


def save_financials(df: pd.DataFrame):
    """財務データを保存"""
    output_dir = PROJECT_ROOT / "data" / "processed" / "jquants_latest_full"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "financials_full.parquet"
    df.to_parquet(output_path, index=False)
    print(f"[INFO] 保存完了: {output_path}")
    print(f"[INFO] 件数: {len(df)}件")


def save_progress(new_records: List[Dict], progress_file: Path):
    """進捗を保存（途中経過）"""
    if new_records:
        df_progress = pd.DataFrame(new_records)
        df_progress.to_csv(progress_file, index=False)
        print(f"[INFO] 進捗保存: {len(new_records)}件（{progress_file}）")


def load_progress(progress_file: Path) -> List[Dict]:
    """進捗を読み込み"""
    if progress_file.exists():
        df_progress = pd.read_csv(progress_file)
        records = df_progress.to_dict('records')
        print(f"[INFO] 進捗読み込み: {len(records)}件")
        return records
    return []


def fetch_financials_completion(start_date: str, end_date: str):
    """
    財務データの完全取得

    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
    """
    print("=" * 80)
    print("財務データ完全取得開始")
    print("=" * 80)
    print(f"期間: {start_date} ~ {end_date}")

    # 進捗ファイル
    progress_file = PROJECT_ROOT / "data" / "processed" / "jquants_latest_full" / "financials_progress.csv"

    # 既存の進捗を読み込み
    new_records = load_progress(progress_file)

    # 既存データを読み込み
    existing_df = load_existing_financials()

    # クライアント初期化
    client = JQuantsFinancialsClient()

    # 日付範囲を生成
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    date_range = pd.date_range(start=start, end=end, freq='D')

    print(f"[INFO] 取得対象日数: {len(date_range)}日")
    print("-" * 80)

    request_count = 0
    success_count = 0
    error_count = 0

    try:
        for i, date in enumerate(date_range):
            date_str = date.strftime('%Y-%m-%d')

            # 進捗表示
            if (i + 1) % 10 == 0:
                print(f"[進捗] {i + 1}/{len(date_range)}日完了（成功: {success_count}件、エラー: {error_count}件）")

            # APIリクエスト
            records = client.get_financials_by_date(date_str)
            request_count += 1

            if records:
                new_records.extend(records)
                success_count += 1
                print(f"  {date_str}: {len(records)}件取得")
            else:
                error_count += 1

            # レート制限対策: 100リクエストごとに60秒休憩
            if request_count % 100 == 0:
                print(f"[INFO] {request_count}リクエスト完了。60秒休憩...")
                # 進捗を保存
                save_progress(new_records, progress_file)
                time.sleep(60)
            else:
                # 通常は1秒待機
                time.sleep(1)

            # 10日ごとに進捗を保存
            if (i + 1) % 10 == 0:
                save_progress(new_records, progress_file)

    except KeyboardInterrupt:
        print("\n[WARNING] ユーザーによる中断")
        print("[INFO] 進捗を保存します...")
        save_progress(new_records, progress_file)
        client.close()
        return

    except Exception as e:
        print(f"\n[ERROR] 予期しないエラー: {e}")
        print("[INFO] 進捗を保存します...")
        save_progress(new_records, progress_file)
        client.close()
        raise

    finally:
        client.close()

    print("-" * 80)
    print(f"[INFO] 取得完了: 成功 {success_count}日、エラー {error_count}日")
    print(f"[INFO] 新規レコード: {len(new_records)}件")

    # 新規データをDataFrameに変換
    if new_records:
        new_df = pd.DataFrame(new_records)
        print(f"[INFO] 新規データ: {len(new_df)}件")

        # 既存データと結合
        if not existing_df.empty:
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            print(f"[INFO] 既存データ: {len(existing_df)}件")
        else:
            combined_df = new_df

        # 重複削除（Code, DiscDate, CurPerEnで一意）
        before_count = len(combined_df)
        combined_df = combined_df.drop_duplicates(subset=['Code', 'DiscDate', 'CurPerEn'], keep='last')
        after_count = len(combined_df)
        duplicates_removed = before_count - after_count

        if duplicates_removed > 0:
            print(f"[INFO] 重複削除: {duplicates_removed}件")

        # DiscDateでソート
        combined_df = combined_df.sort_values('DiscDate').reset_index(drop=True)

        print(f"[INFO] 最終データ: {len(combined_df)}件")
        print(f"[INFO] 期間: {combined_df['DiscDate'].min()} ~ {combined_df['DiscDate'].max()}")

        # 保存
        save_financials(combined_df)

        # 進捗ファイルを削除
        if progress_file.exists():
            progress_file.unlink()
            print(f"[INFO] 進捗ファイル削除: {progress_file}")
    else:
        print("[WARNING] 新規データがありません")

    print("=" * 80)
    print("完了！")
    print("=" * 80)


if __name__ == "__main__":
    # 不足期間を取得
    START_DATE = "2025-07-26"
    END_DATE = "2026-03-15"

    fetch_financials_completion(START_DATE, END_DATE)
