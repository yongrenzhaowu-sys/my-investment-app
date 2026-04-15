"""
週次リバランス・バックテスト

過去3ヶ月間で週次リバランスを行った場合のパフォーマンスを検証
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table

from src.momo.providers import JQuantsDataProvider
from src.momo.strategies import SectorMomentumStrategy
from src.momo.utils import calculate_position_sizes

console = Console()


def get_weekly_rebalance_dates(start_date: str, end_date: str, data_dates: pd.Series) -> list:
    """
    週次リバランス日を取得（毎週月曜日、または次の営業日）

    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        data_dates: 利用可能なデータの日付（営業日判定用）

    Returns:
        list: リバランス日のリスト
    """
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    # 毎週月曜日を生成
    mondays = pd.date_range(start=start_dt, end=end_dt, freq='W-MON')

    # 営業日に調整
    rebalance_dates = []
    available_dates = pd.to_datetime(data_dates).sort_values()

    for monday in mondays:
        # その週の営業日を探す（月曜〜金曜）
        for offset in range(5):  # 月曜〜金曜
            candidate = monday + timedelta(days=offset)
            if candidate in available_dates.values:
                rebalance_dates.append(candidate)
                break

    return [d.strftime('%Y-%m-%d') for d in rebalance_dates]


def calculate_weekly_return(
    daily_bars: pd.DataFrame,
    holdings: dict,
    start_date: str,
    end_date: str,
) -> float:
    """
    週次リターンを計算

    Args:
        daily_bars: 日次バーデータ
        holdings: ポジション {'Code': weight}
        start_date: 週の開始日
        end_date: 週の終了日

    Returns:
        float: 週次リターン（%）
    """
    if not holdings:
        return 0.0

    # 各銘柄のリターンを計算
    weekly_returns = []
    weights = []

    for code, weight in holdings.items():
        stock_data = daily_bars[daily_bars['Code'] == code].copy()
        stock_data = stock_data.sort_values('Date')

        # 期間内のデータを抽出
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        period_data = stock_data[(stock_data['Date'] >= start_dt) & (stock_data['Date'] <= end_dt)]

        if len(period_data) < 2:
            continue

        # 最初と最後の価格
        start_price = period_data.iloc[0]['AdjC']
        end_price = period_data.iloc[-1]['AdjC']

        if start_price > 0:
            stock_return = (end_price / start_price - 1.0) * 100.0
            weekly_returns.append(stock_return)
            weights.append(weight)

    if not weekly_returns:
        return 0.0

    # 加重平均リターン
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0

    weighted_return = sum(r * w for r, w in zip(weekly_returns, weights)) / total_weight
    return weighted_return


def calculate_turnover(old_holdings: dict, new_holdings: dict) -> float:
    """
    ターンオーバー（売買回転率）を計算

    Args:
        old_holdings: 前週のポジション {'Code': weight}
        new_holdings: 今週のポジション {'Code': weight}

    Returns:
        float: ターンオーバー（0.0 〜 2.0、2.0は全銘柄入れ替え）
    """
    all_codes = set(old_holdings.keys()) | set(new_holdings.keys())

    turnover = 0.0
    for code in all_codes:
        old_weight = old_holdings.get(code, 0.0)
        new_weight = new_holdings.get(code, 0.0)
        turnover += abs(new_weight - old_weight)

    return turnover


def run_backtest(
    start_date: str = "2025-12-02",
    end_date: str = "2026-03-02",
    data_days: int = 120,
    top_sectors: int = 3,
    top_stocks: int = 10,
    transaction_cost: float = 0.001,  # 0.1% 片道
    initial_capital: float = 1000000.0,
    use_api: bool = False,
):
    """
    週次リバランス・バックテストを実行

    Args:
        start_date: バックテスト開始日
        end_date: バックテスト終了日
        data_days: データ取得期間（日数）
        top_sectors: 推奨セクター数
        top_stocks: 推奨銘柄数
        transaction_cost: 取引コスト（片道、デフォルト0.1%）
        initial_capital: 初期資金（円）
        use_api: APIからデータ取得するか

    Returns:
        dict: バックテスト結果
    """
    console.print("\n[bold cyan]週次リバランス・バックテスト[/bold cyan]\n")

    # 1. データ取得
    console.print("[1/5] データ取得中...")
    provider = JQuantsDataProvider()

    # データ取得期間を拡張（計算用）
    data_start = (pd.to_datetime(start_date) - timedelta(days=data_days)).strftime('%Y-%m-%d')

    master, daily_bars, _ = provider.fetch_data(
        days=data_days,
        asof_date=end_date,
        use_api=use_api,
    )

    # 2. リバランス日を特定
    console.print("[2/5] リバランス日を特定中...")
    rebalance_dates = get_weekly_rebalance_dates(
        start_date,
        end_date,
        daily_bars['Date']
    )
    console.print(f"  リバランス回数: {len(rebalance_dates)}")

    # 3. 各リバランス日で戦略実行
    console.print("[3/5] 戦略実行中...")
    strategy = SectorMomentumStrategy()

    backtest_log = []
    current_holdings = {}
    portfolio_value = initial_capital
    cumulative_returns = []

    for i, rebal_date in enumerate(rebalance_dates):
        console.print(f"  [{i+1}/{len(rebalance_dates)}] {rebal_date}")

        try:
            # 推奨銘柄を計算
            top_sectors_df, top_stocks_df = strategy.run(
                master=master,
                daily_bars=daily_bars,
                asof_date=rebal_date,
                top_k_sectors=top_sectors,
                top_n_stocks=top_stocks,
            )

            # ポジションサイズを計算
            top_stocks_sized = calculate_position_sizes(
                top_stocks_df,
                target_gross=1.0,
                min_weight=0.05,
                max_weight=0.15,
            )

            # 新しいポジション
            new_holdings = dict(zip(
                top_stocks_sized['Code'],
                top_stocks_sized['weight']
            ))

            # ターンオーバーを計算
            turnover = calculate_turnover(current_holdings, new_holdings) if current_holdings else 0.0

            # 取引コストを計算
            cost = turnover * transaction_cost

            # 次のリバランス日までのリターンを計算
            if i < len(rebalance_dates) - 1:
                next_rebal_date = rebalance_dates[i + 1]
                weekly_return = calculate_weekly_return(
                    daily_bars,
                    new_holdings,
                    rebal_date,
                    next_rebal_date,
                )
            else:
                # 最終週
                weekly_return = calculate_weekly_return(
                    daily_bars,
                    new_holdings,
                    rebal_date,
                    end_date,
                )

            # コストを差し引く
            net_return = weekly_return - (cost * 100.0)

            # ポートフォリオ価値を更新
            portfolio_value *= (1.0 + net_return / 100.0)

            # 累積リターン
            cumulative_return = (portfolio_value / initial_capital - 1.0) * 100.0
            cumulative_returns.append(cumulative_return)

            backtest_log.append({
                "date": rebal_date,
                "holdings": list(new_holdings.keys()),
                "weights": list(new_holdings.values()),
                "turnover": turnover,
                "cost_pct": cost * 100.0,
                "weekly_return_gross": weekly_return,
                "weekly_return_net": net_return,
                "portfolio_value": portfolio_value,
                "cumulative_return": cumulative_return,
            })

            # ポジションを更新
            current_holdings = new_holdings

        except Exception as e:
            console.print(f"  [WARN] {rebal_date}でエラー: {e}")
            continue

    # 4. パフォーマンス評価
    console.print("[4/5] パフォーマンス評価中...")

    weekly_returns_net = [log['weekly_return_net'] for log in backtest_log]
    total_return = (portfolio_value / initial_capital - 1.0) * 100.0

    # 年率換算リターン（3ヶ月 = 0.25年）
    period_years = len(rebalance_dates) / 52.0  # 週数を年に変換
    annualized_return = ((1.0 + total_return / 100.0) ** (1.0 / period_years) - 1.0) * 100.0

    # シャープレシオ（週次リターンの平均/標準偏差）
    if len(weekly_returns_net) > 1:
        avg_return = np.mean(weekly_returns_net)
        std_return = np.std(weekly_returns_net, ddof=1)
        sharpe_ratio = (avg_return / std_return) * np.sqrt(52) if std_return > 0 else 0.0
    else:
        sharpe_ratio = 0.0

    # 最大ドローダウン
    peak = initial_capital
    max_dd = 0.0
    for log in backtest_log:
        pv = log['portfolio_value']
        if pv > peak:
            peak = pv
        dd = (peak - pv) / peak * 100.0
        if dd > max_dd:
            max_dd = dd

    # 勝率
    win_rate = sum(1 for r in weekly_returns_net if r > 0) / len(weekly_returns_net) * 100.0 if weekly_returns_net else 0.0

    results = {
        "period": {"start": start_date, "end": end_date},
        "rebalance_count": len(rebalance_dates),
        "initial_capital": initial_capital,
        "final_value": portfolio_value,
        "total_return_pct": total_return,
        "annualized_return_pct": annualized_return,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown_pct": max_dd,
        "win_rate_pct": win_rate,
        "avg_weekly_return_pct": np.mean(weekly_returns_net) if weekly_returns_net else 0.0,
        "volatility_weekly_pct": np.std(weekly_returns_net, ddof=1) if len(weekly_returns_net) > 1 else 0.0,
        "log": backtest_log,
    }

    # 5. レポート生成
    console.print("[5/5] レポート生成中...")

    # JSON
    # コンテナ環境では /out/reports に保存（read-write）
    reports_dir = Path(os.environ.get("BACKTEST_OUTPUT_DIR", "reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "backtest_weekly_3months.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    # Markdown
    md_lines = []
    md_lines.append("# 週次リバランス・バックテスト結果\n")
    md_lines.append(f"**期間**: {start_date} 〜 {end_date}\n")
    md_lines.append(f"**リバランス回数**: {len(rebalance_dates)}回\n")
    md_lines.append(f"**初期資金**: {initial_capital:,.0f}円\n")
    md_lines.append("\n## パフォーマンスサマリー\n")
    md_lines.append(f"- **最終資産**: {portfolio_value:,.0f}円")
    md_lines.append(f"- **累積リターン**: {total_return:.2f}%")
    md_lines.append(f"- **年率換算リターン**: {annualized_return:.2f}%")
    md_lines.append(f"- **シャープレシオ**: {sharpe_ratio:.2f}")
    md_lines.append(f"- **最大ドローダウン**: {max_dd:.2f}%")
    md_lines.append(f"- **勝率**: {win_rate:.1f}%")
    md_lines.append(f"- **平均週次リターン**: {np.mean(weekly_returns_net):.2f}%")
    md_lines.append(f"- **週次リターンボラティリティ**: {np.std(weekly_returns_net, ddof=1):.2f}%\n")

    md_lines.append("\n## 週次リターン推移\n")
    md_lines.append("| 日付 | 週次リターン(%) | 累積リターン(%) | ポートフォリオ価値(円) |")
    md_lines.append("|------|----------------|----------------|---------------------|")
    for log in backtest_log:
        md_lines.append(
            f"| {log['date']} | {log['weekly_return_net']:.2f} | {log['cumulative_return']:.2f} | {log['portfolio_value']:,.0f} |"
        )

    md_path = reports_dir / "backtest_weekly_3months.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))

    console.print(f"  [OK] JSON: {json_path}")
    console.print(f"  [OK] Markdown: {md_path}")

    # コンソール表示
    _print_results(results)

    return results


def _print_results(results: dict):
    """結果をコンソールに表示"""
    console.print("\n" + "=" * 80)
    console.print("[bold green]バックテスト結果[/bold green]\n")

    table = Table(show_header=False)
    table.add_column("指標", style="cyan")
    table.add_column("値", justify="right", style="yellow")

    table.add_row("期間", f"{results['period']['start']} 〜 {results['period']['end']}")
    table.add_row("リバランス回数", f"{results['rebalance_count']}回")
    table.add_row("初期資金", f"{results['initial_capital']:,.0f}円")
    table.add_row("最終資産", f"{results['final_value']:,.0f}円")
    table.add_row("", "")
    table.add_row("累積リターン", f"{results['total_return_pct']:.2f}%")
    table.add_row("年率換算リターン", f"{results['annualized_return_pct']:.2f}%")
    table.add_row("シャープレシオ", f"{results['sharpe_ratio']:.2f}")
    table.add_row("最大ドローダウン", f"{results['max_drawdown_pct']:.2f}%")
    table.add_row("勝率", f"{results['win_rate_pct']:.1f}%")
    table.add_row("平均週次リターン", f"{results['avg_weekly_return_pct']:.2f}%")

    console.print(table)
    console.print("\n" + "=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="週次リバランス・バックテスト")
    parser.add_argument("--start", type=str, default="2025-12-02", help="開始日")
    parser.add_argument("--end", type=str, default="2026-03-02", help="終了日")
    parser.add_argument("--use-api", action="store_true", help="APIからデータ取得")
    args = parser.parse_args()

    run_backtest(
        start_date=args.start,
        end_date=args.end,
        use_api=args.use_api,
    )
