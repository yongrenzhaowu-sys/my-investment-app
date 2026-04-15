"""
J-Quants API V2で日次データを順次取得（確実版）

並列処理なし、1日ずつ確実に取得
推定所要時間: 270日 × 4秒 ≈ 18分
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import requests
from typing import Dict, Optional

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class JQuantsClient:
    """J-Quants API V2クライアント（順次処理）"""

    BASE_URL = "https://api.jquants.com/v2"

    def __init__(self):
        api_key = os.environ.get("JQUANTS_API_KEY")
        if not api_key:
            raise ValueError("環境変数 JQUANTS_API_KEY が設定されていません。")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": self.api_key})
        print(f"[INFO] APIキー設定完了")

    def get_daily_bars(self, date: str) -> Optional[pd.DataFrame]:
        """指定日の株価データを取得"""
        url = f"{self.BASE_URL}/equities/bars/daily"
        params = {"date": date}

        try:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()
            if data.get("data"):
                return pd.DataFrame(data["data"])
            return None

        except Exception as e:
            print(f"  [ERROR] 株価取得失敗: {e}")
            return None

    def get_financials(self, date: str) -> Optional[pd.DataFrame]:
        """指定日の財務データを取得"""
        url = f"{self.BASE_URL}/fins/summary"
        params = {"date": date}

        try:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()
            if data.get("data"):
                return pd.DataFrame(data["data"])
            return None

        except Exception as e:
            print(f"  [ERROR] 財務取得失敗: {e}")
            return None


def generate_business_days(start_date: str, end_date: str):
    """営業日リストを生成（土日を除外）"""
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")

    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # 月曜～金曜
            dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    return dates


def main():
    print("="*80)
    print("J-Quants API V2 - 日次データ順次取得（確実版）")
    print("="*80)

    # クライアント初期化
    try:
        client = JQuantsClient()
    except ValueError as e:
        print(f"[ERROR] {e}")
        return

    # 出力ディレクトリ
    output_dir = PROJECT_ROOT / "data/processed/jquants_latest_full"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 取得期間
    start_date = "20250301"
    end_date = "20260315"

    # 営業日生成
    business_days = generate_business_days(start_date, end_date)
    print(f"\n[INFO] 取得期間: {start_date} ~ {end_date}")
    print(f"[INFO] 営業日数: {len(business_days)}日")
    print(f"[INFO] 推定所要時間: {len(business_days) * 4 / 60:.1f}分")

    # 株価データ順次取得
    print("\n" + "="*80)
    print("株価データ順次取得開始")
    print("="*80)

    all_prices = []
    success_count = 0
    failed_dates = []

    start_time = time.time()

    for i, date in enumerate(business_days, 1):
        # 10件ごとに進捗表示
        if i % 10 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / i
            remaining = avg_time * (len(business_days) - i)
            print(f"[INFO] 進捗: {i}/{len(business_days)} ({i/len(business_days)*100:.1f}%) "
                  f"- 残り時間: {remaining/60:.1f}分")

        df = client.get_daily_bars(date)

        if df is not None and not df.empty:
            all_prices.append(df)
            success_count += 1
            if i % 10 == 0:
                print(f"  → {date}: {len(df)}レコード取得")
        else:
            failed_dates.append(date)
            if len(failed_dates) % 10 == 0:
                print(f"  [WARN] 失敗累計: {len(failed_dates)}日")

    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] 株価取得完了: {elapsed:.1f}秒 ({elapsed/60:.1f}分)")
    print(f"[INFO] 成功: {success_count}/{len(business_days)}日")
    print(f"[INFO] 失敗: {len(failed_dates)}日")

    # 失敗した日付を記録
    if failed_dates:
        failed_path = output_dir / "failed_dates_prices.txt"
        with open(failed_path, 'w') as f:
            f.write('\n'.join(failed_dates))
        print(f"[INFO] 失敗日付保存: {failed_path}")

    # 結合・保存
    if all_prices:
        print("[INFO] データ結合中...")
        df_prices = pd.concat(all_prices, ignore_index=True)

        prices_path = output_dir / "daily_bars_full.parquet"
        df_prices.to_parquet(prices_path, engine="pyarrow", index=False)

        print(f"[SUCCESS] 保存: {prices_path}")
        print(f"[INFO] レコード数: {len(df_prices):,}")
        print(f"[INFO] 銘柄数: {df_prices['Code'].nunique()}")
        print(f"[INFO] 期間: {df_prices['Date'].min()} ~ {df_prices['Date'].max()}")

    # 財務データ順次取得
    print("\n" + "="*80)
    print("財務データ順次取得開始")
    print("="*80)

    all_fins = []
    success_count = 0
    failed_dates_fins = []

    start_time = time.time()

    for i, date in enumerate(business_days, 1):
        if i % 10 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / i
            remaining = avg_time * (len(business_days) - i)
            print(f"[INFO] 進捗: {i}/{len(business_days)} ({i/len(business_days)*100:.1f}%) "
                  f"- 残り時間: {remaining/60:.1f}分")

        df = client.get_financials(date)

        if df is not None and not df.empty:
            all_fins.append(df)
            success_count += 1
            if i % 10 == 0 or len(df) > 0:
                print(f"  → {date}: {len(df)}レコード取得")
        else:
            failed_dates_fins.append(date)

    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] 財務取得完了: {elapsed:.1f}秒 ({elapsed/60:.1f}分)")
    print(f"[INFO] 成功: {success_count}/{len(business_days)}日")

    # 結合・保存
    if all_fins:
        print("[INFO] データ結合中...")
        df_fins = pd.concat(all_fins, ignore_index=True)

        # 重複除去
        df_fins = df_fins.drop_duplicates(subset=['Code', 'DiscDate'], keep='last')

        fins_path = output_dir / "financials_full.parquet"
        df_fins.to_parquet(fins_path, engine="pyarrow", index=False)

        print(f"[SUCCESS] 保存: {fins_path}")
        print(f"[INFO] レコード数: {len(df_fins):,}")
        print(f"[INFO] 銘柄数: {df_fins['Code'].nunique()}")
        if 'DiscDate' in df_fins.columns:
            print(f"[INFO] 開示日範囲: {df_fins['DiscDate'].min()} ~ {df_fins['DiscDate'].max()}")
    else:
        print("[WARN] 財務データが取得できませんでした")

    print("\n" + "="*80)
    print("完了")
    print("="*80)
    print(f"\n出力ディレクトリ: {output_dir}")
    print(f"\n次のステップ:")
    print(f"  python calculate_ff5_momentum_full.py")


if __name__ == "__main__":
    main()
