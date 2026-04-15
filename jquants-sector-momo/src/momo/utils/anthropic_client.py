"""
Anthropic Claude API クライアント

推奨セクター・銘柄の解説生成（投資助言ではなく条件付き説明）
"""
import os
import json
from typing import Dict, Any, Optional
import pandas as pd

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class ClaudeCommentaryClient:
    """Claudeによる解説生成クライアント"""

    def __init__(self):
        """初期化（環境変数からAPIキー取得）"""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropicパッケージがインストールされていません。\n"
                "pip install anthropic を実行してください。"
            )

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "環境変数 ANTHROPIC_API_KEY が設定されていません。\n"
                "Windows環境変数に設定してください。"
            )

        self.client = Anthropic(api_key=api_key)

    def generate_commentary(
        self,
        top_sectors: pd.DataFrame,
        top_stocks: pd.DataFrame,
        asof_date: str,
    ) -> Dict[str, Any]:
        """
        推奨セクター・銘柄の解説を生成

        Args:
            top_sectors: 推奨セクターのDataFrame（最大10件）
            top_stocks: 推奨銘柄のDataFrame（最大20件）
            asof_date: 基準日

        Returns:
            dict: {
                "market_summary": str,
                "sector_notes": str,
                "stock_notes": dict[code, note]
            }
        """
        # データ配布禁止に配慮し、最小限の情報のみ送信
        sectors_json = top_sectors.head(10).to_json(orient="records", force_ascii=False)
        stocks_json = top_stocks.head(20).to_json(orient="records", force_ascii=False)

        prompt = f"""
あなたは日本株のクオンツアナリストです。以下の推奨セクター・銘柄データを分析し、
**投資助言ではなく、条件付きの統計的説明**として解説を生成してください。

【重要な注意事項】
- 「買うべき」「売るべき」等の直接的な推奨は避ける
- 「〜の条件下では〜の傾向がある」「〜を下回れば無効化」等、条件付きで説明
- 過去データに基づく統計的特徴の説明に留める

【データ】
基準日: {asof_date}

推奨セクター（33業種）:
{sectors_json}

推奨銘柄:
{stocks_json}

【出力形式】
以下のJSON形式で回答してください（他のテキストは不要）:
{{
  "market_summary": "全体の市場環境や推奨セクターの特徴を2-3文で",
  "sector_notes": "推奨セクターの見方を2-3文で",
  "stock_notes": {{
    "銘柄コード1": "強み・注意点・無効化条件を1-2文で",
    "銘柄コード2": "...",
    ...（最大10銘柄）
  }}
}}
"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text.strip()

            # JSON部分を抽出（```json ... ``` がある場合）
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()

            commentary = json.loads(content)
            return commentary

        except Exception as e:
            print(f"WARN Claude解説生成エラー: {e}")
            return {
                "market_summary": "解説生成エラー",
                "sector_notes": "解説生成エラー",
                "stock_notes": {},
            }


def generate_claude_commentary(
    top_sectors: pd.DataFrame,
    top_stocks: pd.DataFrame,
    asof_date: str,
) -> Optional[Dict[str, Any]]:
    """
    Claude解説生成のヘルパー関数

    Args:
        top_sectors: 推奨セクター
        top_stocks: 推奨銘柄
        asof_date: 基準日

    Returns:
        dict or None: 解説（失敗時はNone）
    """
    try:
        client = ClaudeCommentaryClient()
        return client.generate_commentary(top_sectors, top_stocks, asof_date)
    except Exception as e:
        print(f"WARN Claude解説をスキップ: {e}")
        return None
