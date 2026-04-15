"""Idea Deduplication
投資アイデアの重複排除
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Set
import logging

logger = logging.getLogger(__name__)


def load_ideas_from_jsonl(filepath: str) -> List[Dict[str, Any]]:
    """
    JSONLファイルからアイデアを読み込む

    Args:
        filepath: JSONLファイルパス

    Returns:
        アイデアのリスト
    """
    ideas = []
    path = Path(filepath)

    if not path.exists():
        logger.warning(f"File not found: {filepath}")
        return ideas

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    idea = json.loads(line)
                    ideas.append(idea)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON line: {e}")

    return ideas


def get_existing_idea_ids(ideas_queue_path: str = "analyses/00_to_be_started/ideas.jsonl") -> Set[str]:
    """
    既存のアイデアキューからIDセットを取得

    Args:
        ideas_queue_path: アイデアキューのファイルパス

    Returns:
        既存のアイデアIDセット
    """
    existing_ideas = load_ideas_from_jsonl(ideas_queue_path)
    return {idea['id'] for idea in existing_ideas if 'id' in idea}


def deduplicate_ideas(
    new_ideas: List[Dict[str, Any]],
    existing_ids: Set[str]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    新規アイデアから重複を排除

    Args:
        new_ideas: 新規アイデアのリスト
        existing_ids: 既存のアイデアIDセット

    Returns:
        (unique_ideas, duplicate_ideas) のタプル
    """
    unique_ideas = []
    duplicate_ideas = []

    for idea in new_ideas:
        idea_id = idea.get('id')

        if not idea_id:
            logger.warning("Idea without ID found, skipping")
            continue

        if idea_id in existing_ids:
            duplicate_ideas.append(idea)
            logger.debug(f"Duplicate idea: {idea_id} - {idea.get('title', '')}")
        else:
            unique_ideas.append(idea)
            existing_ids.add(idea_id)  # 追加して以降の重複チェックに使う

    logger.info(f"Deduplication: {len(unique_ideas)} unique, {len(duplicate_ideas)} duplicates")

    return unique_ideas, duplicate_ideas


if __name__ == "__main__":
    # ロギング設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # テスト用
    from datetime import datetime

    today = datetime.now().strftime('%Y%m%d')
    extracted_ideas_path = f"analyses/00_to_be_started/ideas_extracted_{today}.jsonl"

    # 新規アイデア読み込み
    new_ideas = load_ideas_from_jsonl(extracted_ideas_path)

    # 既存ID取得
    existing_ids = get_existing_idea_ids()

    # 重複排除
    unique_ideas, duplicates = deduplicate_ideas(new_ideas, existing_ids)

    print(f"\n=== Deduplication Summary ===")
    print(f"New ideas: {len(new_ideas)}")
    print(f"Existing IDs: {len(existing_ids)}")
    print(f"Unique: {len(unique_ideas)}")
    print(f"Duplicates: {len(duplicates)}")
