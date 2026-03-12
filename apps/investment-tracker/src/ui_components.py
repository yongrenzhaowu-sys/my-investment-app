"""UI部品モジュール"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd


def render_metric_card(label: str, value: float, delta: float = None, color: str = "normal"):
    """
    メトリックカードを表示

    Args:
        label: ラベル
        value: 値
        delta: 変化量（オプション）
        color: カラー（"normal", "inverse"）
    """
    st.metric(
        label=label,
        value=f"{value:.2f}%",
        delta=f"{delta:.2f}%" if delta is not None else None,
        delta_color=color
    )


def render_alpha_chart(df: pd.DataFrame):
    """
    アルファ推移チャートを表示（モバイル最適化）

    Args:
        df: 時系列データフレーム（Date, stock_return, sp500_return, alpha）
    """
    fig = go.Figure()

    # 個別銘柄
    fig.add_trace(go.Scatter(
        x=df["Date"],
        y=df["stock_return"],
        mode="lines",
        name="個別銘柄",
        line=dict(color="#1f77b4", width=3)
    ))

    # S&P500
    fig.add_trace(go.Scatter(
        x=df["Date"],
        y=df["sp500_return"],
        mode="lines",
        name="S&P500",
        line=dict(color="#7f7f7f", width=2, dash="dash")
    ))

    # アルファ（塗りつぶし）
    fig.add_trace(go.Scatter(
        x=df["Date"],
        y=df["alpha"],
        mode="lines",
        name="アルファ",
        fill="tozeroy",
        line=dict(color="#2ca02c", width=2),
        fillcolor="rgba(44, 160, 44, 0.2)"
    ))

    # モバイル最適化レイアウト
    fig.update_layout(
        title={
            "text": "アルファ推移（個別 vs S&P500）",
            "font": {"size": 18}
        },
        xaxis_title="",
        yaxis_title="騰落率 (%)",
        hovermode="x unified",
        height=450,  # モバイルでも見やすい高さ
        margin=dict(l=10, r=10, t=40, b=10),  # 余白を最小化
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
        font=dict(size=14)  # フォントサイズを大きく
    )

    # グリッドを見やすく
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

    st.plotly_chart(fig, width="stretch")


def render_kpi_alert(kpi_result: dict):
    """
    KPI警告カードを表示

    Args:
        kpi_result: check_exit_kpiの結果
    """
    if kpi_result["triggered"]:
        st.error(f"### {kpi_result['message']}")
        st.warning(f"最新決算期: {kpi_result['latest_fiscal_period']}")
    else:
        st.success(f"### {kpi_result['message']}")
        st.info(f"最新決算期: {kpi_result['latest_fiscal_period']}")
