"""
適正株価算出機能の簡易テストスクリプト

実際のJ-Quants APIを使わず、モックデータで動作確認します。
"""

from src.fair_value_models import FinancialData
from src.fair_value_growth import calculate_growth_fair_value
from src.fair_value_value import calculate_value_fair_value


def test_growth_valuation():
    """グロース株評価のテスト"""
    print("=" * 80)
    print("グロース株評価テスト")
    print("=" * 80)

    # モックデータ（架空のグロース株）
    mock_data = FinancialData(
        code="99999",
        company_name="テストグロース株",
        current_price=2000.0,
        shares_outstanding=10_000_000,
        market_cap=20_000,  # 百万円
        sales=[1000, 1200, 1500, 1800, 2200],  # 百万円
        operating_profit=[100, 140, 190, 250, 330],
        ordinary_profit=[],
        net_profit=[80, 112, 152, 200, 264],
        eps_list=[80, 112, 152, 200, 264],  # 円
        bps=500,
        equity=5000,
        total_assets=8000,
        cash=1500,
        debt=2000,
        operating_cf=300,
        investing_cf=-100,
        dividend=None,
        roe=12.0,
        forecast_eps=330,  # 予想EPS
        forecast_net_profit=330,
        historical_per_min=15,
        historical_per_max=35,
        historical_pbr_min=2.0,
        historical_pbr_max=5.0,
        fiscal_periods=["2020-03", "2021-03", "2022-03", "2023-03", "2024-03"]
    )

    # 評価実行
    result = calculate_growth_fair_value(mock_data)

    # 結果表示
    print(f"\n【銘柄情報】")
    print(f"  銘柄名: {result.company_name} ({result.code})")
    print(f"  現在株価: 円{result.current_price:.0f}")

    print(f"\n【成長率分析】")
    print(f"  過去CAGR: {result.growth_analysis.historical_cagr*100:.1f}%")
    print(f"  採用成長率: {result.growth_analysis.adopted_growth*100:.1f}%")
    print(f"  成長率帯: {result.growth_analysis.growth_band}")
    print(f"  成長品質: {result.growth_quality.rank}")

    print(f"\n【PEG・PER分析】")
    print(f"  採用PEG: {result.peg_analysis.adopted_peg:.2f}")
    print(f"  理論PER: {result.per_analysis.theoretical_per:.1f}")
    print(f"  調整後PER: {result.per_analysis.adjusted_per:.1f}")

    print(f"\n【適正株価レンジ】")
    print(f"  保守ケース: 円{result.conservative_price:.0f}")
    print(f"  中央ケース: 円{result.base_price:.0f}")
    print(f"  強気ケース: 円{result.optimistic_price:.0f}")

    print(f"\n【評価】")
    print(f"  判定: {result.current_vs_fair.upper()}")
    print(f"  乖離率: {result.divergence_pct:+.1f}%")
    print(f"  投資判断: {result.investment_comment}")

    print("\n[OK] グロース株評価テスト完了\n")


def test_value_valuation():
    """バリュー株評価のテスト"""
    print("=" * 80)
    print("バリュー株評価テスト")
    print("=" * 80)

    # モックデータ（架空のバリュー株）
    mock_data = FinancialData(
        code="88888",
        company_name="テストバリュー株",
        current_price=800.0,
        shares_outstanding=50_000_000,
        market_cap=40_000,  # 百万円
        sales=[10000, 10200, 9800, 10100, 10300],  # 百万円
        operating_profit=[800, 850, 750, 820, 880],
        ordinary_profit=[],
        net_profit=[600, 640, 560, 615, 660],
        eps_list=[120, 128, 112, 123, 132],  # 円
        bps=1200,  # 1株当たり純資産
        equity=60_000,
        total_assets=100_000,
        cash=15_000,
        debt=25_000,
        operating_cf=1200,
        investing_cf=-300,
        dividend=30,  # 配当30円
        roe=5.5,  # ROE 5.5%
        forecast_eps=140,
        forecast_net_profit=700,
        historical_per_min=6,
        historical_per_max=10,
        historical_pbr_min=0.6,
        historical_pbr_max=1.2,
        fiscal_periods=["2020-03", "2021-03", "2022-03", "2023-03", "2024-03"]
    )

    # 評価実行
    result = calculate_value_fair_value(mock_data)

    # 結果表示
    print(f"\n【銘柄情報】")
    print(f"  銘柄名: {result.company_name} ({result.code})")
    print(f"  現在株価: 円{result.current_price:.0f}")

    print(f"\n【正規化EPS】")
    print(f"  過去平均EPS: {result.normalized_eps.historical_avg_eps:.2f}円")
    print(f"  採用EPS: {result.normalized_eps.adopted_eps:.2f}円")

    print(f"\n【品質評価】")
    print(f"  資産品質: {result.value_quality.asset_quality.rank}")
    print(f"  財務安全性: {result.value_quality.financial_safety.rank}")
    print(f"  ROE水準: {result.value_quality.roe_level}")
    print(f"  還元姿勢: {result.value_quality.dividend_policy}")
    print(f"  総合品質: {result.value_quality.overall_rank}")

    print(f"\n【評価軸】")
    print(f"  評価方法: {result.primary_method.method.upper()}")
    print(f"  採用マルチプル: {result.multiple_analysis.adjusted_multiple:.2f}")

    print(f"\n【適正株価レンジ】")
    print(f"  保守ケース: 円{result.conservative_price:.0f}")
    print(f"  中央ケース: 円{result.base_price:.0f}")
    print(f"  強気ケース: 円{result.optimistic_price:.0f}")

    print(f"\n【評価】")
    print(f"  判定: {result.current_vs_fair.upper()}")
    print(f"  乖離率: {result.divergence_pct:+.1f}%")
    print(f"  安全域: {result.margin_of_safety:.1f}%")
    print(f"  投資判断: {result.investment_comment}")

    print("\n[OK] バリュー株評価テスト完了\n")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("適正株価算出機能 テスト実行")
    print("=" * 80 + "\n")

    try:
        test_growth_valuation()
        test_value_valuation()

        print("=" * 80)
        print("[OK] 全テスト完了")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERROR] テストエラー: {e}")
        import traceback
        traceback.print_exc()
