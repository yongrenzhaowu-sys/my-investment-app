"""
適正株価算出機能のUI表示モジュール

Streamlit UIコンポーネントをまとめます。
"""

import streamlit as st
from typing import Optional
from src.fair_value_models import GrowthFairValue, ValueFairValue
from src.fair_value_data_builder import build_financial_data_from_api
from src.fair_value_growth import calculate_growth_fair_value
from src.fair_value_value import calculate_value_fair_value


def render_growth_result(result: GrowthFairValue):
    """
    グロース株評価結果を表示

    Args:
        result: グロース株適正株価評価結果
    """
    st.markdown("---")
    st.subheader(f"📈 グロース株評価: {result.company_name} ({result.code})")

    # サマリーカード
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "現在株価",
            f"¥{result.current_price:.0f}"
        )

    with col2:
        # 評価に応じて色を変更
        if result.current_vs_fair == 'undervalued':
            delta_color = "normal"  # 緑（割安は良い）
        elif result.current_vs_fair == 'overvalued':
            delta_color = "inverse"  # 赤（割高は悪い）
        else:
            delta_color = "off"

        st.metric(
            "中央ケース",
            f"¥{result.base_price:.0f}",
            delta=f"{result.divergence_pct:+.1f}%",
            delta_color=delta_color
        )

    with col3:
        st.metric(
            "採用PEG",
            f"{result.peg_analysis.adopted_peg:.2f}"
        )

    with col4:
        st.metric(
            "採用PER",
            f"{result.per_analysis.adjusted_per:.1f}x"
        )

    # 評価判定バッジ
    if result.current_vs_fair == 'undervalued':
        st.success(f"✅ 評価: 割安（{result.divergence_pct:.1f}%アンダーバリュー）")
    elif result.current_vs_fair == 'overvalued':
        st.error(f"⚠️ 評価: 割高（{result.divergence_pct:.1f}%オーバーバリュー）")
    else:
        st.info(f"📊 評価: 適正（乖離{result.divergence_pct:+.1f}%）")

    # 投資判断コメント
    st.markdown(f"**💬 投資判断**: {result.investment_comment}")

    # 株価レンジ
    st.markdown("---")
    st.markdown("**📊 適正株価レンジ**")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("保守ケース", f"¥{result.conservative_price:.0f}")
        st.caption(f"今期EPS {result.current_eps:.2f}円 × PER {result.per_analysis.adjusted_per:.1f}")

    with col2:
        st.metric("中央ケース", f"¥{result.base_price:.0f}")
        st.caption(f"来期EPS {result.next_eps:.2f}円 × PER {result.per_analysis.adjusted_per:.1f}")

    with col3:
        st.metric("強気ケース", f"¥{result.optimistic_price:.0f}")
        st.caption(f"再来期EPS想定 × PER {result.per_analysis.adjusted_per:.1f}")

    # 詳細情報（折りたたみ）
    with st.expander("🔍 詳細分析"):
        # 成長率分析
        st.markdown("### 📈 成長率分析")
        for reason in result.growth_analysis.reasons:
            st.markdown(f"- {reason}")

        # 成長品質
        st.markdown("### ⭐ 成長品質")
        for reason in result.growth_quality.reasons:
            st.markdown(f"- {reason}")

        # PEG分析
        st.markdown("### 🎯 PEGレシオ分析")
        for reason in result.peg_analysis.reasons:
            st.markdown(f"- {reason}")

        # PER分析
        st.markdown("### 💹 PER分析")
        for reason in result.per_analysis.adjustment_reasons:
            st.markdown(f"- {reason}")


