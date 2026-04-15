"""バリュエーション分析ページ"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import sys

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.valuation_analysis import analyze_stock

# ページ設定
st.set_page_config(
    page_title="バリュエーション分析",
    page_icon="📊",
    layout="wide"
)

# データファイルパス
DATA_DIR = project_root / "data"
HYPOTHESES_FILE = DATA_DIR / "hypotheses.json"


def load_hypotheses():
    """仮説データを読み込み"""
    if not HYPOTHESES_FILE.exists():
        return []

    with open(HYPOTHESES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def render_signal_badge(signal):
    """シグナルバッジを表示"""
    if signal == 'BUY':
        return "🟢 買い"
    elif signal == 'SELL':
        return "🔴 売り"
    elif signal == 'HOLD':
        return "🟡 保持"
    else:
        return "⚪ -"


def render_analysis_result(result):
    """分析結果を表示"""
    st.markdown("---")

    # ヘッダー
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.subheader(f"銘柄コード: {result['code']}")

    with col2:
        # 現在株価と最小理論株価
        current_price = result.get('current_price')
        min_theoretical = result.get('min_theoretical_price')
        min_method = result.get('min_theoretical_method')
        divergence = result.get('divergence_from_min')

        if current_price is not None and min_theoretical is not None:
            st.metric(
                "現在株価",
                f"¥{current_price:.0f}",
                delta=f"{divergence:+.1f}%" if divergence is not None else None,
                delta_color="inverse"  # プラス（割高）は赤、マイナス（割安）は緑
            )
            st.caption(f"最小理論株価（{min_method}）: ¥{min_theoretical:.0f}")

    with col3:
        overall_signal = result['overall_signal']
        if overall_signal == 'BUY':
            st.success(f"総合判定: {render_signal_badge(overall_signal)}")
        elif overall_signal == 'SELL':
            st.error(f"総合判定: {render_signal_badge(overall_signal)}")
        elif overall_signal == 'HOLD':
            st.warning(f"総合判定: {render_signal_badge(overall_signal)}")
        else:
            st.info(f"総合判定: {render_signal_badge(overall_signal)}")

    # 4つの分析結果を表示
    cols = st.columns(4)

    # 1. PEG Ratio
    with cols[0]:
        st.markdown("**PEG Ratio**")
        peg = result['peg_ratio']

        if peg.get('error'):
            st.warning(f"⚠️ {peg['error']}")
        else:
            st.metric("PEG", f"{peg.get('peg_ratio', 0):.2f}")
            st.caption(f"PER: {peg.get('per', 0):.1f}")
            st.caption(f"成長率: {peg.get('growth_rate', 0)*100:.1f}%")
            if peg.get('theoretical_price') is not None:
                st.caption(f"理論株価: ¥{peg.get('theoretical_price', 0):.0f}")
            st.markdown(render_signal_badge(peg.get('signal')))

    # 2. 移動平均乖離
    with cols[1]:
        st.markdown("**移動平均**")
        ma = result['ma_divergence']

        if ma.get('error'):
            st.warning(f"⚠️ {ma['error']}")
        else:
            st.metric("25日MA乖離", f"{ma.get('divergence_25', 0):.1f}%")
            st.caption(f"現在: ¥{ma.get('current_price', 0):.0f}")
            st.caption(f"25日MA: ¥{ma.get('ma_25', 0):.0f}")
            st.caption(f"75日MA: ¥{ma.get('ma_75', 0):.0f}")
            st.markdown(render_signal_badge(ma.get('signal')))

    # 3. EV/EBITDA
    with cols[2]:
        st.markdown("**EV/EBITDA**")
        ev = result['ev_ebitda']

        if ev.get('error'):
            st.warning(f"⚠️ {ev['error']}")
        else:
            st.metric("EV/EBITDA", f"{ev.get('ev_ebitda', 0):.1f}")
            st.caption(f"EV: {ev.get('ev', 0)/1e9:.0f}億円")
            st.caption(f"EBITDA: {ev.get('ebitda', 0)/1e9:.0f}億円")
            if ev.get('theoretical_price') is not None:
                st.caption(f"理論株価: ¥{ev.get('theoretical_price', 0):.0f}")
            st.markdown(render_signal_badge(ev.get('signal')))

    # 4. DCF Proxy
    with cols[3]:
        st.markdown("**DCF Proxy**")
        dcf = result['dcf_proxy']

        if dcf.get('error'):
            st.warning(f"⚠️ {dcf['error']}")
        else:
            ratio = dcf.get('price_to_theoretical', 0)
            st.metric("株価/理論株価", f"{ratio:.2f}")
            st.caption(f"現在: ¥{dcf.get('current_price', 0):.0f}")
            st.caption(f"理論: ¥{dcf.get('theoretical_price', 0):.0f}")
            st.markdown(render_signal_badge(dcf.get('signal')))


def main():
    """メイン処理"""
    st.title("📊 バリュエーション分析")
    st.markdown("保有銘柄に対して4つのバリュエーション分析を実行します。")

    # 仮説データ読み込み
    hypotheses = load_hypotheses()

    if len(hypotheses) == 0:
        st.info("保有銘柄がありません。「仮説登録」ページから銘柄を登録してください。")
        return

    st.info(f"保有銘柄数: {len(hypotheses)}銘柄")

    # 分析実行ボタン
    if st.button("🔍 全銘柄を分析", type="primary", use_container_width=True):
        with st.spinner("分析中..."):
            results = []

            # プログレスバー
            progress_bar = st.progress(0)

            for idx, hypo in enumerate(hypotheses):
                code = hypo.get('code')

                if code:
                    # 分析実行
                    result = analyze_stock(code)
                    results.append(result)

                # プログレス更新
                progress = (idx + 1) / len(hypotheses)
                progress_bar.progress(progress)

            progress_bar.empty()

            # 結果を保存（セッション状態）
            st.session_state.valuation_results = results
            st.success("分析完了！")

    # 結果表示
    if 'valuation_results' in st.session_state:
        results = st.session_state.valuation_results

        # サマリー表示
        st.markdown("---")
        st.subheader("📈 分析サマリー")

        # シグナル集計
        buy_count = sum(1 for r in results if r['overall_signal'] == 'BUY')
        hold_count = sum(1 for r in results if r['overall_signal'] == 'HOLD')
        sell_count = sum(1 for r in results if r['overall_signal'] == 'SELL')

        col1, col2, col3 = st.columns(3)
        col1.metric("🟢 買い推奨", f"{buy_count}銘柄")
        col2.metric("🟡 保持推奨", f"{hold_count}銘柄")
        col3.metric("🔴 売り推奨", f"{sell_count}銘柄")

        # 詳細結果表示
        st.markdown("---")
        st.subheader("📋 詳細結果")

        # フィルター
        filter_option = st.selectbox(
            "フィルター",
            ["全て", "買い推奨のみ", "売り推奨のみ", "保持推奨のみ"]
        )

        # フィルタリング
        if filter_option == "買い推奨のみ":
            filtered_results = [r for r in results if r['overall_signal'] == 'BUY']
        elif filter_option == "売り推奨のみ":
            filtered_results = [r for r in results if r['overall_signal'] == 'SELL']
        elif filter_option == "保持推奨のみ":
            filtered_results = [r for r in results if r['overall_signal'] == 'HOLD']
        else:
            filtered_results = results

        # 結果表示
        for result in filtered_results:
            render_analysis_result(result)

    # 使い方ガイド
    with st.expander("📖 使い方ガイド"):
        st.markdown("""
        ### 分析指標の説明

        #### 1. PEG Ratio（株価収益成長率）
        - **計算式**: PEG = PER / (成長率 × 100)
        - **判定基準**:
          - PEG < 1.0: 🟢 割安（成長性に対して株価が低い）
          - PEG 1.0-2.0: 🟡 適正
          - PEG > 2.0: 🔴 割高

        #### 2. 移動平均乖離
        - **対象**: 25日移動平均線（短期）、75日移動平均線（中期）
        - **シグナル**:
          - ゴールデンクロス: 🟢 買いシグナル
          - デッドクロス: 🔴 売りシグナル
          - 現在価格が両MAより上: 🟡 強気トレンド

        #### 3. EV/EBITDA（簡易版）
        - **計算式**: EV/EBITDA = (時価総額 + 純負債) / EBITDA
        - **注**: EBITDAの代わりに営業利益を使用
        - **判定基準**:
          - EV/EBITDA < 10: 🟢 割安
          - EV/EBITDA 10-15: 🟡 適正
          - EV/EBITDA > 15: 🔴 割高

        #### 4. DCF Proxy（簡易版）
        - **計算式**: 理論株価 = FCF / WACC / 発行済株式数
        - **判定基準**:
          - 現在株価 / 理論株価 < 0.8: 🟢 割安
          - 0.8-1.2: 🟡 適正
          - > 1.2: 🔴 割高

        ### 総合判定
        4つの指標のシグナルを多数決で判定します。
        """)

    # データソース情報
    with st.expander("ℹ️ データソース"):
        st.markdown("""
        - **財務データ**: J-Quants API（2021-2026年）
        - **株価データ**: J-Quants API（2021-2026年、調整済み株価）
        - **更新頻度**: 手動更新（最新データは別途取得が必要）
        """)


if __name__ == "__main__":
    main()
