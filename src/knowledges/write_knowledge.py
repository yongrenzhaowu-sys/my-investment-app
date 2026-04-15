"""知見ファイル生成。"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def generate_knowledge_file(
    idea: Dict,
    backtest_result: Dict,
    output_path: str,
) -> None:
    """知見ファイルを生成する。
    
    Args:
        idea: 投資アイデア
        backtest_result: バックテスト結果
        output_path: 出力先パス（例: docs/knowledges/20260220_0530_topic.md）
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 知見ファイル生成
    lines = []
    
    # ヘッダー
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"# 知見: {idea.get('title', 'Unknown')}\n\n")
    lines.append(f"生成日時: {timestamp}\n\n")
    lines.append("---\n\n")
    
    # 出典
    lines.append("## 出典情報\n\n")
    lines.append(f"- **ソース**: {idea.get('source', 'Unknown')}\n")
    lines.append(f"- **URL**: {idea.get('source_url', 'N/A')}\n")
    lines.append(f"- **公開日**: {idea.get('published_at', 'N/A')}\n")
    lines.append(f"- **タイトル**: {idea.get('title', 'Unknown')}\n\n")
    
    # 要約
    summary = idea.get('summary', '')
    if summary:
        lines.append("## 要約\n\n")
        lines.append(f"{summary}\n\n")
    
    # 対象銘柄と抽出根拠
    lines.append("## 対象銘柄と抽出根拠\n\n")
    tickers = idea.get('tickers', [])
    lines.append(f"- **抽出銘柄**: {', '.join(tickers)}\n")
    lines.append(f"- **抽出数**: {len(tickers)}銘柄\n")
    lines.append(f"- **スコア**: {idea.get('score', 0):.3f}\n\n")
    
    lines.append("### 抽出根拠\n\n")
    lines.append("記事本文から4桁の証券コードを検出し、ポジティブキーワード（増益、好調、提携等）の")
    lines.append("出現頻度に基づいてスコアリング。ネガティブキーワード（不正、倒産等）が含まれる場合は除外。\n\n")
    
    # バックテスト条件
    lines.append("## バックテスト条件\n\n")
    lines.append(f"- **イベント日**: {backtest_result.get('event_date', 'N/A')}\n")
    lines.append(f"- **保有期間**: 1日、3日、5日（営業日）\n")
    lines.append(f"- **ベンチマーク**: TOPIX（比較は今後実装）\n")
    lines.append(f"- **リターン計算**: 単純リターン（株式分割調整あり）\n\n")
    
    # 結果
    lines.append("## バックテスト結果\n\n")
    
    summary = backtest_result.get('summary', {})
    if summary:
        avg_return = summary.get('average_return_5d')
        positive_rate = summary.get('positive_rate', 0)
        total_tickers = summary.get('total_tickers', 0)
        valid_tickers = summary.get('valid_tickers', 0)
        
        lines.append("### サマリー\n\n")
        if avg_return is not None:
            lines.append(f"- **5日平均リターン**: {avg_return * 100:.2f}%\n")
            lines.append(f"- **勝率**: {positive_rate * 100:.1f}%\n")
        lines.append(f"- **対象銘柄数**: {total_tickers}銘柄\n")
        lines.append(f"- **有効銘柄数**: {valid_tickers}銘柄（データ取得成功）\n\n")
    
    # 保有期間別
    holding_periods = backtest_result.get('holding_periods', {})
    if holding_periods:
        lines.append("### 保有期間別詳細\n\n")
        lines.append("| 保有期間 | 平均 | 中央値 | 標準偏差 | 最小 | 最大 | サンプル数 |\n")
        lines.append("|---------|------|--------|---------|------|------|----------|\n")
        
        for period in ["1d", "3d", "5d"]:
            if period in holding_periods:
                metrics = holding_periods[period]
                mean_ret = metrics.get('mean_return')
                median_ret = metrics.get('median_return')
                std_ret = metrics.get('std_return')
                min_ret = metrics.get('min_return')
                max_ret = metrics.get('max_return')
                count = metrics.get('count', 0)
                
                if mean_ret is not None:
                    lines.append(f"| {period} | {mean_ret*100:.2f}% | {median_ret*100:.2f}% | ")
                    lines.append(f"{std_ret*100:.2f}% | {min_ret*100:.2f}% | {max_ret*100:.2f}% | {count} |\n")
        
        lines.append("\n")
    
    # 学び
    lines.append("## 学びと改善案\n\n")
    
    if summary and summary.get('average_return_5d'):
        avg_ret = summary['average_return_5d']
        
        if avg_ret > 0.02:  # 2%以上
            lines.append("### ✅ 成功パターン\n\n")
            lines.append("- このタイプのニュースは短期的に好影響を与える可能性が高い\n")
            lines.append("- 同様のキーワードパターンを今後も監視する価値あり\n")
        elif avg_ret < -0.01:  # -1%以下
            lines.append("### ❌ 失敗パターン\n\n")
            lines.append("- このタイプのニュースは期待ほどの効果がなかった\n")
            lines.append("- フィルタリング条件の見直しが必要\n")
        else:
            lines.append("### 📊 中立的な結果\n\n")
            lines.append("- 明確なトレンドは確認できず\n")
            lines.append("- より多くのサンプルで検証が必要\n")
    else:
        lines.append("- データ不足のため、明確な学びは得られず\n")
    
    lines.append("\n### 改善案\n\n")
    lines.append("- [ ] より精度の高い銘柄抽出ロジックの検討\n")
    lines.append("- [ ] ベンチマーク（TOPIX）との比較実装\n")
    lines.append("- [ ] セクター別の分析追加\n")
    lines.append("- [ ] より長期（10日、20日）の保有期間検証\n\n")
    
    # 再実行コマンド
    lines.append("## 再実行コマンド\n\n")
    lines.append("```bash\n")
    lines.append("# 日次実行\n")
    lines.append("python scripts/daily_run.py\n\n")
    lines.append("# 個別のアイデアで再実行する場合は、該当する analyses/ ディレクトリで\n")
    lines.append("# Jupyter Notebookを使用\n")
    lines.append("```\n\n")
    
    # ファイルに書き込み
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    logger.info(f"Knowledge file generated: {output_path}")
