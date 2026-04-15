"""投資アイデアの抽出とスコアリング。"""
import hashlib
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 日本株の証券コードパターン（4桁数字）
TICKER_PATTERN = re.compile(r'\b(\d{4})\b')

# ポジティブキーワード（スコアリング用）
POSITIVE_KEYWORDS = [
    "増益", "増収", "好調", "過去最高", "上方修正", "黒字転換",
    "新製品", "新サービス", "提携", "買収", "M&A", "資本提携",
    "配当増", "自社株買い", "株式分割",
    "受注", "大型案件", "契約締結",
]

# ネガティブキーワード（除外用）
NEGATIVE_KEYWORDS = [
    "不正", "不祥事", "倒産", "破綻", "リコール",
    "業績下方修正", "減益", "赤字", "損失",
]


def extract_tickers(text: str) -> List[str]:
    """テキストから証券コード（4桁）を抽出する。
    
    Args:
        text: 検索対象テキスト
        
    Returns:
        証券コードのリスト（重複なし、ソート済み）
    """
    matches = TICKER_PATTERN.findall(text)
    # 重複削除、ソート
    tickers = sorted(set(matches))
    return tickers


def calculate_score(title: str, summary: str, content: str) -> float:
    """アイデアのスコアを計算する（0〜1）。
    
    Args:
        title: タイトル
        summary: 要約
        content: 本文
        
    Returns:
        スコア（0〜1の範囲）
    """
    text = f"{title} {summary} {content}".lower()
    
    # ネガティブキーワードチェック
    for keyword in NEGATIVE_KEYWORDS:
        if keyword in text:
            return 0.0  # 即座に除外
    
    # ポジティブキーワードカウント
    positive_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    
    # スコア計算（シンプルな正規化）
    # 最大5個のキーワードでスコア1.0とする
    score = min(positive_count / 5.0, 1.0)
    
    return score


def generate_idea_id(url: str, published: str) -> str:
    """アイデアの一意IDを生成する（URL + published_atのハッシュ）。
    
    Args:
        url: ソースURL
        published: 公開日時
        
    Returns:
        16文字のハッシュID
    """
    text = f"{url}_{published}"
    return hashlib.md5(text.encode()).hexdigest()[:16]


def extract_idea_from_item(item: Dict, feed_name: str) -> Optional[Dict]:
    """RSS itemから投資アイデアを抽出する。
    
    Args:
        item: RSSアイテム（title, link, published, summary, content）
        feed_name: フィード名
        
    Returns:
        投資アイデア辞書、または抽出失敗時はNone
    """
    title = item.get("title", "")
    link = item.get("link", "")
    published = item.get("published", "")
    summary = item.get("summary", "")
    content = item.get("content", "")
    
    # 証券コード抽出
    all_text = f"{title} {summary} {content}"
    tickers = extract_tickers(all_text)
    
    if not tickers:
        # 証券コードがない場合はスキップ
        logger.debug(f"No tickers found in: {title}")
        return None
    
    # スコア計算
    score = calculate_score(title, summary, content)
    
    if score == 0.0:
        # ネガティブキーワードで除外
        logger.debug(f"Negative keywords found in: {title}")
        return None
    
    # アイデアID生成
    idea_id = generate_idea_id(link, published)
    
    # アイデアデータ構築
    idea = {
        "id": idea_id,
        "source": feed_name,
        "source_url": link,
        "published_at": published,
        "title": title,
        "summary": summary[:500],  # 要約は500文字まで
        "tickers": tickers,
        "score": round(score, 3),
        "extracted_at": datetime.now().isoformat(),
    }
    
    return idea


def extract_ideas_from_rss_data(rss_data: Dict) -> List[Dict]:
    """RSSデータから投資アイデアを抽出する。
    
    Args:
        rss_data: RSS取得結果（fetch_rss_feedの戻り値）
        
    Returns:
        投資アイデアのリスト
    """
    if not rss_data.get("success", False):
        logger.warning(f"Skipping failed feed: {rss_data.get('feed_name')}")
        return []
    
    feed_name = rss_data["feed_name"]
    items = rss_data.get("items", [])
    
    ideas = []
    for item in items:
        idea = extract_idea_from_item(item, feed_name)
        if idea:
            ideas.append(idea)
    
    logger.info(f"Extracted {len(ideas)} ideas from {feed_name} ({len(items)} items)")
    return ideas


def extract_ideas_from_all_feeds(rss_results: List[Dict]) -> List[Dict]:
    """複数のRSS取得結果から投資アイデアを抽出する。
    
    Args:
        rss_results: RSS取得結果のリスト
        
    Returns:
        全フィードから抽出した投資アイデアのリスト
    """
    all_ideas = []
    for rss_data in rss_results:
        ideas = extract_ideas_from_rss_data(rss_data)
        all_ideas.extend(ideas)
    
    logger.info(f"Total ideas extracted: {len(all_ideas)}")
    return all_ideas
