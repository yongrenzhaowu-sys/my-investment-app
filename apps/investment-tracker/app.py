"""投資判断支援アプリ（Streamlit）"""
import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path
from datetime import datetime
import uuid

from src.auth import JQuantsAuth
from src.api import JQuantsClient
from src.alpha import calculate_alpha
from src.kpi_check import check_exit_kpi
from src.ui_components import render_alpha_chart, render_kpi_alert
from src.simple_gsheets_client import get_simple_gsheets_client

# ページ設定（モバイル最適化）
st.set_page_config(
    page_title="投資判断支援",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# データファイルパス（ローカル環境用）
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
HYPOTHESES_FILE = DATA_DIR / "hypotheses.json"

# Google Sheetsを使用するかどうか判定
def use_gsheets() -> bool:
    """Google Sheetsを使用するか判定"""
    try:
        # Streamlit CloudまたはSecretsでUSE_GSHEETS=trueが設定されている場合
        return st.secrets.get("USE_GSHEETS", False)
    except:
        # ローカル環境（secretsがない場合）
        return False


def load_hypotheses():
    """仮説データを読み込み（Google Sheets or ローカルJSON）"""
    if use_gsheets():
        # シンプルなGoogle Sheetsクライアントから読み込み
        client = get_simple_gsheets_client()
        if client:
            return client.load_hypotheses()
        else:
            st.error("Google Sheets接続エラー。ローカルJSONにフォールバック。")
            return load_hypotheses_local()
    else:
        # ローカルJSONから読み込み
        return load_hypotheses_local()


def load_hypotheses_local():
    """ローカルJSONファイルから仮説データを読み込み"""
    if not HYPOTHESES_FILE.exists():
        return []
    with open(HYPOTHESES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_hypotheses(hypotheses):
    """仮説データを保存（Google Sheets or ローカルJSON）"""
    if use_gsheets():
        # シンプルなGoogle Sheetsクライアントに保存
        client = get_simple_gsheets_client()
        if client:
            client.save_hypotheses(hypotheses)
        else:
            st.error("Google Sheets接続エラー。ローカルJSONにフォールバック。")
            save_hypotheses_local(hypotheses)
    else:
        # ローカルJSONに保存
        save_hypotheses_local(hypotheses)


def save_hypotheses_local(hypotheses):
    """ローカルJSONファイルに仮説データを保存"""
    with open(HYPOTHESES_FILE, "w", encoding="utf-8") as f:
        json.dump(hypotheses, f, ensure_ascii=False, indent=2)


def check_login():
    """
    ログイン認証チェック

    Returns:
        bool: ログイン成功ならTrue
    """
    # セッション状態でログイン状態を保持
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    # 既にログイン済みならTrue
    if st.session_state.logged_in:
        return True

    # ログイン画面を表示
    st.title("🔐 ログイン")

    # Streamlit Secretsからパスワードを取得
    try:
        correct_password = st.secrets["APP_PASSWORD"]
    except (FileNotFoundError, KeyError):
        st.error(
            "APP_PASSWORD が設定されていません。\n"
            ".streamlit/secrets.toml に APP_PASSWORD を設定してください。"
        )
        st.stop()

    # パスワード入力フォーム
    with st.form("login_form"):
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン", width="stretch")

        if submitted:
            if password == correct_password:
                st.session_state.logged_in = True
                st.success("ログイン成功！")
                st.rerun()
            else:
                st.error("パスワードが正しくありません。")

    st.stop()


def initialize_jquants_client():
    """J-Quants APIクライアントを初期化"""
    if "client" not in st.session_state:
        try:
            # Streamlit Secretsから認証情報を取得
            auth = JQuantsAuth(secrets=st.secrets)
            st.session_state.client = JQuantsClient(auth)
            st.session_state.authenticated = True
        except Exception as e:
            st.session_state.authenticated = False
            st.session_state.auth_error = str(e)


def render_sidebar():
    """サイドバーを表示"""
    st.sidebar.title("📋 仮説登録")

    with st.sidebar.form("hypothesis_form"):
        code = st.text_input("銘柄コード（5桁）", placeholder="72030")
        purchase_date = st.date_input("購入日", value=datetime.now())
        purchase_price = st.number_input("購入価格（円）", min_value=1, value=1000)
        reason = st.text_area("購入理由", placeholder="中計で注目している点など...")

        st.subheader("撤退KPI")
        kpi_threshold = st.number_input("営業利益率の閾値（%）", min_value=0.0, value=10.0, step=0.1)

        submitted = st.form_submit_button("登録", width="stretch")

        if submitted:
            if not code or len(code) != 5:
                st.error("銘柄コードは5桁で入力してください")
            elif not reason:
                st.error("購入理由を入力してください")
            else:
                # 銘柄情報取得
                try:
                    with st.spinner("銘柄情報取得中..."):
                        company_info = st.session_state.client.get_company_info(code)
                        company_name = company_info.get("CompanyName", f"銘柄{code}")

                    new_hypothesis = {
                        "id": str(uuid.uuid4()),
                        "code": code,
                        "name": company_name,
                        "purchase_date": purchase_date.strftime("%Y-%m-%d"),
                        "purchase_price": purchase_price,
                        "reason": reason,
                        "exit_kpi": {
                            "metric": "operating_margin",
                            "threshold": kpi_threshold,
                            "operator": "less_than"
                        },
                        "created_at": datetime.now().isoformat()
                    }

                    hypotheses = load_hypotheses()
                    hypotheses.append(new_hypothesis)
                    save_hypotheses(hypotheses)

                    st.success(f"✅ {company_name} を登録しました")
                    st.rerun()

                except Exception as e:
                    st.error(f"エラー: {e}")

    # ログアウトボタン
    st.sidebar.divider()
    if st.sidebar.button("🚪 ログアウト", width="stretch"):
        st.session_state.logged_in = False
        st.rerun()


def render_hypothesis_list():
    """仮説一覧を表示"""
    hypotheses = load_hypotheses()

    if not hypotheses:
        st.info("まだ仮説が登録されていません。サイドバーから登録してください。")
        return

    st.header("📊 保有銘柄一覧")

    for hypo in hypotheses:
        with st.expander(f"**{hypo['name']}** ({hypo['code']})", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**購入日**: {hypo['purchase_date']}")
                st.write(f"**購入価格**: ¥{hypo['purchase_price']:,}")

            with col2:
                st.write(f"**撤退KPI**: 営業利益率 < {hypo['exit_kpi']['threshold']}%")
                st.write(f"**登録日**: {hypo['created_at'][:10]}")

            st.write(f"**購入理由**:\n{hypo['reason']}")

            # ボタン（詳細と削除）
            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                if st.button(f"📊 詳細", key=f"detail_{hypo['id']}", width="stretch"):
                    st.session_state.selected_hypothesis = hypo['id']
                    st.rerun()

            with col_btn2:
                if st.button(f"🗑️ 削除", key=f"delete_{hypo['id']}", width="stretch", type="secondary"):
                    hypotheses_updated = [h for h in hypotheses if h["id"] != hypo['id']]
                    save_hypotheses(hypotheses_updated)
                    st.success(f"{hypo['name']} を削除しました")
                    st.rerun()


def render_hypothesis_detail(hypothesis_id: str):
    """仮説詳細を表示（モバイル最適化）"""
    hypotheses = load_hypotheses()
    hypo = next((h for h in hypotheses if h["id"] == hypothesis_id), None)

    if not hypo:
        st.error("仮説が見つかりませんでした")
        return

    st.header(f"📈 {hypo['name']} ({hypo['code']})")

    # 戻るボタン
    if st.button("← 一覧に戻る", width="stretch"):
        st.session_state.selected_hypothesis = None
        st.rerun()

    st.divider()

    # キャッシュ付きでデータ取得
    with st.spinner("データ取得中..."):
        # 1. アルファ計算
        try:
            stock_return, sp500_return, alpha, df = calculate_alpha(
                st.session_state.client,
                hypo["code"],
                hypo["purchase_date"],
                hypo["purchase_price"]
            )
            alpha_available = True
        except Exception as e:
            st.error(f"アルファ計算エラー: {e}")
            alpha_available = False

        # 2. KPIチェック（エラーでも継続）
        try:
            kpi_result = check_exit_kpi(
                st.session_state.client,
                hypo["code"],
                hypo["exit_kpi"]
            )
            kpi_available = True
        except Exception as e:
            st.warning(f"財務データ取得エラー（KPIチェック不可）: {e}")
            kpi_available = False

    # アルファ計算が成功した場合のみ表示
    if alpha_available:
        # メトリック表示（モバイル最適化：st.metricで強調）
        st.subheader("💰 パフォーマンス")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="個別銘柄",
                value=f"{stock_return:.2f}%",
                delta=None
            )

        with col2:
            st.metric(
                label="S&P500",
                value=f"{sp500_return:.2f}%",
                delta=None
            )

        with col3:
            # アルファの色分け（正なら緑、負なら赤）
            delta_color = "normal" if alpha >= 0 else "inverse"
            st.metric(
                label="アルファ",
                value=f"{alpha:.2f}%",
                delta=f"{alpha:.2f}%",
                delta_color=delta_color
            )

        st.divider()

        # グラフ表示（横幅いっぱい）
        render_alpha_chart(df)

        st.divider()

    # KPI警告（データがある場合のみ）
    if kpi_available:
        st.subheader("🎯 撤退KPIチェック")
        render_kpi_alert(kpi_result)
        st.divider()
    else:
        st.info("💡 財務データが取得できないため、KPIチェックは表示できません")

    st.divider()

    # 購入理由の再確認
    st.subheader("📝 購入理由（再確認）")
    st.info(hypo["reason"])

    # 削除ボタン
    st.divider()
    if st.button("🗑️ この仮説を削除", type="secondary", width="stretch"):
        hypotheses = [h for h in hypotheses if h["id"] != hypothesis_id]
        save_hypotheses(hypotheses)
        st.session_state.selected_hypothesis = None
        st.success("削除しました")
        st.rerun()


def main():
    """メイン処理"""
    # 1. ログイン認証チェック
    check_login()

    # 2. J-Quants APIクライアント初期化
    initialize_jquants_client()

    # 認証チェック
    if not st.session_state.authenticated:
        st.error("### 認証エラー")
        st.error(st.session_state.auth_error)
        st.stop()

    # 3. サイドバー
    render_sidebar()

    # 4. メインコンテンツ
    if "selected_hypothesis" in st.session_state and st.session_state.selected_hypothesis:
        render_hypothesis_detail(st.session_state.selected_hypothesis)
    else:
        render_hypothesis_list()


if __name__ == "__main__":
    main()
