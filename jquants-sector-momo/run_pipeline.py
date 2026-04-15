"""
J-Quants Sector Momentum Pipeline

セクターモメンタム戦略のメイン実行スクリプト

使用方法:
    python run_pipeline.py --days 400 --top-sectors 5 --top-stocks 20
    python run_pipeline.py --use-claude  # Claude解説付き
    python run_pipeline.py --prime-only  # プライム市場のみ
"""
import argparse
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.momo.providers import JQuantsDataProvider
from src.momo.strategies import SectorMomentumStrategy
from src.momo.utils import calculate_position_sizes, generate_reports
from src.momo.utils.anthropic_client import generate_claude_commentary


console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="J-Quants Sector Momentum Strategy"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=400,
        help="データ取得期間（日数、デフォルト400）",
    )
    parser.add_argument(
        "--asof",
        type=str,
        default=None,
        help="基準日（YYYY-MM-DD、未指定なら最新）",
    )
    parser.add_argument(
        "--top-sectors",
        type=int,
        default=5,
        help="推奨セクター数（デフォルト5）",
    )
    parser.add_argument(
        "--top-stocks",
        type=int,
        default=20,
        help="推奨銘柄数（デフォルト20）",
    )
    parser.add_argument(
        "--prime-only",
        action="store_true",
        help="プライム市場のみに絞る",
    )
    parser.add_argument(
        "--use-claude",
        action="store_true",
        help="Claude解説を追加",
    )
    parser.add_argument(
        "--portfolio-value-jpy",
        type=float,
        default=None,
        help="ポートフォリオ評価額（円）",
    )
    parser.add_argument(
        "--use-local",
        action="store_true",
        help="ローカルファイルからデータ取得（デフォルトはAPI）",
    )

    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold cyan]J-Quants Sector Momentum Pipeline[/bold cyan]",
            subtitle=f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )
    )

    try:
        # ========================================
        # 1. データ取得
        # ========================================
        console.print("\n[bold yellow]1/5 データ取得[/bold yellow]")
        provider = JQuantsDataProvider()
        master, daily_bars, asof_date = provider.fetch_data(
            days=args.days,
            asof_date=args.asof,
            prime_only=args.prime_only,
            use_api=not args.use_local,  # --use-localが指定されていなければAPIを使用
        )

        # ========================================
        # 2. 戦略実行
        # ========================================
        console.print("\n[bold yellow]2/5 戦略実行[/bold yellow]")
        strategy = SectorMomentumStrategy()
        top_sectors, top_stocks = strategy.run(
            master=master,
            daily_bars=daily_bars,
            asof_date=asof_date,
            top_k_sectors=args.top_sectors,
            top_n_stocks=args.top_stocks,
        )

        # ========================================
        # 3. ポジションサイジング
        # ========================================
        console.print("\n[bold yellow]3/5 ポジションサイジング[/bold yellow]")
        top_stocks_sized = calculate_position_sizes(
            top_stocks,
            target_gross=1.0,
            min_weight=0.02,
            max_weight=0.08,
            risk_measure="volatility",
        )

        # ========================================
        # 4. Claude解説（オプション）
        # ========================================
        claude_commentary = None
        if args.use_claude:
            console.print("\n[bold yellow]4/5 Claude解説生成[/bold yellow]")
            claude_commentary = generate_claude_commentary(
                top_sectors=top_sectors.head(10),
                top_stocks=top_stocks_sized.head(20),
                asof_date=asof_date,
            )
        else:
            console.print("\n[bold yellow]4/5 Claude解説[/bold yellow] (スキップ)")

        # ========================================
        # 5. レポート生成
        # ========================================
        console.print("\n[bold yellow]5/5 レポート生成[/bold yellow]")
        metadata = {
            "asof_date": asof_date,
            "days": args.days,
            "top_sectors": args.top_sectors,
            "top_stocks": args.top_stocks,
            "prime_only": args.prime_only,
            "portfolio_value_jpy": args.portfolio_value_jpy,
        }

        json_path, md_path = generate_reports(
            top_sectors=top_sectors.head(args.top_sectors),
            top_stocks=top_stocks_sized,
            metadata=metadata,
            claude_commentary=claude_commentary,
        )

        console.print(f"  OK JSON: {json_path}")
        console.print(f"  OK Markdown: {md_path}")

        # ========================================
        # コンソール表示
        # ========================================
        console.print("\n" + "=" * 80)
        console.print("[bold green]推奨セクター（33業種）[/bold green]\n")
        _print_sector_table(top_sectors.head(args.top_sectors))

        console.print("\n" + "=" * 80)
        console.print("[bold green]推奨銘柄（ポジションサイズ調整済み）[/bold green]\n")
        _print_stock_table(top_stocks_sized)

        console.print("\n[bold cyan]OK パイプライン完了！[/bold cyan]")

    except Exception as e:
        console.print(f"\n[bold red]ERROR エラー: {e}[/bold red]")
        raise


def _print_sector_table(df):
    """推奨セクター表を表示"""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("順位", style="dim", width=6)
    table.add_column("セクターコード", width=12)
    table.add_column("セクター名", width=20)
    table.add_column("平均スコア", justify="right", width=12)
    table.add_column("Breadth", justify="right", width=10)
    table.add_column("平均Ret20%", justify="right", width=12)
    table.add_column("銘柄数", justify="right", width=8)

    for i, row in enumerate(df.itertuples(), start=1):
        table.add_row(
            str(i),
            str(row.Sector33Code),
            str(row.Sector33Name),
            f"{row.AvgScore:.2f}",
            f"{row.Breadth:.2%}",
            f"{row.AvgRet20:.2f}%",
            str(row.StockCount),
        )

    console.print(table)


def _print_stock_table(df):
    """推奨銘柄表を表示"""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("順位", style="dim", width=6)
    table.add_column("コード", width=8)
    table.add_column("銘柄名", width=20)
    table.add_column("セクター", width=15)
    table.add_column("終値", justify="right", width=10)
    table.add_column("Ret5%", justify="right", width=8)
    table.add_column("Ret10%", justify="right", width=8)
    table.add_column("Ret20%", justify="right", width=8)
    table.add_column("スコア", justify="right", width=8)
    table.add_column("ウェイト", justify="right", width=10)

    for i, row in enumerate(df.itertuples(), start=1):
        table.add_row(
            str(i),
            str(row.Code),
            str(row.CompanyName)[:18],
            str(row.Sector33Name)[:13],
            f"{row.AdjC:.0f}",
            f"{row.Ret_5:.1f}",
            f"{row.Ret_10:.1f}",
            f"{row.Ret_20:.1f}",
            f"{row.Score:.2f}",
            f"{row.weight:.2%}",
        )

    console.print(table)


if __name__ == "__main__":
    main()
