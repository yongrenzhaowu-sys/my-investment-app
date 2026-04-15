"""RSS feed fetching with caching support."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import feedparser
import yaml

logger = logging.getLogger(__name__)


def load_rss_feeds(config_path: str = "config/rss_feeds.yaml") -> List[Dict]:
    """RSSフィード設定を読み込む。
    
    Args:
        config_path: 設定ファイルのパス
        
    Returns:
        フィード設定のリスト
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("feeds", [])


def fetch_rss_feed(feed_url: str, feed_name: str) -> Dict:
    """RSSフィードを取得する。
    
    Args:
        feed_url: フィードURL
        feed_name: フィード名
        
    Returns:
        取得結果（items, metadata）
    """
    logger.info(f"Fetching RSS feed: {feed_name} from {feed_url}")
    
    try:
        # feedparserでRSS取得
        parsed = feedparser.parse(feed_url)
        
        # ステータス確認
        if hasattr(parsed, "status") and parsed.status >= 400:
            logger.warning(f"HTTP error {parsed.status} for {feed_name}")
            return {
                "feed_name": feed_name,
                "feed_url": feed_url,
                "success": False,
                "error": f"HTTP {parsed.status}",
                "items": [],
                "fetched_at": datetime.now().isoformat(),
            }
        
        # エントリーを正規化
        items = []
        for entry in parsed.entries:
            item = {
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", ""),
                "content": "",
            }
            
            # content取得（存在する場合）
            if hasattr(entry, "content") and entry.content:
                item["content"] = entry.content[0].get("value", "")
            
            items.append(item)
        
        logger.info(f"Fetched {len(items)} items from {feed_name}")
        
        return {
            "feed_name": feed_name,
            "feed_url": feed_url,
            "success": True,
            "items": items,
            "fetched_at": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error fetching {feed_name}: {e}")
        return {
            "feed_name": feed_name,
            "feed_url": feed_url,
            "success": False,
            "error": str(e),
            "items": [],
            "fetched_at": datetime.now().isoformat(),
        }


def save_rss_data(data: Dict, output_dir: str, feed_name: str) -> Path:
    """RSSデータをJSONで保存する。
    
    Args:
        data: RSS取得結果
        output_dir: 保存先ディレクトリ（例: data/raw/rss/20260220）
        feed_name: フィード名
        
    Returns:
        保存先ファイルパス
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    file_path = output_path / f"{feed_name}.json"
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved RSS data to {file_path}")
    return file_path


def fetch_all_feeds(
    config_path: str = "config/rss_feeds.yaml",
    output_dir: Optional[str] = None,
) -> List[Dict]:
    """すべてのRSSフィードを取得して保存する。
    
    Args:
        config_path: RSSフィード設定ファイルのパス
        output_dir: 保存先ディレクトリ（Noneの場合は今日の日付で自動生成）
        
    Returns:
        取得結果のリスト
    """
    if output_dir is None:
        today = datetime.now().strftime("%Y%m%d")
        output_dir = f"data/raw/rss/{today}"
    
    feeds = load_rss_feeds(config_path)
    results = []
    
    for feed in feeds:
        feed_name = feed["name"]
        feed_url = feed["url"]
        
        # RSS取得
        data = fetch_rss_feed(feed_url, feed_name)
        
        # 保存
        save_rss_data(data, output_dir, feed_name)
        
        results.append(data)
    
    return results
