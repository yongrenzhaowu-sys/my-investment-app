"""日次レポート生成。"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def generate_daily_report(
    rss_results: List[Dict],
    ideas: List[Dict],
    processed_ideas: List[Dict],
    backtest_results: List[Dict],
    output_path: str,
) -> None:
    """日次レポートを生成する。
    
    Args:
        rss_results: RSS取得結果のリスト
        ideas: 抽出されたアイデアのリスト
        processed_ideas: 処理されたアイデアのリスト
        backtest_results: バックテスト結果のリスト
        output_path: 出力先パス（例: docs/reports/20260220.md）
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # レポート生成
    report_lines = []
    
    # ヘッダー
    today = datetime.now().strftime("%Y-%m-%d")
    report_lines.append(f"# Daily Report - {today}\n")
    report_lines.append(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report_lines.append("---\n")
    
    # RSS取得サマリー
    report_lines.append("## RSS取得サマリー\n")
    
    total_feeds = len(rss_results)
    successful_feeds = sum(1 for r in rss_results if r.get("success", False))
    total_items = sum(len(r.get("items", [])) for r in rss_results)
    
    report_lines.append(f"- 取得フィード数: {successful_feeds}/{total_feeds}\n")
    report_lines.append(f"- 取得記事数: {total_items}\n")
    
    # フィード別詳細
    report_lines.append("\n### フィード別詳細\n")
    for result in rss_results:
        feed_name = result.get("feed_name", "Unknown")
        success = "✅" if result.get("success", False) else "❌"
        item_count = len(result.get("items", []))
        report_lines.append(f"- {success} **{feed_name}**: {item_count}件\n")
    
    # アイデア抽出サマリー
    report_lines.append("\n## アイデア抽出サマリー\n")
    report_lines.append(f"- 抽出されたアイデア数: {len(ideas)}\n")
    report_lines.append(f"- 処理されたアイデア数: {len(processed_ideas)}\n")
    
    if ideas:
        avg_score = sum(i.get("score", 0) for i in ideas) / len(ideas)
        report_lines.append(f"- 平均スコア: {avg_score:.3f}\n")
    
    # 処理されたアイデアの詳細
    if processed_ideas:
        report_lines.append("\n### 処理されたアイデア\n")
        for idea in processed_ideas:
            title = idea.get("title", "Unknown")
            tickers = ", ".join(idea.get("tickers", []))
            score = idea.get("score", 0)
            report_lines.append(f"- **{title}**\n")
            report_lines.append(f"  - 銘柄: {tickers}\n")
            report_lines.append(f"  - スコア: {score:.3f}\n")
    
    # バックテスト結果サマリー
    report_lines.append("\n## バックテスト結果サマリー\n")
    
    if backtest_results:
        for result in backtest_results:
            idea_id = result.get("idea_id", "Unknown")
            tickers = ", ".join(result.get("tickers", []))
            summary = result.get("summary", {})
            
            report_lines.append(f"\n### アイデア: {idea_id}\n")
            report_lines.append(f"- 銘柄: {tickers}\n")
            report_lines.append(f"- イベント日: {result.get('event_date', 'N/A')}\n")
            
            if summary:
                avg_return = summary.get("average_return_5d")
                positive_rate = summary.get("positive_rate", 0)
                valid_tickers = summary.get("valid_tickers", 0)
                
                if avg_return is not None:
                    report_lines.append(f"- 5日平均リターン: {avg_return * 100:.2f}%\n")
                    report_lines.append(f"- 勝率: {positive_rate * 100:.1f}%\n")
                    report_lines.append(f"- 有効銘柄数: {valid_tickers}\n")
            
            # 保有期間別
            holding_periods = result.get("holding_periods", {})
            if holding_periods:
                report_lines.append("\n**保有期間別リターン:**\n")
                for period, metrics in holding_periods.items():
                    mean_ret = metrics.get("mean_return")
                    if mean_ret is not None:
                        report_lines.append(f"- {period}: {mean_ret * 100:.2f}% (n={metrics.get('count', 0)})\n")
    else:
        report_lines.append("- 処理されたバックテストなし\n")
    
    # 明日のTODO
    report_lines.append("\n## 明日のTODO\n")
    report_lines.append("- [ ] 日次実行の確認\n")
    report_lines.append("- [ ] 新規アイデアのレビュー\n")
    report_lines.append("- [ ] バックテスト結果の分析\n")
    
    # ファイルに書き込み
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(report_lines)
    
    logger.info(f"Daily report generated: {output_path}")
