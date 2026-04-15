"""
ポートフォリオ分析・組み替え提案

現在の保有銘柄を分析し、最新の推奨銘柄に基づいて組み替え提案を作成
"""
import json
from pathlib import Path
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table

from src.momo.providers import JQuantsDataProvider
from src.momo.strategies import SectorMomentumStrategy
from src.momo.utils import calculate_position_sizes

console = Console()


def analyze_portfolio(
    holdings: dict,  # {code: shares}
    acquisition_prices: dict,  # {code: avg_price}
    asof_date: str = "2026-03-02",
    top_sectors: int = 3,
    top_stocks: int = 10,
):
    """
    ポートフォリオを分析し、組み替え提案を作成

    Args:
        holdings: 保有銘柄と株数 {code: shares}
        acquisition_prices: 取得単価 {code: avg_price}
        asof_date: 分析基準日
        top_sectors: 推奨セクター数
        top_stocks: 推奨銘柄数

    Returns:
        dict: 分析結果と組み替え提案
    """
    console.print("\n[bold cyan]ポートフォリオ分析[/bold cyan]\n")

    # 1. データ取得
    console.print("[1/6] データ取得中...")
    provider = JQuantsDataProvider()
    master, daily_bars, _ = provider.fetch_data(
        days=60,
        asof_date=asof_date,
        use_api=True,
    )

    # 2. 保有銘柄の現在値とセクター情報を取得
    console.print("[2/6] 保有銘柄の現在値を取得中...")
    holdings_analysis = []

    for code, shares in holdings.items():
        # 銘柄データを取得
        stock_data = daily_bars[daily_bars['Code'] == code].copy()
        if stock_data.empty:
            console.print(f"  [WARN] {code}: データなし")
            continue

        # 最新価格
        latest_data = stock_data.sort_values('Date').iloc[-1]
        current_price = latest_data['AdjC']

        # 銘柄マスター情報
        master_info = master[master['Code'] == code]
        if master_info.empty:
            company_name = "不明"
            sector = "不明"
        else:
            company_name = master_info.iloc[0]['CompanyName']
            sector = master_info.iloc[0].get('Sector33Name', '不明')

        # 取得単価
        avg_price = acquisition_prices.get(code, 0)

        # 評価額と損益
        market_value = current_price * shares
        acquisition_value = avg_price * shares
        pnl = market_value - acquisition_value
        pnl_pct = (pnl / acquisition_value * 100) if acquisition_value > 0 else 0

        holdings_analysis.append({
            'Code': code,
            'CompanyName': company_name,
            'Sector': sector,
            'Shares': shares,
            'AvgPrice': avg_price,
            'CurrentPrice': current_price,
            'AcquisitionValue': acquisition_value,
            'MarketValue': market_value,
            'PnL': pnl,
            'PnL_pct': pnl_pct,
        })

    holdings_df = pd.DataFrame(holdings_analysis)

    # 3. 最新の推奨銘柄を取得
    console.print("[3/6] 最新の推奨銘柄を計算中...")
    strategy = SectorMomentumStrategy()
    top_sectors_df, top_stocks_df = strategy.run(
        master=master,
        daily_bars=daily_bars,
        asof_date=asof_date,
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

    # 4. 保有銘柄のモメンタムスコアを確認
    console.print("[4/6] 保有銘柄のモメンタム分析中...")

    # 全銘柄の特徴量とスコアを計算
    all_features = strategy.calculate_features(master, daily_bars, asof_date)

    holdings_with_scores = []
    for _, holding in holdings_df.iterrows():
        code = holding['Code']
        # スコアデータから該当銘柄を取得
        score_data = all_features[all_features['Code'] == code]
        if not score_data.empty:
            score = score_data.iloc[0].get('Score', 0.0)
            ret_20 = score_data.iloc[0].get('Ret_20', 0.0)
            volatility = score_data.iloc[0].get('Volatility20', 0.0)
        else:
            score = 0.0
            ret_20 = 0.0
            volatility = 0.0

        holdings_with_scores.append({
            **holding.to_dict(),
            'Score': score,
            'Ret_20': ret_20,
            'Volatility20': volatility,
        })

    holdings_df = pd.DataFrame(holdings_with_scores)

    # 5. 組み替え提案を作成
    console.print("[5/6] 組み替え提案を作成中...")

    # 保有銘柄が推奨リストに含まれているか
    recommended_codes = set(top_stocks_sized['Code'].tolist())
    holdings_df['IsRecommended'] = holdings_df['Code'].isin(recommended_codes)

    # 売却候補: 推奨リストに含まれていない
    sell_candidates = holdings_df[~holdings_df['IsRecommended']].copy()
    sell_candidates = sell_candidates.sort_values('Score')  # スコアが低い順

    # 購入候補: 推奨リストで保有していない
    current_codes = set(holdings_df['Code'].tolist())
    buy_candidates = top_stocks_sized[~top_stocks_sized['Code'].isin(current_codes)].copy()
    buy_candidates = buy_candidates.sort_values('Score', ascending=False)  # スコアが高い順

    # 6. レポート生成
    console.print("[6/6] レポート生成中...")

    total_market_value = holdings_df['MarketValue'].sum()
    total_pnl = holdings_df['PnL'].sum()
    total_pnl_pct = (total_pnl / holdings_df['AcquisitionValue'].sum() * 100) if holdings_df['AcquisitionValue'].sum() > 0 else 0

    result = {
        'asof_date': asof_date,
        'portfolio_summary': {
            'total_acquisition_value': float(holdings_df['AcquisitionValue'].sum()),
            'total_market_value': float(total_market_value),
            'total_pnl': float(total_pnl),
            'total_pnl_pct': float(total_pnl_pct),
            'num_holdings': len(holdings_df),
        },
        'holdings': holdings_df.to_dict(orient='records'),
        'top_sectors': top_sectors_df.to_dict(orient='records'),
        'recommended_stocks': top_stocks_sized.to_dict(orient='records'),
        'sell_candidates': sell_candidates.to_dict(orient='records'),
        'buy_candidates': buy_candidates.to_dict(orient='records'),
    }

    # JSON出力
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    json_path = reports_dir / "portfolio_analysis.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    # Markdown出力
    md_lines = []
    md_lines.append("# ポートフォリオ分析・組み替え提案\n")
    md_lines.append(f"**分析基準日**: {asof_date}\n")
    md_lines.append("---\n")

    md_lines.append("## 現在のポートフォリオ\n")
    md_lines.append(f"- **取得価額合計**: {holdings_df['AcquisitionValue'].sum():,.0f}円")
    md_lines.append(f"- **時価総額合計**: {total_market_value:,.0f}円")
    md_lines.append(f"- **含み損益**: {total_pnl:+,.0f}円 ({total_pnl_pct:+.2f}%)")
    md_lines.append(f"- **保有銘柄数**: {len(holdings_df)}銘柄\n")

    md_lines.append("### 保有銘柄一覧\n")
    md_lines.append("| コード | 銘柄名 | セクター | 株数 | 取得単価 | 現在値 | 評価額 | 含み損益(%) | 推奨 | スコア |")
    md_lines.append("|--------|--------|----------|------|----------|--------|--------|-------------|------|--------|")
    for _, row in holdings_df.iterrows():
        is_rec = "✓" if row['IsRecommended'] else ""
        md_lines.append(
            f"| {row['Code']} | {row['CompanyName']} | {row['Sector']} | {row['Shares']:.0f} | "
            f"{row['AvgPrice']:,.0f} | {row['CurrentPrice']:,.0f} | {row['MarketValue']:,.0f} | "
            f"{row['PnL_pct']:+.1f}% | {is_rec} | {row['Score']:.2f} |"
        )
    md_lines.append("")

    md_lines.append("## 最新の推奨セクター（TOP 3）\n")
    for i, row in top_sectors_df.iterrows():
        md_lines.append(
            f"{i+1}. **{row['Sector33Name']}** - 平均20日リターン: {row['AvgRet20']:.2f}% - "
            f"平均スコア: {row['AvgScore']:.2f}"
        )
    md_lines.append("")

    md_lines.append("## 最新の推奨銘柄（TOP 10）\n")
    md_lines.append("| 順位 | コード | 銘柄名 | セクター | 現在値 | 20日リターン | スコア | 推奨ウェイト |")
    md_lines.append("|------|--------|--------|----------|--------|--------------|--------|--------------|")
    for i, row in top_stocks_sized.iterrows():
        md_lines.append(
            f"| {i+1} | {row['Code']} | {row['CompanyName']} | {row['Sector33Name']} | "
            f"{row['AdjC']:,.0f} | {row['Ret_20']:+.1f}% | {row['Score']:.2f} | {row['weight']:.1%} |"
        )
    md_lines.append("")

    md_lines.append("## 組み替え提案\n")

    if not sell_candidates.empty:
        md_lines.append("### 売却候補（推奨リストに含まれない銘柄）\n")
        md_lines.append("| コード | 銘柄名 | セクター | 評価額 | 含み損益(%) | スコア | 理由 |")
        md_lines.append("|--------|--------|----------|--------|-------------|--------|------|")
        for _, row in sell_candidates.iterrows():
            reason = "モメンタム低下" if row['Score'] < 0 else "推奨外"
            md_lines.append(
                f"| {row['Code']} | {row['CompanyName']} | {row['Sector']} | "
                f"{row['MarketValue']:,.0f} | {row['PnL_pct']:+.1f}% | {row['Score']:.2f} | {reason} |"
            )
        md_lines.append("")
    else:
        md_lines.append("### 売却候補: なし\n")
        md_lines.append("全ての保有銘柄が推奨リストに含まれています。\n")

    if not buy_candidates.empty:
        md_lines.append("### 購入候補（推奨銘柄で未保有）\n")
        md_lines.append("| 順位 | コード | 銘柄名 | セクター | 現在値 | 20日リターン | スコア | 推奨ウェイト |")
        md_lines.append("|------|--------|--------|----------|--------|--------------|--------|--------------|")
        for i, row in buy_candidates.iterrows():
            md_lines.append(
                f"| {i+1} | {row['Code']} | {row['CompanyName']} | {row['Sector33Name']} | "
                f"{row['AdjC']:,.0f} | {row['Ret_20']:+.1f}% | {row['Score']:.2f} | {row['weight']:.1%} |"
            )
        md_lines.append("")
    else:
        md_lines.append("### 購入候補: なし\n")
        md_lines.append("推奨銘柄はすべて保有済みです。\n")

    md_lines.append("---\n")
    md_lines.append("## 推奨アクション\n")

    if not sell_candidates.empty and not buy_candidates.empty:
        sell_value = sell_candidates['MarketValue'].sum()
        md_lines.append(f"1. **売却**: {len(sell_candidates)}銘柄（合計約{sell_value:,.0f}円）")
        md_lines.append(f"2. **購入**: {len(buy_candidates)}銘柄（推奨ウェイトに基づく）")
        md_lines.append(f"3. **取引コスト**: 約{sell_value * 0.002:,.0f}円（往復0.2%と仮定）")
    elif sell_candidates.empty and buy_candidates.empty:
        md_lines.append("- **現状維持**: ポートフォリオは既に最適化されています。")
    elif sell_candidates.empty:
        md_lines.append("- **部分的な追加購入**: 推奨銘柄で未保有の銘柄を追加検討")
    else:
        md_lines.append("- **部分的な売却**: モメンタムが低下した銘柄の売却を検討")

    md_lines.append("")
    md_lines.append("## 注意事項\n")
    md_lines.append("- この提案は短期モメンタム戦略に基づいています")
    md_lines.append("- 税金・手数料を考慮した実効リターンを確認してください")
    md_lines.append("- 含み益がある場合、税金の影響を考慮してください")
    md_lines.append("- 一度に全て組み替えるのではなく、段階的な調整も検討してください")
    md_lines.append("- ご自身の投資方針（長期保有 vs スイング）に合わせて判断してください")

    md_path = reports_dir / "portfolio_rebalance_proposal.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))

    console.print(f"  [OK] JSON: {json_path}")
    console.print(f"  [OK] Markdown: {md_path}")

    # コンソール表示
    _print_summary(result)

    return result


def _print_summary(result: dict):
    """分析結果をコンソールに表示"""
    console.print("\n" + "=" * 80)
    console.print("[bold green]ポートフォリオ分析結果[/bold green]\n")

    summary = result['portfolio_summary']

    table = Table(show_header=False)
    table.add_column("項目", style="cyan")
    table.add_column("値", justify="right", style="yellow")

    table.add_row("取得価額合計", f"{summary['total_acquisition_value']:,.0f}円")
    table.add_row("時価総額合計", f"{summary['total_market_value']:,.0f}円")
    table.add_row("含み損益", f"{summary['total_pnl']:+,.0f}円 ({summary['total_pnl_pct']:+.2f}%)")
    table.add_row("保有銘柄数", f"{summary['num_holdings']}銘柄")

    console.print(table)

    # 推奨アクション
    num_sell = len(result['sell_candidates'])
    num_buy = len(result['buy_candidates'])

    console.print("\n[bold cyan]推奨アクション[/bold cyan]")
    if num_sell > 0:
        console.print(f"  [red]売却候補: {num_sell}銘柄[/red]")
    if num_buy > 0:
        console.print(f"  [green]購入候補: {num_buy}銘柄[/green]")
    if num_sell == 0 and num_buy == 0:
        console.print("  [green]現状維持: ポートフォリオは既に最適化されています[/green]")

    console.print("\n" + "=" * 80)


if __name__ == "__main__":
    # ユーザーの保有銘柄（4桁コード → 5桁コードに変換）
    holdings = {
        "16630": 200,
        "27680": 100,
        "41770": 400,
        "47650": 1000,
        "54820": 200,
        "63010": 200,
        "70820": 1000,
        "75250": 100,
        "77170": 100,
        "80110": 100,
        "80500": 100,
        "83060": 100,
    }

    acquisition_prices = {
        "16630": 5066.5,
        "27680": 4527.0,
        "41770": 1180.0,
        "47650": 617.4,
        "54820": 2818.35,
        "63010": 3721.5,
        "70820": 880.34,
        "75250": 2973.0,
        "77170": 3161.5,
        "80110": 2481.0,
        "80500": 2500.0,
        "83060": 1924.0,
    }

    analyze_portfolio(
        holdings=holdings,
        acquisition_prices=acquisition_prices,
        asof_date="2026-03-02",
        top_sectors=3,
        top_stocks=10,
    )
