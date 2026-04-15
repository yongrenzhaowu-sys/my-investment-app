"""投資アイデアのキュー管理。"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

QUEUE_FILE = "analyses/00_to_be_started/ideas.jsonl"


def load_queue() -> List[Dict]:
    """キューからアイデアを読み込む。
    
    Returns:
        アイデアのリスト
    """
    queue_path = Path(QUEUE_FILE)
    
    if not queue_path.exists():
        logger.info(f"Queue file not found, creating: {QUEUE_FILE}")
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        queue_path.touch()
        return []
    
    ideas = []
    with open(queue_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ideas.append(json.loads(line))
    
    logger.info(f"Loaded {len(ideas)} ideas from queue")
    return ideas


def save_queue(ideas: List[Dict]) -> None:
    """アイデアをキューに保存する。
    
    Args:
        ideas: アイデアのリスト
    """
    queue_path = Path(QUEUE_FILE)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(queue_path, "w", encoding="utf-8") as f:
        for idea in ideas:
            f.write(json.dumps(idea, ensure_ascii=False) + "\n")
    
    logger.info(f"Saved {len(ideas)} ideas to queue")


def get_existing_ids(ideas: List[Dict]) -> Set[str]:
    """既存アイデアのIDセットを取得する。
    
    Args:
        ideas: アイデアのリスト
        
    Returns:
        IDのセット
    """
    return {idea["id"] for idea in ideas}


def add_ideas_to_queue(new_ideas: List[Dict]) -> None:
    """新しいアイデアをキューに追加する（重複排除）。
    
    Args:
        new_ideas: 新しいアイデアのリスト
    """
    # 既存のキューを読み込み
    existing_ideas = load_queue()
    existing_ids = get_existing_ids(existing_ideas)
    
    # 重複を除外
    added_count = 0
    for idea in new_ideas:
        if idea["id"] not in existing_ids:
            existing_ideas.append(idea)
            existing_ids.add(idea["id"])
            added_count += 1
    
    # キューを保存
    save_queue(existing_ideas)
    
    logger.info(f"Added {added_count} new ideas to queue (skipped {len(new_ideas) - added_count} duplicates)")


def select_top_ideas(max_count: int, min_score: float = 0.0) -> List[Dict]:
    """キューから上位N件のアイデアを選択する。
    
    Args:
        max_count: 最大選択数
        min_score: 最低スコア
        
    Returns:
        選択されたアイデアのリスト
    """
    ideas = load_queue()
    
    # フィルタリング
    filtered_ideas = [idea for idea in ideas if idea.get("score", 0) >= min_score]
    
    # スコア順にソート（降順）
    sorted_ideas = sorted(filtered_ideas, key=lambda x: x.get("score", 0), reverse=True)
    
    # 上位N件を選択
    selected = sorted_ideas[:max_count]
    
    logger.info(f"Selected {len(selected)} ideas (max={max_count}, min_score={min_score})")
    return selected


def mark_idea_as_processed(idea_id: str) -> None:
    """アイデアを処理済みとしてマークする（キューから削除）。
    
    Args:
        idea_id: アイデアID
    """
    ideas = load_queue()
    remaining_ideas = [idea for idea in ideas if idea["id"] != idea_id]
    
    if len(remaining_ideas) < len(ideas):
        save_queue(remaining_ideas)
        logger.info(f"Marked idea {idea_id} as processed")
    else:
        logger.warning(f"Idea {idea_id} not found in queue")
