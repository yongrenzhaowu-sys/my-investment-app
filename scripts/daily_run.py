"""日次自動実行スクリプト。

このスクリプトは1日1回実行され、以下の処理を行う：
1. RSS取得
2. アイデア抽出・キュー投入
3. 上位N件を選択して分析
4. J-Quants APIで価格データ取得
5. イベントスタディ型バックテスト
6. 知見ファイル・日次レポート生成
"""
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml

# プロジェクトルートをPYTHONPATHに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rss.fetch import fetch_all_feeds
from src.ideas.extract import extract_ideas_from_all_feeds
from src.ideas.queue import add_ideas_to_queue, select_top_ideas, mark_idea_as_processed
from src.jquants.client import JQuantsClient
from src.data.cache import get_cached_or_fetch, cleanup_old_cache
from src.backtest.event_study import run_event_study, save_backtest_results
from src.reporting.daily_report import generate_daily_report
from src.knowledges.write_knowledge import generate_knowledge_file

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/daily_run.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/daily.yaml") -> dict:
    """設定ファイルを読み込む。"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_analysis_directory(idea: dict) -> Path:
    """分析ディレクトリを作成する。
    
    Args:
        idea: アイデア辞書
        
    Returns:
        分析ディレクトリのパス
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    # タイトルから安全なディレクトリ名を生成
    title = idea.get("title", "unknown")
    safe_title = "".join(c if c.isalnum() or c in (" ", "_") else "" for c in title)
    safe_title = safe_title[:50].strip().replace(" ", "_")
    
    dir_name = f"{timestamp}_{safe_title}"
    analysis_dir = Path("analyses") / dir_name
    analysis_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Created analysis directory: {analysis_dir}")
    return analysis_dir


def save_idea_file(idea: dict, analysis_dir: Path) -> None:
    """アイデアファイルを保存する。
    
    Args:
        idea: アイデア辞書
        analysis_dir: 分析ディレクトリ
    """
    idea_file = analysis_dir / "idea_01.md"
    
    lines = [
        f"# アイデア: {idea.get('title', 'Unknown')}\n\n",
        f"## 基本情報\n\n",
        f"- **ソース**: {idea.get('source', 'Unknown')}\n",
        f"- **URL**: {idea.get('source_url', 'N/A')}\n",
        f"- **公開日**: {idea.get('published_at', 'N/A')}\n",
        f"- **スコア**: {idea.get('score', 0):.3f}\n\n",
        f"## 対象銘柄\n\n",
        f"{', '.join(idea.get('tickers', []))}\n\n",
        f"## 要約\n\n",
        f"{idea.get('summary', '')}\n\n",
    ]
    
    with open(idea_file, "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    logger.info(f"Saved idea file: {idea_file}")


def main():
    """メイン処理。"""
    logger.info("=" * 60)
    logger.info("Daily automation started")
    logger.info("=" * 60)
    
    try:
        # 設定読み込み
        config = load_config()
        max_ideas = config.get("max_ideas_per_day", 1)
        min_score = config["filters"].get("min_score", 0.0)
        lookback_days = config["backtest"].get("lookback_days", 30)
        holding_days = config["backtest"].get("holding_days", [1, 3, 5])
        
        # ログディレクトリ作成
        Path("logs").mkdir(exist_ok=True)
        
        # ステップ1: RSS取得
        logger.info("Step 1: Fetching RSS feeds...")
        rss_results = fetch_all_feeds()
        
        # ステップ2: アイデア抽出
        logger.info("Step 2: Extracting investment ideas...")
        ideas = extract_ideas_from_all_feeds(rss_results)
        
        # ステップ3: キューに追加
        logger.info("Step 3: Adding ideas to queue...")
        if ideas:
            add_ideas_to_queue(ideas)
        
        # ステップ4: 上位N件を選択
        logger.info(f"Step 4: Selecting top {max_ideas} ideas...")
        selected_ideas = select_top_ideas(max_ideas, min_score)
        
        if not selected_ideas:
            logger.warning("No ideas selected for processing")
        
        # 処理済みアイデアとバックテスト結果を記録
        processed_ideas = []
        backtest_results = []
        
        # ステップ5: 各アイデアを処理
        for idea in selected_ideas:
            logger.info(f"Processing idea: {idea['id']} - {idea['title'][:50]}...")
            
            # 分析ディレクトリ作成
            analysis_dir = create_analysis_directory(idea)
            
            # アイデアファイル保存
            save_idea_file(idea, analysis_dir)
            
            # J-Quants APIで価格データ取得
            logger.info("Fetching price data from J-Quants...")
            client = JQuantsClient()
            
            # 日付範囲計算（イベント前後のデータ）
            # 実際のデータは2024年までなので、2024年のデータを使用
            to_date = datetime(2024, 12, 31)
            from_date = to_date - timedelta(days=lookback_days)

            from_date_str = from_date.strftime("%Y-%m-%d")
            to_date_str = to_date.strftime("%Y-%m-%d")
            
            # 各銘柄のデータを取得（キャッシュ優先）
            price_data = {}
            for code in idea["tickers"]:
                try:
                    df = get_cached_or_fetch(client, code, from_date_str, to_date_str)
                    price_data[code] = df
                except Exception as e:
                    logger.error(f"Failed to fetch data for {code}: {e}")
                    price_data[code] = None
            
            # バックテスト実行
            logger.info("Running event study backtest...")
            backtest_result = run_event_study(
                idea=idea,
                price_data=price_data,
                holding_days=holding_days,
            )
            
            # バックテスト結果を保存
            backtest_file = analysis_dir / "backtest_metrics.json"
            save_backtest_results(backtest_result, str(backtest_file))
            
            # 知見ファイル生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            safe_title = "".join(c if c.isalnum() or c in ("_",) else "" for c in idea["title"])[:30]
            knowledge_file = f"docs/knowledges/{timestamp}_{safe_title}.md"
            generate_knowledge_file(idea, backtest_result, knowledge_file)
            
            # 処理済みとしてマーク
            mark_idea_as_processed(idea["id"])
            
            processed_ideas.append(idea)
            backtest_results.append(backtest_result)
            
            logger.info(f"Completed processing idea: {idea['id']}")
        
        # ステップ6: 日次レポート生成
        logger.info("Step 6: Generating daily report...")
        today = datetime.now().strftime("%Y%m%d")
        report_file = f"docs/reports/{today}.md"
        generate_daily_report(
            rss_results=rss_results,
            ideas=ideas,
            processed_ideas=processed_ideas,
            backtest_results=backtest_results,
            output_path=report_file,
        )
        
        # キャッシュクリーンアップ
        logger.info("Cleaning up old cache...")
        cleanup_old_cache(retention_days=30)
        
        logger.info("=" * 60)
        logger.info("Daily automation completed successfully")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Daily automation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
