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
from src.trading_history import add_sell_record, load_trading_history
from src.profit_calculator import (
    calculate_realized_profit,
    calculate_unrealized_profit,
    calculate_total_profit,
    calculate_available_capital,
    calculate_yearly_profit
)
from src.settings import load_settings, save_settings

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
    # セッション状態にキャッシュがあればそれを使う（最優先）
    if "hypotheses_cache" in st.session_state:
        return st.session_state.hypotheses_cache

    # キャッシュがない場合のみ、外部から読み込む
    if use_gsheets():
        # シンプルなGoogle Sheetsクライアントから読み込み
        client = get_simple_gsheets_client()
        if client:
            hypotheses = client.load_hypotheses()
        else:
            st.error("Google Sheets接続エラー。ローカルJSONにフォールバック。")
            hypotheses = load_hypotheses_local()
    else:
        # ローカルJSONから読み込み
        hypotheses = load_hypotheses_local()

    # セッション状態にキャッシュ
    st.session_state.hypotheses_cache = hypotheses
    return hypotheses


def load_hypotheses_local():
    """ローカルJSONファイルから仮説データを読み込み"""
    if not HYPOTHESES_FILE.exists():
        return []
    with open(HYPOTHESES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_hypotheses(hypotheses):
    """仮説データを保存（Google Sheets or ローカルJSON）"""
    # まずセッション状態を更新（即座に反映）
    st.session_state.hypotheses_cache = hypotheses

    # 次に永続化ストレージに保存（バックグラウンド）
    if use_gsheets():
        # シンプルなGoogle Sheetsクライアントに保存
        client = get_simple_gsheets_client()
        if client:
            client.save_hypotheses(hypotheses)
            # 注: Google Sheetsへの保存は非同期的に行われる
            # セッション状態をマスターデータとするため、反映を待つ必要はない
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
    # メニュー選択
    st.sidebar.title("📱 メニュー")
    menu = st.sidebar.radio(
        "選択してください",
        ["📋 仮説登録", "📊 損益サマリー", "📜 売買履歴"],
        label_visibility="collapsed"
    )

    # メニューに応じた画面を表示
    if menu == "📊 損益サマリー":
        st.session_state.current_view = "profit_summary"
    elif menu == "📜 売買履歴":
        st.session_state.current_view = "trading_history"
    else:
        st.session_state.current_view = "main"

    st.sidebar.divider()
    st.sidebar.title("📋 仮説登録")

    with st.sidebar.form("hypothesis_form"):
        code = st.text_input("銘柄コード（5桁）", placeholder="72030")
        purchase_date = st.date_input("購入日", value=datetime.now())
        purchase_price = st.number_input("購入価格（円/株）", min_value=1, value=1000)
        shares = st.number_input("購入数量（株）", min_value=1, value=100, step=100)
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
                        "shares": shares,
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

    # ヘッダーと一括更新ボタン
    col_header, col_button = st.columns([3, 1])

    with col_header:
        st.header("📊 保有銘柄一覧")

    with col_button:
        if st.button("🔄 銘柄名更新", help="全銘柄の名前を最新情報に更新", type="secondary"):
            # 一括更新処理
            with st.spinner("銘柄名を更新中..."):
                updated_count = 0
                error_count = 0

                for hypo in hypotheses:
                    try:
                        # 銘柄情報を再取得
                        company_info = st.session_state.client.get_company_info(hypo["code"])
                        new_name = company_info.get("CompanyName", f"銘柄{hypo['code']}")

                        # 名前が変わった場合のみ更新
                        if new_name != hypo.get("name", ""):
                            hypo["name"] = new_name
                            updated_count += 1
                    except Exception as e:
                        error_count += 1
                        st.warning(f"銘柄 {hypo['code']} の更新に失敗: {e}")

                # 保存
                save_hypotheses(hypotheses)

                # 結果表示
                if updated_count > 0:
                    st.success(f"✅ {updated_count}件の銘柄名を更新しました")
                else:
                    st.info("更新対象がありませんでした")

                if error_count > 0:
                    st.error(f"❌ {error_count}件のエラーが発生しました")

                # 画面を再描画
                st.rerun()

    for hypo in hypotheses:
        with st.expander(f"**{hypo['name']}** ({hypo['code']})", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**購入日**: {hypo['purchase_date']}")
                st.write(f"**購入価格**: ¥{hypo['purchase_price']:,}/株")
                shares = hypo.get('shares', 100)  # デフォルト100株
                st.write(f"**購入数量**: {shares:,}株")

            with col2:
                total_investment = hypo['purchase_price'] * shares
                st.write(f"**投資額**: ¥{total_investment:,}")
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

    # アクションボタン
    st.divider()
    col_action1, col_action2, col_action3 = st.columns(3)

    with col_action1:
        if st.button("✏️ 編集", width="stretch"):
            st.session_state.edit_hypothesis_id = hypothesis_id
            st.rerun()

    with col_action2:
        if st.button("📤 売却", type="primary", width="stretch"):
            st.session_state.sell_hypothesis_id = hypothesis_id
            st.rerun()

    with col_action3:
        if st.button("🗑️ 削除", type="secondary", width="stretch"):
            hypotheses = [h for h in hypotheses if h["id"] != hypothesis_id]
            save_hypotheses(hypotheses)
            st.session_state.selected_hypothesis = None
            st.success("削除しました")
            st.rerun()


def render_edit_form(hypothesis_id: str):
    """編集フォームを表示"""
    hypotheses = load_hypotheses()
    hypo = next((h for h in hypotheses if h["id"] == hypothesis_id), None)

    if not hypo:
        st.error("仮説が見つかりませんでした")
        return

    st.header(f"✏️ 編集: {hypo['name']} ({hypo['code']})")

    # 戻るボタン
    if st.button("← 詳細に戻る", width="stretch"):
        del st.session_state.edit_hypothesis_id
        st.rerun()

    st.divider()

    # 編集フォーム
    with st.form("edit_form"):
        st.subheader("基本情報")

        # 銘柄コードは変更不可
        st.text_input("銘柄コード（変更不可）", value=hypo['code'], disabled=True)
        st.text_input("銘柄名（変更不可）", value=hypo.get('name', f"銘柄{hypo['code']}"), disabled=True)

        st.divider()

        # 編集可能な項目
        from datetime import datetime as dt
        current_purchase_date = dt.strptime(hypo["purchase_date"], "%Y-%m-%d").date()

        purchase_date = st.date_input("購入日", value=current_purchase_date)
        purchase_price = st.number_input(
            "購入価格（円/株）",
            min_value=1,
            value=int(hypo["purchase_price"])
        )
        shares = st.number_input(
            "購入数量（株）",
            min_value=1,
            value=int(hypo.get("shares", 100)),
            step=100
        )
        reason = st.text_area(
            "購入理由",
            value=hypo["reason"]
        )

        st.subheader("撤退KPI")
        kpi_threshold = st.number_input(
            "営業利益率の閾値（%）",
            min_value=0.0,
            value=float(hypo["exit_kpi"]["threshold"]),
            step=0.1
        )

        st.divider()

        # 投資額を表示
        total_investment = purchase_price * shares
        st.info(f"**投資額**: ¥{total_investment:,}")

        submitted = st.form_submit_button("✅ 保存", type="primary", width="stretch")

        if submitted:
            if not reason:
                st.error("購入理由を入力してください")
            else:
                try:
                    # 仮説データを更新
                    updated_hypo = {
                        "id": hypo["id"],
                        "code": hypo["code"],
                        "name": hypo.get("name", f"銘柄{hypo['code']}"),
                        "purchase_date": purchase_date.strftime("%Y-%m-%d"),
                        "purchase_price": purchase_price,
                        "shares": shares,
                        "reason": reason,
                        "exit_kpi": {
                            "metric": "operating_margin",
                            "threshold": kpi_threshold,
                            "operator": "less_than"
                        },
                        "created_at": hypo.get("created_at", datetime.now().isoformat())
                    }

                    # 仮説リストを更新
                    hypotheses = [updated_hypo if h["id"] == hypothesis_id else h for h in hypotheses]
                    save_hypotheses(hypotheses)

                    st.success("✅ 更新しました")

                    # セッション状態をクリア
                    del st.session_state.edit_hypothesis_id
                    st.rerun()

                except Exception as e:
                    st.error(f"エラー: {e}")


def render_sell_form(hypothesis_id: str):
    """売却フォームを表示"""
    hypotheses = load_hypotheses()
    hypo = next((h for h in hypotheses if h["id"] == hypothesis_id), None)

    if not hypo:
        st.error("仮説が見つかりませんでした")
        return

    st.header(f"📤 売却: {hypo['name']} ({hypo['code']})")

    # 戻るボタン
    if st.button("← 詳細に戻る", width="stretch"):
        del st.session_state.sell_hypothesis_id
        st.rerun()

    st.divider()

    # 売却フォーム
    with st.form("sell_form"):
        st.subheader("売却情報")

        sell_date = st.date_input("売却日", value=datetime.now())
        sell_price = st.number_input("売却価格（円）", min_value=1, value=int(hypo["purchase_price"]))
        sell_reason = st.text_area(
            "売却理由",
            placeholder="例: 目標価格到達、損切り、資金需要、KPI未達成など..."
        )

        st.divider()

        # 予想損益を表示（株数を考慮）
        shares = hypo.get("shares", 100)
        expected_profit_per_share = sell_price - hypo["purchase_price"]
        expected_profit = expected_profit_per_share * shares
        expected_profit_rate = (expected_profit_per_share / hypo["purchase_price"]) * 100 if hypo["purchase_price"] > 0 else 0
        expected_tax = max(0, expected_profit * 0.20315)
        expected_after_tax = expected_profit - expected_tax

        st.info(f"**保有株数**: {shares:,}株")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("実現損益", f"¥{expected_profit:,.0f}", f"{expected_profit_rate:+.2f}%")
        with col2:
            st.metric("税引き後利益", f"¥{expected_after_tax:,.0f}")

        st.caption(f"税金: ¥{expected_tax:,.0f} (20.315%) | 1株あたり損益: ¥{expected_profit_per_share:,.0f}")

        submitted = st.form_submit_button("✅ 売却を確定", type="primary", width="stretch")

        if submitted:
            if not sell_reason:
                st.error("売却理由を入力してください")
            elif sell_date < datetime.strptime(hypo["purchase_date"], "%Y-%m-%d").date():
                st.error("売却日は購入日以降にしてください")
            else:
                try:
                    # 売却記録を追加
                    record = add_sell_record(
                        hypo,
                        sell_date.strftime("%Y-%m-%d"),
                        sell_price,
                        sell_reason
                    )

                    # 仮説から削除
                    hypotheses = [h for h in hypotheses if h["id"] != hypothesis_id]
                    save_hypotheses(hypotheses)

                    st.success(f"✅ {hypo['name']} を売却しました")
                    st.success(f"実現損益: ¥{record.realized_profit:,.0f} ({record.realized_profit_rate:+.2f}%)")
                    st.success(f"税引き後利益: ¥{record.after_tax_profit:,.0f}")

                    # セッション状態をクリア
                    del st.session_state.sell_hypothesis_id
                    st.session_state.selected_hypothesis = None
                    st.rerun()

                except Exception as e:
                    st.error(f"エラー: {e}")


def render_profit_summary():
    """損益サマリー画面を表示"""
    st.header("📊 損益サマリー")

    hypotheses = load_hypotheses()
    current_year = datetime.now().year

    # 実現損益
    realized = calculate_realized_profit()
    st.subheader("💰 実現損益（売却済み）")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("売却済み銘柄数", f"{realized['count']}銘柄")
    with col2:
        st.metric("累計実現損益", f"¥{realized['total_profit']:,.0f}")
    with col3:
        st.metric("税引き後利益", f"¥{realized['after_tax_profit']:,.0f}")

    st.caption(f"累計税金: ¥{realized['total_tax']:,.0f}")

    st.divider()

    # 含み損益
    unrealized = calculate_unrealized_profit(hypotheses)
    st.subheader("📈 含み損益（保持中）")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("保持中銘柄数", f"{unrealized['count']}銘柄")
    with col2:
        st.metric("累計含み損益", f"¥{unrealized['total_unrealized']:,.0f}")

    # 銘柄別の詳細
    if unrealized['details']:
        with st.expander("📋 銘柄別の含み損益"):
            for detail in unrealized['details']:
                st.write(f"**{detail['name']} ({detail['code']})**")
                st.write(f"保有株数: {detail['shares']:,}株")
                st.write(f"購入価格: ¥{detail['purchase_price']:,.0f}/株 → 現在価格: ¥{detail['current_price']:,.0f}/株")
                st.write(f"含み損益: ¥{detail['unrealized_profit']:,.0f} ({detail['unrealized_profit_rate']:+.2f}%)")
                st.divider()

    st.divider()

    # 合計損益
    total_profit = calculate_total_profit(hypotheses)
    st.subheader("🎯 合計損益")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("実現損益", f"¥{total_profit['realized']:,.0f}")
    with col2:
        st.metric("含み損益", f"¥{total_profit['unrealized']:,.0f}")
    with col3:
        st.metric("合計損益", f"¥{total_profit['total']:,.0f}")

    st.divider()

    # 余力
    st.subheader("💵 余力（投資可能額）")

    # 初期資金の設定（settings.jsonに永続化）
    if "initial_capital" not in st.session_state:
        # settings.jsonから読み込み
        settings = load_settings()
        st.session_state.initial_capital = settings.get("initial_capital", 1_000_000)

    with st.expander("⚙️ 初期資金設定"):
        new_capital = st.number_input(
            "初期資金（円）",
            min_value=0,
            value=st.session_state.initial_capital,
            step=100_000,
            help="ログイン後も保持されます"
        )
        if st.button("更新", key="update_initial_capital"):
            # セッション状態を更新
            st.session_state.initial_capital = new_capital

            # settings.jsonに保存
            settings = load_settings()
            settings["initial_capital"] = new_capital
            if save_settings(settings):
                st.success("✅ 初期資金を更新しました（永続化済み）")
            else:
                st.warning("⚠️ 初期資金を更新しました（永続化に失敗）")
            st.rerun()

    available = calculate_available_capital(hypotheses, st.session_state.initial_capital)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("初期資金", f"¥{available['initial_capital']:,.0f}")
    with col2:
        st.metric("現在保有額", f"¥{available['current_investment']:,.0f}")
    with col3:
        st.metric("累計売却額", f"¥{available['cumulative_sales']:,.0f}")
    with col4:
        st.metric("余力", f"¥{available['available_capital']:,.0f}")

    st.divider()

    # 年間損益（確定申告用）
    yearly = calculate_yearly_profit(current_year)
    st.subheader(f"📅 年間損益（{current_year}年）")
    st.caption("※確定申告用")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("売却件数", f"{yearly['count']}件")
    with col2:
        st.metric("年間実現損益", f"¥{yearly['total_profit']:,.0f}")
    with col3:
        st.metric("税引き後利益", f"¥{yearly['after_tax_profit']:,.0f}")

    st.caption(f"年間税金: ¥{yearly['total_tax']:,.0f}")


def render_trading_history():
    """売買履歴一覧を表示"""
    st.header("📜 売買履歴")

    history = load_trading_history()

    if not history:
        st.info("まだ売買履歴がありません。")
        return

    # フィルタリング
    col_filter1, col_filter2 = st.columns(2)

    with col_filter1:
        years = sorted(set(record["sell_date"][:4] for record in history), reverse=True)
        selected_year = st.selectbox("年を選択", ["全て"] + years)

    with col_filter2:
        sort_by = st.selectbox("並び順", ["売却日（新しい順）", "売却日（古い順）", "損益（大きい順）", "損益（小さい順）"])

    # フィルタリング処理
    filtered_history = history
    if selected_year != "全て":
        filtered_history = [r for r in filtered_history if r["sell_date"].startswith(selected_year)]

    # ソート処理
    if sort_by == "売却日（新しい順）":
        filtered_history = sorted(filtered_history, key=lambda x: x["sell_date"], reverse=True)
    elif sort_by == "売却日（古い順）":
        filtered_history = sorted(filtered_history, key=lambda x: x["sell_date"])
    elif sort_by == "損益（大きい順）":
        filtered_history = sorted(filtered_history, key=lambda x: x["realized_profit"], reverse=True)
    else:
        filtered_history = sorted(filtered_history, key=lambda x: x["realized_profit"])

    st.divider()

    # テーブル表示
    st.subheader(f"📋 売買履歴（{len(filtered_history)}件）")

    for record in filtered_history:
        with st.expander(
            f"**{record['name']}** ({record['code']}) - {record['sell_date']} - ¥{record['realized_profit']:+,.0f}",
            expanded=False
        ):
            col1, col2 = st.columns(2)

            shares = record.get('shares', 100)

            with col1:
                st.write("**購入情報**")
                st.write(f"購入日: {record['purchase_date']}")
                st.write(f"購入価格: ¥{record['purchase_price']:,.0f}/株")
                st.write(f"購入数量: {shares:,}株")
                st.write(f"投資額: ¥{record['purchase_price'] * shares:,.0f}")
                st.write(f"購入理由: {record['purchase_reason']}")

            with col2:
                st.write("**売却情報**")
                st.write(f"売却日: {record['sell_date']}")
                st.write(f"売却価格: ¥{record['sell_price']:,.0f}/株")
                st.write(f"売却額: ¥{record['sell_price'] * shares:,.0f}")
                st.write(f"売却理由: {record['sell_reason']}")

            st.divider()

            col3, col4, col5 = st.columns(3)
            with col3:
                st.metric("実現損益", f"¥{record['realized_profit']:,.0f}", f"{record['realized_profit_rate']:+.2f}%")
            with col4:
                st.metric("税金", f"¥{record['tax_amount']:,.0f}")
            with col5:
                st.metric("税引き後", f"¥{record['after_tax_profit']:,.0f}")

            st.caption(f"保有日数: {record['holding_days']}日")


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
    # 編集フォーム表示中
    if "edit_hypothesis_id" in st.session_state:
        render_edit_form(st.session_state.edit_hypothesis_id)
    # 売却フォーム表示中
    elif "sell_hypothesis_id" in st.session_state:
        render_sell_form(st.session_state.sell_hypothesis_id)
    # 損益サマリー表示
    elif st.session_state.get("current_view") == "profit_summary":
        render_profit_summary()
    # 売買履歴表示
    elif st.session_state.get("current_view") == "trading_history":
        render_trading_history()
    # 仮説詳細表示
    elif "selected_hypothesis" in st.session_state and st.session_state.selected_hypothesis:
        render_hypothesis_detail(st.session_state.selected_hypothesis)
    # 仮説一覧表示（デフォルト）
    else:
        render_hypothesis_list()


if __name__ == "__main__":
    main()