def render_value_result(result: ValueFairValue):
    """
    バリュー株評価結果を表示

    Args:
        result: バリュー株適正株価評価結果
    """
    st.markdown("---")
    st.subheader(f"💎 バリュー株評価: {result.company_name} ({result.code})")

    # サマリーカード
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "現在株価",
            f"¥{result.current_price:.0f}"
        )

    with col2:
        # 評価に応じて色を変更
        if result.current_vs_fair == 'undervalued':
            delta_color = "normal"
        elif result.current_vs_fair == 'overvalued':
            delta_color = "inverse"
        else:
            delta_color = "off"

        st.metric(
            "中央ケース",
            f"¥{result.base_price:.0f}",
            delta=f"{result.divergence_pct:+.1f}%",
            delta_color=delta_color
        )

    with col3:
        method_name = {'pbr': 'PBR', 'per': 'PER', 'ev_ebitda': 'EV/EBITDA'}.get(
            result.primary_method.method, result.primary_method.method
        )
        st.metric(
            f"採用{method_name}",
            f"{result.multiple_analysis.adjusted_multiple:.2f}x"
        )

    with col4:
        st.metric(
            "安全域",
            f"{result.margin_of_safety:.1f}%"
        )

    # 評価判定バッジ
    if result.current_vs_fair == 'undervalued':
        st.success(f"✅ 評価: 割安（安全域{result.margin_of_safety:.1f}%）")
    elif result.current_vs_fair == 'overvalued':
        st.error(f"⚠️ 評価: 割高（{result.margin_of_safety:.1f}%オーバーバリュー）")
    else:
        st.info(f"📊 評価: 適正（安全域{result.margin_of_safety:+.1f}%）")

    # 投資判断コメント
    st.markdown(f"**💬 投資判断**: {result.investment_comment}")

    # 株価レンジ
    st.markdown("---")
    st.markdown("**📊 適正株価レンジ**")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("保守ケース", f"¥{result.conservative_price:.0f}")

    with col2:
        st.metric("中央ケース", f"¥{result.base_price:.0f}")

    with col3:
        st.metric("強気ケース", f"¥{result.optimistic_price:.0f}")

    # 詳細情報（折りたたみ）
    with st.expander("🔍 詳細分析"):
        # 正規化EPS
        st.markdown("### 💰 正規化EPS")
        for reason in result.normalized_eps.reasons:
            st.markdown(f"- {reason}")

        # 品質評価
        st.markdown("### ⭐ 品質評価")
        for reason in result.value_quality.reasons:
            st.markdown(f"- {reason}")

        # 評価軸
        st.markdown("### 🎯 評価軸")
        for reason in result.primary_method.reasons:
            st.markdown(f"- {reason}")

        # マルチプル分析
        st.markdown("### 💹 マルチプル分析")
        for reason in result.multiple_analysis.adjustment_reasons:
            st.markdown(f"- {reason}")


def render_fair_value_analysis(client, hypotheses):
    """
    適正株価分析画面を表示（既存のバリュエーション分析に統合）

    Args:
        client: JQuantsClient
        hypotheses: 保有銘柄リスト
    """
    st.markdown("---")
    st.header("💰 適正株価算出（新機能）")
    st.markdown("グロース株・バリュー株それぞれの適正株価を算出します。")

    # 銘柄選択
    if not hypotheses:
        st.info("保有銘柄がありません。「📋 仮説登録」から銘柄を登録してください。")
        return

    # 銘柄コード一覧
    stock_codes = [h.get('code') for h in hypotheses if h.get('code')]
    stock_names = [f"{h.get('code')} - {h.get('name')}" for h in hypotheses if h.get('code')]

    selected_stock_display = st.selectbox(
        "分析する銘柄を選択",
        stock_names,
        key="fair_value_stock_select"
    )

    # 選択された銘柄コードを抽出
    selected_code = selected_stock_display.split(' - ')[0] if selected_stock_display else None

    if not selected_code:
        return

    # 評価タイプ選択
    eval_type = st.radio(
        "評価タイプ",
        ["🚀 グロース株評価", "💎 バリュー株評価", "🔄 両方"],
        horizontal=True
    )

    # 分析実行ボタン
    if st.button("🔍 適正株価を算出", type="primary", use_container_width=True):
        with st.spinner(f"{selected_code} のデータを取得中..."):
            # FinancialDataモデル構築
            financial_data = build_financial_data_from_api(client, selected_code)

            if financial_data is None:
                st.error("データ取得に失敗しました。J-Quants APIのレスポンスを確認してください。")
                return

        # グロース株評価
        if eval_type in ["🚀 グロース株評価", "🔄 両方"]:
            with st.spinner("グロース株評価を実行中..."):
                try:
                    growth_result = calculate_growth_fair_value(financial_data)
                    render_growth_result(growth_result)
                except Exception as e:
                    st.error(f"グロース株評価エラー: {e}")
                    import traceback
                    st.code(traceback.format_exc())

        # バリュー株評価
        if eval_type in ["💎 バリュー株評価", "🔄 両方"]:
            with st.spinner("バリュー株評価を実行中..."):
                try:
                    value_result = calculate_value_fair_value(financial_data)
                    render_value_result(value_result)
                except Exception as e:
                    st.error(f"バリュー株評価エラー: {e}")
                    import traceback
                    st.code(traceback.format_exc())
