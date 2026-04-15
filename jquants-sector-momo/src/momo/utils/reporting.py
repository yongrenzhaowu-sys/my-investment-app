"""
レポート生成（JSON + Markdown）

推奨セクター・銘柄をreports/に保存
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd
from .sector33 import get_sector_name


def generate_reports(
    top_sectors: pd.DataFrame,
    top_stocks: pd.DataFrame,
    metadata: Dict[str, Any],
    claude_commentary: Optional[Dict[str, Any]] = None,
    output_dir: str = "reports",
) -> tuple[str, str]:
    """
    レポート生成（JSON + MD）

    Args:
        top_sectors: 推奨セクターのDataFrame
        top_stocks: 推奨銘柄のDataFrame（weight含む）
        metadata: メタデータ（asof_date, days, etc）
        claude_commentary: Claudeの解説（任意）
        output_dir: 出力先ディレクトリ

    Returns:
        tuple[str, str]: (json_path, md_path)
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # タイムスタンプ
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    asof_date = metadata.get("asof_date", "N/A")

    # JSON生成
    report_data = {
        "metadata": metadata,
        "top_sectors": top_sectors.to_dict(orient="records"),
        "top_stocks": top_stocks.to_dict(orient="records"),
        "claude_commentary": claude_commentary,
    }

    json_path = output_path / "report_latest.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)

    # Markdown生成
    md_lines = []
    md_lines.append("# J-Quants セクターモメンタム 推奨レポート")
    md_lines.append("")
    md_lines.append("## WARN ディスクレーマー")
    md_lines.append("**本レポートは投資助言ではありません。**")
    md_lines.append("過去のデータに基づく統計的分析結果であり、将来の運用成果を保証するものではありません。")
    md_lines.append("実際の投資判断は自己責任で行ってください。")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append(f"- **生成日時**: {timestamp}")
    md_lines.append(f"- **基準日（as-of）**: {asof_date}")
    md_lines.append(f"- **データ期間**: {metadata.get('days', 'N/A')}日分")
    md_lines.append(f"- **推奨セクター数**: {len(top_sectors)}")
    md_lines.append(f"- **推奨銘柄数**: {len(top_stocks)}")
    md_lines.append("")
    md_lines.append("## 推奨セクター（33業種）")
    md_lines.append("")
    md_lines.append(_df_to_markdown(top_sectors))
    md_lines.append("")
    md_lines.append("## 推奨銘柄（ポジションサイズ調整済み）")
    md_lines.append("")
    md_lines.append("**価格**: 調整済み終値（AdjC）を使用")
    md_lines.append("**ストップ距離**: 2×ATR14")
    md_lines.append("")
    md_lines.append(_df_to_markdown(top_stocks))
    md_lines.append("")

    # Claude解説
    if claude_commentary:
        md_lines.append("## Claude解説（条件付き・ルールベース）")
        md_lines.append("")
        md_lines.append("### 市場サマリー")
        md_lines.append(claude_commentary.get("market_summary", "N/A"))
        md_lines.append("")
        md_lines.append("### セクター所見")
        md_lines.append(claude_commentary.get("sector_notes", "N/A"))
        md_lines.append("")
        md_lines.append("### 銘柄別ノート")
        stock_notes = claude_commentary.get("stock_notes", {})
        if isinstance(stock_notes, dict):
            for code, note in stock_notes.items():
                md_lines.append(f"- **{code}**: {note}")
        md_lines.append("")

    md_lines.append("---")
    md_lines.append("")
    md_lines.append("**備考**:")
    md_lines.append("- J-Quants日次バーの調整済み列（AdjO/AdjH/AdjL/AdjC/AdjVo）を使用")
    md_lines.append("- モメンタムスコアは5/10/20日リターン・出来高比の頑健化z-scoreで合成")
    md_lines.append("- ポジションサイズはボラティリティ逆相関で配分（min 2%, max 8%）")
    md_lines.append("")

    md_path = output_path / "report_latest.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return str(json_path), str(md_path)


def _df_to_markdown(df: pd.DataFrame) -> str:
    """DataFrameをMarkdownテーブルに変換"""
    if df.empty:
        return "(データなし)"

    # 列名
    headers = "| " + " | ".join(str(col) for col in df.columns) + " |"
    separator = "|" + "|".join([" --- "] * len(df.columns)) + "|"

    # データ行
    rows = []
    for _, row in df.iterrows():
        row_str = "| " + " | ".join(_format_cell(val) for val in row) + " |"
        rows.append(row_str)

    return "\n".join([headers, separator] + rows)


def _format_cell(val) -> str:
    """セル値のフォーマット"""
    if pd.isna(val):
        return "N/A"
    if isinstance(val, float):
        if abs(val) < 0.001 and val != 0:
            return f"{val:.4f}"
        return f"{val:.2f}"
    return str(val)
