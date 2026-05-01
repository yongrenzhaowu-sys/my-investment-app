"""投資判断支援アプリ（Streamlit）"""
import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import uuid

# 開発時のモジュール強制リロード（修正を即座に反映）
import sys
import importlib
if 'src.profit_calculator' in sys.modules:
    importlib.reload(sys.modules['src.profit_calculator'])
if 'src.trading_history' in sys.modules:
    importlib.reload(sys.modules['src.trading_history'])
if 'src.asset_calculator' in sys.modules:
    importlib.reload(sys.modules['src.asset_calculator'])

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
from src.settings import (
    load_settings,
    save_settings,
    get_initial_capital,
    get_additional_capital,
    get_additional_investments,
    add_additional_investment,
    remove_additional_investment
)
from src.metrics import (
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_win_rate,
    calculate_avg_holding_days,
    calculate_total_return
)
from src.asset_calculator import (
    calculate_asset_change,
    get_asset_history
)
from src.sector_returns import (
    calculate_sector_returns_from_indices,
    calculate_topix_return,
    calculate_relative_returns
)
import plotly.express as px

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
                # ログイン時に初期資金を強制的にクリア（次のmain()で再読み込みされる）
                if "initial_capital" in st.session_state:
                    del st.session_state.initial_capital
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
        ["📋 仮説登録", "📊 損益サマリー", "📜 売買履歴", "📈 バリュエーション分析", "💰 資産推移分析", "🔄 セクターローテーション", "💪 セクター強弱判定"],
        label_visibility="collapsed"
    )

    # メニューに応じた画面を表示
    if menu == "📊 損益サマリー":
        st.session_state.current_view = "profit_summary"
    elif menu == "📜 売買履歴":
        st.session_state.current_view = "trading_history"
    elif menu == "📈 バリュエーション分析":
        st.session_state.current_view = "valuation_analysis"
    elif menu == "💰 資産推移分析":
        st.session_state.current_view = "asset_tracking"
    elif menu == "🔄 セクターローテーション":
        st.session_state.current_view = "sector_rotation"
    elif menu == "💪 セクター強弱判定":
        st.session_state.current_view = "sector_strength"
    else:
        st.session_state.current_view = "main"

    st.sidebar.divider()
    st.sidebar.title("📋 仮説登録")

    with st.sidebar.form("hypothesis_form"):
        code = st.text_input("銘柄コード（5桁）", placeholder="72030")
        purchase_date = st.date_input("購入日", value=datetime.now())
        purchase_price = st.number_input("購入価格（円/株）", min_value=1, value=1000)
        shares = st.number_input("購入数量（株）", min_value=1, value=100, step=100)
        is_nisa = st.checkbox("NISA口座", value=False, help="NISA口座の場合、売却時の税金が0%になります")
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
                        "is_nisa": is_nisa,
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
        # セッション状態を完全にクリア（次回ログイン時に設定を再読み込み）
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def render_hypothesis_list():
    """仮説一覧を表示"""
    hypotheses = load_hypotheses()

    # 銘柄コード順にソート
    hypotheses = sorted(hypotheses, key=lambda x: x['code'])

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

        # 保有株数
        total_shares = hypo.get("shares", 100)

        sell_date = st.date_input("売却日", value=datetime.now())
        sell_price = st.number_input("売却価格（円）", min_value=1, value=int(hypo["purchase_price"]))
        sell_shares = st.number_input(
            "売却数量（株）",
            min_value=1,
            max_value=total_shares,
            value=total_shares,
            step=100,
            help=f"保有株数: {total_shares:,}株"
        )
        sell_reason = st.text_area(
            "売却理由",
            placeholder="例: 目標価格到達、損切り、資金需要、KPI未達成など..."
        )

        st.divider()

        # NISA口座フラグを取得
        is_nisa = hypo.get("is_nisa", False)

        # 予想損益を表示（売却数量を考慮）
        expected_profit_per_share = sell_price - hypo["purchase_price"]
        expected_profit = expected_profit_per_share * sell_shares
        expected_profit_rate = (expected_profit_per_share / hypo["purchase_price"]) * 100 if hypo["purchase_price"] > 0 else 0

        # 税金計算（NISA口座の場合は0%）
        if is_nisa:
            expected_tax = 0.0
            st.success("✅ NISA口座（税金0%）")
        else:
            expected_tax = max(0, expected_profit * 0.20315)
            st.info("課税口座（税率20.315%）")

        expected_after_tax = expected_profit - expected_tax

        # 残株数を表示
        remaining_shares = total_shares - sell_shares
        if remaining_shares > 0:
            st.info(f"**売却後の残株数**: {remaining_shares:,}株（保有継続）")
        else:
            st.warning(f"**全株売却**: 仮説一覧から削除されます")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("実現損益", f"¥{expected_profit:,.0f}", f"{expected_profit_rate:+.2f}%")
        with col2:
            st.metric("税引き後利益", f"¥{expected_after_tax:,.0f}")

        if is_nisa:
            st.caption(f"税金: ¥0（NISA口座）| 1株あたり損益: ¥{expected_profit_per_share:,.0f}")
        else:
            st.caption(f"税金: ¥{expected_tax:,.0f} (20.315%) | 1株あたり損益: ¥{expected_profit_per_share:,.0f}")

        submitted = st.form_submit_button("✅ 売却を確定", type="primary", width="stretch")

        if submitted:
            if not sell_reason:
                st.error("売却理由を入力してください")
            elif sell_date < datetime.strptime(hypo["purchase_date"], "%Y-%m-%d").date():
                st.error("売却日は購入日以降にしてください")
            else:
                try:
                    # 売却記録を追加（売却数量を指定）
                    record = add_sell_record(
                        hypo,
                        sell_date.strftime("%Y-%m-%d"),
                        sell_price,
                        sell_reason,
                        sell_shares=sell_shares
                    )

                    # 残株数を計算
                    remaining_shares = total_shares - sell_shares

                    if remaining_shares > 0:
                        # 部分売却: 仮説の株数を更新
                        for h in hypotheses:
                            if h["id"] == hypothesis_id:
                                h["shares"] = remaining_shares
                                break
                        save_hypotheses(hypotheses)

                        st.success(f"✅ {hypo['name']} を{sell_shares:,}株売却しました（残{remaining_shares:,}株）")
                    else:
                        # 全株売却: 仮説から削除
                        hypotheses = [h for h in hypotheses if h["id"] != hypothesis_id]
                        save_hypotheses(hypotheses)

                        st.success(f"✅ {hypo['name']} を全株売却しました")

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

    # 投資成績サマリー
    st.subheader("📊 投資成績サマリー")

    with st.expander("⚙️ 初期資金設定"):
        # 現在の初期資金を表示
        st.info(f"**現在の初期資金**: ¥{st.session_state.initial_capital:,}")

        # Streamlit Cloudの場合の注意事項
        if use_gsheets():
            st.caption("💡 **Streamlit Cloudで初期資金を変更する場合**：Settings → Secrets から `initial_capital` を更新してください")

        new_capital = st.number_input(
            "新しい初期資金（円）",
            min_value=0,
            value=int(st.session_state.initial_capital),
            step=100_000,
            key="new_initial_capital_input",
            help="変更後は「更新」ボタンを押してください"
        )

        # 値が変更されたかチェック
        is_changed = new_capital != st.session_state.initial_capital

        if st.button(
            "更新" if is_changed else "更新（変更なし）",
            key="update_initial_capital",
            type="primary" if is_changed else "secondary",
            disabled=not is_changed
        ):
            # セッション状態を更新
            st.session_state.initial_capital = new_capital

            # settings.jsonに保存
            settings = load_settings()
            settings["initial_capital"] = new_capital
            if save_settings(settings):
                st.success(f"✅ 初期資金を ¥{new_capital:,} に更新しました（永続化済み）")
                # セッション状態を明示的に更新
                st.session_state.initial_capital = new_capital
            else:
                st.warning("⚠️ 初期資金を更新しました（永続化に失敗）")
            st.rerun()

    # 追加投資履歴管理
    with st.expander("💰 追加投資履歴"):
        investments = st.session_state.additional_investments

        # 合計表示
        total = sum(inv["amount"] for inv in investments)
        st.info(f"**追加投資額の合計**: ¥{total:,}")
        st.caption("楽天銀行からスイープされた追加資金や、後から入金した資金をここで管理します")

        # 履歴一覧
        if investments:
            st.subheader("📋 履歴")
            for i, inv in enumerate(investments):
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.write(f"日付: {inv['date']}")
                with col2:
                    st.write(f"金額: ¥{inv['amount']:,}")
                with col3:
                    if st.button("🗑️", key=f"delete_inv_{i}"):
                        if remove_additional_investment(i):
                            st.session_state.additional_investments = get_additional_investments()
                            st.success("削除しました")
                            st.rerun()
                        else:
                            st.error("削除に失敗しました")

        st.divider()

        # 新規追加フォーム
        st.subheader("➕ 追加投資を記録")
        with st.form("add_investment_form"):
            inv_date = st.date_input("追加投資日", value=datetime.now())
            inv_amount = st.number_input("金額（円）", min_value=0, step=100_000)

            submitted = st.form_submit_button("追加", type="primary")
            if submitted:
                if inv_amount > 0:
                    if add_additional_investment(
                        inv_date.strftime("%Y-%m-%d"),
                        inv_amount
                    ):
                        st.session_state.additional_investments = get_additional_investments()
                        st.success(f"✅ ¥{inv_amount:,} を記録しました")
                        st.rerun()
                    else:
                        st.error("追加に失敗しました")
                else:
                    st.error("金額は1円以上を入力してください")

    available = calculate_available_capital(
        hypotheses,
        st.session_state.initial_capital,
        st.session_state.additional_investments
    )

    # 総資産と損益を計算
    total_assets = available['current_investment'] + available['available_capital']
    profit_loss = total_assets - available['total_capital']
    profit_loss_rate = (profit_loss / available['total_capital'] * 100) if available['total_capital'] > 0 else 0

    # メイン表示：総資産と損益
    col_main1, col_main2 = st.columns(2)
    with col_main1:
        st.metric(
            "総資産",
            f"¥{total_assets:,.0f}",
            delta=f"¥{profit_loss:,.0f}",
            delta_color="normal" if profit_loss >= 0 else "inverse"
        )
    with col_main2:
        st.metric(
            "損益率",
            f"{profit_loss_rate:+.2f}%",
            delta=f"¥{profit_loss:,.0f}",
            delta_color="normal" if profit_loss >= 0 else "inverse"
        )

    st.divider()

    # 内訳表示
    st.write("**内訳：**")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("保有証券", f"¥{available['current_investment']:,.0f}", help=f"{len(hypotheses)}銘柄保有中")
    with col2:
        st.metric("現金", f"¥{available['available_capital']:,.0f}", help="投資可能額")

    col3, col4, col5 = st.columns(3)
    with col3:
        st.metric("初期資金", f"¥{available['initial_capital']:,.0f}", help="最初に投入した資金")
    with col4:
        st.metric("追加投資額", f"¥{available['additional_capital']:,.0f}", help="楽天銀行からスイープされた追加資金")
    with col5:
        st.metric("合計投資額", f"¥{available['total_capital']:,.0f}", help="初期資金 + 追加投資額")

    st.divider()

    # 投資指標
    st.subheader("📈 投資指標")

    # 売買履歴を取得
    trading_history = load_trading_history()

    # 指標を計算
    if trading_history:
        # リターンのリストを作成（売買履歴から）
        returns = [record.get("realized_profit_rate", 0) for record in trading_history]

        # シャープレシオ
        sharpe = calculate_sharpe_ratio(returns)

        # 勝率
        win_rate = calculate_win_rate(trading_history)

        # 平均保有日数
        avg_holding_days = calculate_avg_holding_days(trading_history)
    else:
        sharpe = 0.0
        win_rate = 0.0
        avg_holding_days = 0.0

    # 累計リターン（合計投資額に対するリターン）
    total_return = calculate_total_return(
        available['total_capital'],  # 初期資金 + 追加投資額
        available['current_investment'],
        unrealized['total_unrealized'],
        available['cumulative_sales']
    )

    # 最大ドローダウン（ポートフォリオ価値の時系列が必要）
    # 簡易版: 含み損益が最も悪い銘柄のドローダウンを使用
    if unrealized['details']:
        max_dd = max(
            abs(min(detail['unrealized_profit_rate'] for detail in unrealized['details'])),
            0
        )
    else:
        max_dd = 0.0

    # 表示
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("累計リターン", f"{total_return:+.2f}%", help="初期資金からの総合リターン")

    with col2:
        st.metric("シャープレシオ", f"{sharpe:.2f}", help="リスク調整後リターン（高いほど良い）")

    with col3:
        st.metric("勝率", f"{win_rate:.1f}%", help="利益が出た取引の割合")

    with col4:
        st.metric("平均保有日数", f"{avg_holding_days:.0f}日", help="売却した銘柄の平均保有期間")

    with col5:
        st.metric("最大DD", f"{max_dd:.2f}%", help="最大下落率（低いほど良い）")

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


def render_valuation_analysis():
    """バリュエーション分析を表示"""
    from src.valuation_analysis_api import analyze_stock

    st.title("📊 バリュエーション分析")
    st.markdown("保有銘柄に対して4つのバリュエーション分析を実行します。")

    # APIクライアントチェック
    if not hasattr(st.session_state, 'client') or st.session_state.client is None:
        st.error("J-Quants APIクライアントが初期化されていません。")
        return

    # 仮説データ読み込み
    hypotheses = load_hypotheses()

    # 銘柄コード順にソート
    hypotheses = sorted(hypotheses, key=lambda h: h.get('code', ''))

    if len(hypotheses) == 0:
        st.info("保有銘柄がありません。「📋 仮説登録」から銘柄を登録してください。")
        return

    st.info(f"保有銘柄数: {len(hypotheses)}銘柄")
    st.warning("⚠️ J-Quants APIからデータを取得します。銘柄数が多いと時間がかかる場合があります。")

    # 分析実行ボタン
    if st.button("🔍 全銘柄を分析", type="primary", use_container_width=True):
        with st.spinner("分析中..."):
            results = []

            # プログレスバー
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, hypo in enumerate(hypotheses):
                code = hypo.get('code')

                if code:
                    status_text.text(f"分析中: {code} ({idx + 1}/{len(hypotheses)})")

                    try:
                        # 分析実行（APIクライアントを渡す）
                        result = analyze_stock(st.session_state.client, code)
                        results.append(result)
                    except Exception as e:
                        st.error(f"銘柄 {code} の分析エラー: {e}")
                        # エラーでも結果に追加（エラー情報付き）
                        results.append({
                            'code': code,
                            'overall_signal': None,
                            'peg_ratio': {'error': str(e)},
                            'ma_divergence': {'error': str(e)},
                            'ev_ebitda': {'error': str(e)},
                            'dcf_proxy': {'error': str(e)}
                        })

                # プログレス更新
                progress = (idx + 1) / len(hypotheses)
                progress_bar.progress(progress)

            progress_bar.empty()
            status_text.empty()

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

        # 銘柄コード順にソート
        filtered_results = sorted(filtered_results, key=lambda r: r.get('code', ''))

        # 結果表示
        for result in filtered_results:
            _render_analysis_result(result)

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


def _render_analysis_result(result):
    """分析結果を表示（内部関数）"""
    def _render_signal_badge(signal):
        """シグナルバッジを表示"""
        if signal == 'BUY':
            return "🟢 買い"
        elif signal == 'SELL':
            return "🔴 売り"
        elif signal == 'HOLD':
            return "🟡 保持"
        else:
            return "⚪ -"

    st.markdown("---")

    # ヘッダー
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        company_name = result.get('company_name', '')
        if company_name:
            st.subheader(f"{company_name} ({result['code']})")
        else:
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
            st.success(f"総合判定: {_render_signal_badge(overall_signal)}")
        elif overall_signal == 'SELL':
            st.error(f"総合判定: {_render_signal_badge(overall_signal)}")
        elif overall_signal == 'HOLD':
            st.warning(f"総合判定: {_render_signal_badge(overall_signal)}")
        else:
            st.info(f"総合判定: {_render_signal_badge(overall_signal)}")

    # 4つの分析結果を表示（モバイル対応：2カラム×2行）

    # 1行目：PEG Ratio と 移動平均
    col1, col2 = st.columns(2)

    with col1:
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
            # デバッグ情報
            with st.expander("🔍 詳細"):
                eps_type = peg.get('eps_type', '実績')
                st.write(f"**現在株価**: ¥{result.get('current_price', 0):.2f}")
                st.write(f"**EPS（{eps_type}）**: {peg.get('eps', 'N/A'):.2f} 円")
                st.write(f"**NP（最新）**: {peg.get('np_latest', 0):,.0f} 百万円")
                st.write(f"**決算期**: {peg.get('fiscal_period', 'N/A')}")
                st.write(f"**開示日**: {peg.get('disc_date', 'N/A')}")
                st.write(f"**計算式**: PER = {result.get('current_price', 0):.2f} ÷ {peg.get('eps', 0):.2f} = {peg.get('per', 0):.2f}")
            st.markdown(_render_signal_badge(peg.get('signal')))

    with col2:
        st.markdown("**移動平均**")
        ma = result['ma_divergence']

        if ma.get('error'):
            st.warning(f"⚠️ {ma['error']}")
        else:
            st.metric("25日MA乖離", f"{ma.get('divergence_25', 0):.1f}%")
            st.caption(f"現在: ¥{ma.get('current_price', 0):.0f}")
            st.caption(f"25日MA: ¥{ma.get('ma_25', 0):.0f}")
            st.caption(f"75日MA: ¥{ma.get('ma_75', 0):.0f}")
            st.markdown(_render_signal_badge(ma.get('signal')))

    # 2行目：EV/EBITDA と DCF Proxy
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("**EV/EBITDA**")
        ev = result['ev_ebitda']

        if ev.get('error'):
            st.warning(f"⚠️ {ev['error']}")
        else:
            st.metric("EV/EBITDA", f"{ev.get('ev_ebitda', 0):.1f}")
            # EVとEBITDAは百万円単位なので、億円に変換するには /100
            st.caption(f"EV: {ev.get('ev', 0)/100:.0f}億円")
            st.caption(f"EBITDA: {ev.get('ebitda', 0)/100:.0f}億円")
            # 営業利益×10との乖離
            if ev.get('op_divergence') is not None:
                op_div = ev.get('op_divergence', 0)
                st.caption(f"📊 OP×10乖離: {op_div:+.1f}%")
                st.caption(f"   時総: {ev.get('market_cap', 0)/100:.0f}億 vs OP×10: {ev.get('op_x10', 0)/100:.0f}億")
            if ev.get('theoretical_price') is not None:
                st.caption(f"理論株価: ¥{ev.get('theoretical_price', 0):.0f}")

            # デバッグ情報
            with st.expander("🔍 詳細"):
                st.write(f"**時価総額**: {ev.get('market_cap', 0)/100:.0f}億円")
                st.write(f"**営業利益（OP）**: {ev.get('ebitda', 0)/100:.0f}億円")
                st.write(f"**純負債**: {ev.get('net_debt', 0)/100:.0f}億円")
                st.write(f"**EV**: {ev.get('ev', 0)/100:.0f}億円")
                st.write(f"**発行済株式数**: {ev.get('shares_outstanding', 0):,.0f}株")
                st.write(f"**NP（円）**: {ev.get('np', 0):,.0f}")
                st.write(f"**NP（億円）**: {ev.get('np', 0)/1e8:.2f}")
                st.write(f"**EPS（円）**: {ev.get('eps', 0):.2f}")

            st.markdown(_render_signal_badge(ev.get('signal')))

    with col4:
        st.markdown("**DCF Proxy**")
        dcf = result['dcf_proxy']

        if dcf.get('error'):
            st.warning(f"⚠️ {dcf['error']}")
        else:
            ratio = dcf.get('price_to_theoretical', 0)
            st.metric("株価/理論株価", f"{ratio:.2f}")
            st.caption(f"現在: ¥{dcf.get('current_price', 0):.0f}")
            st.caption(f"理論: ¥{dcf.get('theoretical_price', 0):.0f}")
            st.markdown(_render_signal_badge(dcf.get('signal')))


def render_asset_tracking():
    """資産推移分析を表示"""
    st.title("💰 資産推移分析")
    st.markdown("任意の基準日からの資産額の増減を分析します。")

    # データ読み込み
    hypotheses = load_hypotheses()
    trading_history = load_trading_history()
    initial_capital = st.session_state.get("initial_capital", 1_000_000)
    additional_investments = st.session_state.get("additional_investments", [])

    # 期間選択
    st.subheader("📅 期間を選択")
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "開始日",
            value=datetime(2026, 3, 13),
            help="分析開始日を選択します"
        )

    with col2:
        end_date = st.date_input(
            "終了日",
            value=datetime.now(),
            help="分析終了日を選択します"
        )

    # バリデーション
    if start_date >= end_date:
        st.error("⚠️ 開始日は終了日より前である必要があります")
        return

    # 計算ボタン
    col3, _ = st.columns([1, 3])
    with col3:
        calculate_button = st.button("🔍 計算開始", type="primary", use_container_width=True)

    # 計算実行
    if calculate_button or "asset_change_data" in st.session_state:
        with st.spinner("資産額を計算中..."):
            try:
                # 資産増減計算
                change = calculate_asset_change(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    hypotheses=hypotheses,
                    trading_history=trading_history,
                    initial_capital=initial_capital,
                    additional_investments=additional_investments,
                    end_date=end_date.strftime("%Y-%m-%d")
                )

                # セッション状態に保存
                st.session_state.asset_change_data = change

            except Exception as e:
                st.error(f"計算エラー: {e}")
                return

    # 結果表示
    if "asset_change_data" in st.session_state:
        change = st.session_state.asset_change_data

        st.markdown("---")
        st.subheader("📊 資産増減サマリー")

        # メトリクス表示
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "開始日資産額",
                f"¥{change['start_asset']:,.0f}",
                help=f"開始日: {change['start_date']}"
            )
            st.caption(f"時価総額: ¥{change['start_market_value']:,.0f}")
            st.caption(f"現金: ¥{change['start_cash']:,.0f}")

        with col2:
            st.metric(
                "終了日資産額",
                f"¥{change['end_asset']:,.0f}",
                help=f"終了日: {change['end_date']}"
            )
            st.caption(f"時価総額: ¥{change['end_market_value']:,.0f}")
            st.caption(f"現金: ¥{change['end_cash']:,.0f}")

        with col3:
            # 増減額（色分け）
            change_amount = change['change_amount']
            change_rate = change['change_rate']

            if change_amount >= 0:
                st.success(f"**+¥{change_amount:,.0f}**")
                st.success(f"**+{change_rate:.2f}%**")
            else:
                st.error(f"**¥{change_amount:,.0f}**")
                st.error(f"**{change_rate:.2f}%**")

        # 保有銘柄詳細（開始日）
        st.markdown("---")
        st.subheader(f"📋 開始日時点の保有銘柄（{change['start_date']}）")

        if change['start_holdings']:
            start_df = pd.DataFrame(change['start_holdings'])
            start_df['価格'] = start_df['price'].apply(lambda x: f"¥{x:,.0f}")
            start_df['株数'] = start_df['shares'].apply(lambda x: f"{x:,}株")
            start_df['評価額'] = start_df['value'].apply(lambda x: f"¥{x:,.0f}")

            st.dataframe(
                start_df[['code', 'name', '価格', '株数', '評価額']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("開始日時点では銘柄を保有していませんでした。")

        # 保有銘柄詳細（終了日）
        st.markdown("---")
        st.subheader(f"📋 終了日時点の保有銘柄（{change['end_date']}）")

        if change['end_holdings']:
            current_df = pd.DataFrame(change['end_holdings'])
            current_df['価格'] = current_df['price'].apply(lambda x: f"¥{x:,.0f}")
            current_df['株数'] = current_df['shares'].apply(lambda x: f"{x:,}株")
            current_df['評価額'] = current_df['value'].apply(lambda x: f"¥{x:,.0f}")

            st.dataframe(
                current_df[['code', 'name', '価格', '株数', '評価額']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("終了日時点では銘柄を保有していません。")

        # 資産推移グラフ（Phase 2）
        st.markdown("---")
        st.subheader("📈 資産推移グラフ")

        with st.spinner("グラフデータを取得中..."):
            try:
                history = get_asset_history(
                    start_date=change['start_date'],
                    end_date=change['end_date'],
                    hypotheses=hypotheses,
                    trading_history=trading_history,
                    initial_capital=initial_capital,
                    additional_investments=additional_investments
                )

                # Plotlyグラフ作成
                fig = px.line(
                    history,
                    x="date",
                    y="total_asset",
                    title="資産推移",
                    labels={"date": "日付", "total_asset": "総資産額（円）"}
                )

                # Y軸フォーマット（カンマ区切り）
                fig.update_yaxes(tickformat=",")

                # グラフ表示
                st.plotly_chart(fig, use_container_width=True)

                # データテーブル（展開可能）
                with st.expander("📊 詳細データを表示"):
                    history_display = history.copy()
                    history_display['total_asset'] = history_display['total_asset'].apply(lambda x: f"¥{x:,.0f}")
                    history_display['market_value'] = history_display['market_value'].apply(lambda x: f"¥{x:,.0f}")
                    history_display['cash'] = history_display['cash'].apply(lambda x: f"¥{x:,.0f}")

                    st.dataframe(
                        history_display,
                        use_container_width=True,
                        hide_index=True
                    )

            except Exception as e:
                st.error(f"グラフ作成エラー: {e}")

    # 使い方ガイド
    with st.expander("📖 使い方ガイド"):
        st.markdown("""
        ### 資産推移分析の使い方

        #### 1. 期間を選択
        - **開始日**: 分析開始日を選択（デフォルト: 2026-03-13）
        - **終了日**: 分析終了日を選択（デフォルト: 今日）
        - ⚠️ 開始日 < 終了日 である必要があります

        #### 2. 計算開始
        - 「🔍 計算開始」ボタンをクリックすると、以下が計算されます:
          - **開始日時点の資産額**: 開始日の時価総額 + 現金残高
          - **終了日時点の資産額**: 終了日の時価総額 + 現金残高
          - **増減額**: 終了日資産額 - 開始日資産額
          - **増減率**: (終了日資産額 / 開始日資産額 - 1) × 100%

        #### 3. 資産推移グラフ
        - 開始日から終了日までの日次資産推移をグラフで表示
        - 営業日のみデータが表示されます

        ### ユースケース
        - 📊 **過去1ヶ月のリターン**: 開始日=1ヶ月前、終了日=今日
        - 📊 **特定月のパフォーマンス**: 開始日=2026-03-01、終了日=2026-03-31
        - 📊 **運用開始からのリターン**: 開始日=運用開始日、終了日=今日
        - 📊 **四半期ごとの比較**: 開始日=Q1開始、終了日=Q1終了

        ### 注意事項
        - 株価データはyfinance APIから取得します
        - 取得失敗した場合は0円として扱われます
        - 開始日・終了日が休日の場合、直近の営業日の株価を使用します
        """)


def render_sector_strength():
    """セクター強弱判定画面を表示（東証33業種指数）"""
    st.title("💪 セクター強弱判定（東証33業種）")
    st.markdown("東証33業種指数をTOPIX対比で強弱判定します。3つの指標（期間リターン、移動平均乖離、RSI）を統合してスコアリングします。")

    # APIクライアントチェック
    if not hasattr(st.session_state, 'client') or st.session_state.client is None:
        st.error("J-Quants APIクライアントが初期化されていません。")
        return

    # 期間選択
    st.subheader("📅 期間を選択")
    col1, col2 = st.columns([1, 3])

    with col1:
        preset = st.selectbox(
            "プリセット",
            ["1ヶ月", "3ヶ月", "6ヶ月", "1年", "カスタム"]
        )

    if preset == "カスタム":
        col2_1, col2_2 = st.columns(2)
        with col2_1:
            start_date = st.date_input("開始日", value=datetime.now() - timedelta(days=30))
        with col2_2:
            end_date = st.date_input("終了日", value=datetime.now())
    else:
        # プリセットから期間を計算
        end_date = datetime.now()
        if preset == "1ヶ月":
            start_date = end_date - timedelta(days=30)
        elif preset == "3ヶ月":
            start_date = end_date - timedelta(days=90)
        elif preset == "6ヶ月":
            start_date = end_date - timedelta(days=180)
        else:  # 1年
            start_date = end_date - timedelta(days=365)

    # 注意事項
    st.info("💡 東証33業種指数を使用します（J-Quants API Standard プラン以上）")

    # 分析ボタン
    if st.button("🔍 分析開始", type="primary", use_container_width=True):
        with st.spinner("東証33業種指数データを分析中..."):
            try:
                from src.sector_strength import analyze_all_sectors

                # デバッグ用エクスパンダー
                debug_expander = st.expander("🔍 デバッグ情報", expanded=True)

                with debug_expander:
                    st.write("### API接続テスト")
                    st.write(f"開始日: {start_date.strftime('%Y-%m-%d')}")
                    st.write(f"終了日: {end_date.strftime('%Y-%m-%d')}")

                    # 簡単なAPIテスト（TOPIX取得）
                    try:
                        st.write("**TOPIXデータ取得テスト...**")
                        topix_test = st.session_state.client.get_indices_topix(
                            start_date.strftime("%Y-%m-%d"),
                            end_date.strftime("%Y-%m-%d")
                        )
                        if topix_test:
                            st.success(f"✅ TOPIX取得成功（{len(topix_test)}件）")
                            st.json(topix_test[0] if topix_test else {})
                        else:
                            st.error("❌ TOPIXデータが空です")
                    except Exception as te:
                        st.error(f"❌ TOPIX取得エラー: {te}")

                    # 33業種指数取得テスト（最初の1業種のみ）
                    try:
                        st.write("**33業種指数取得テスト（水産・農林業=0040）...**")
                        from src.sector_33_data import get_all_sector_codes
                        test_code = get_all_sector_codes()[0]

                        # 直接API呼び出し
                        url = f"https://api.jquants.com/v2/indices/bars/daily"
                        params = {
                            "code": test_code,
                            "from": start_date.strftime("%Y%m%d"),
                            "to": end_date.strftime("%Y%m%d")
                        }
                        st.write(f"URL: {url}")
                        st.write(f"パラメータ: {params}")

                        import requests
                        response = st.session_state.client.session.get(url, params=params, timeout=30)
                        st.write(f"ステータスコード: {response.status_code}")

                        if response.status_code == 200:
                            data = response.json()
                            st.write(f"レスポンスキー: {list(data.keys())}")

                            if "daily_bars" in data and data["daily_bars"]:
                                st.success(f"✅ 33業種指数取得成功（{len(data['daily_bars'])}件）")
                                st.json(data["daily_bars"][0])
                            elif "data" in data and data["data"]:
                                st.success(f"✅ 33業種指数取得成功（{len(data['data'])}件）")
                                st.json(data["data"][0])
                            else:
                                st.error(f"❌ データキーが見つかりません: {list(data.keys())}")
                                st.json(data)
                        elif response.status_code == 403:
                            st.error("❌ 403 Forbidden - プラン制限またはAPI認証エラー")
                            st.write("レスポンス:")
                            st.code(response.text)
                        else:
                            st.error(f"❌ HTTPエラー: {response.status_code}")
                            st.code(response.text)

                    except Exception as se:
                        st.error(f"❌ 33業種指数取得エラー: {se}")
                        import traceback
                        st.code(traceback.format_exc())

                # 全業種を一括分析
                st.info("全33業種を分析中...")

                # デバッグ用のステータス表示
                status_container = st.empty()

                # ステップ1: 期間リターン計算
                status_container.info("📊 [1/3] 期間リターン計算中...")
                from src.sector_strength import calculate_period_return
                try:
                    sector_returns, topix_return = calculate_period_return(
                        st.session_state.client,
                        start_date.strftime("%Y-%m-%d"),
                        end_date.strftime("%Y-%m-%d")
                    )
                    st.success(f"✅ 期間リターン計算完了: {len(sector_returns)}業種、TOPIX={topix_return:.2f}%")
                except Exception as e:
                    st.error(f"❌ 期間リターン計算エラー: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    raise

                # ステップ2: MA乖離計算
                status_container.info("📈 [2/3] 移動平均乖離計算中...")
                from src.sector_strength import calculate_ma_divergence
                from datetime import timedelta
                try:
                    # 期間延長の計算（75日MA用に150日分遡る）
                    extended_start = (start_date - timedelta(days=150)).strftime("%Y-%m-%d")
                    st.caption(f"データ取得期間: {extended_start} 〜 {end_date.strftime('%Y-%m-%d')}")

                    sector_ma_divs, topix_ma_div = calculate_ma_divergence(
                        st.session_state.client,
                        start_date.strftime("%Y-%m-%d"),
                        end_date.strftime("%Y-%m-%d")
                    )
                    st.success(f"✅ MA乖離計算完了: {len(sector_ma_divs)}業種")

                    # データ不足の業種を確認
                    if len(sector_ma_divs) < len(sector_returns):
                        missing_count = len(sector_returns) - len(sector_ma_divs)
                        st.warning(f"⚠️ {missing_count}業種でMA乖離データ不足（移動平均計算に必要なデータ件数が不足）")
                except Exception as e:
                    st.error(f"❌ MA乖離計算エラー: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    raise

                # ステップ3: RSI計算
                status_container.info("📉 [3/3] RSI計算中...")
                from src.sector_strength import calculate_rsi
                try:
                    sector_rsi, topix_rsi = calculate_rsi(
                        st.session_state.client,
                        start_date.strftime("%Y-%m-%d"),
                        end_date.strftime("%Y-%m-%d")
                    )
                    st.success(f"✅ RSI計算完了: {len(sector_rsi)}業種、TOPIX RSI={topix_rsi:.1f}")
                except Exception as e:
                    st.error(f"❌ RSI計算エラー: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    raise

                # ステップ4: 統合判定
                status_container.info("🎯 統合判定中...")
                results = analyze_all_sectors(
                    st.session_state.client,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")
                )

                status_container.empty()

                # セッション状態に保存
                st.session_state.sector_strength_data = {
                    "results": results,
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d")
                }

                if results:
                    st.success(f"✅ 分析完了！（{len(results)}業種）")
                else:
                    st.warning("⚠️ 分析結果が空です")

            except Exception as e:
                st.error(f"❌ 分析エラー: {e}")

                # 詳細なエラー情報を表示
                import traceback
                with st.expander("🔍 詳細なエラー情報（デバッグ用）"):
                    st.code(traceback.format_exc())

    # 結果表示
    if "sector_strength_data" in st.session_state:
        data = st.session_state.sector_strength_data
        results = data["results"]

        st.markdown("---")
        st.subheader("📊 分析結果")

        # 結果が空の場合
        if not results:
            st.warning("⚠️ 分析結果が取得できませんでした。")
            st.info("**考えられる原因:**")
            st.write("- J-Quants APIのデータ取得に失敗した")
            st.write("- Standard プラン以上が必要です")
            st.write("- ネットワークエラー")
            return

        # サマリー
        col1, col2, col3 = st.columns(3)
        strong_count = sum(1 for r in results if r["strength"] == "強い")
        normal_count = sum(1 for r in results if r["strength"] == "普通")
        weak_count = sum(1 for r in results if r["strength"] == "弱い")

        col1.metric("🟢 強い", f"{strong_count}業種")
        col2.metric("🟡 普通", f"{normal_count}業種")
        col3.metric("🔴 弱い", f"{weak_count}業種")

        st.divider()

        # フィルタリングとソート
        col_filter1, col_filter2 = st.columns(2)

        with col_filter1:
            filter_option = st.selectbox(
                "フィルター",
                ["全て", "強いのみ", "普通のみ", "弱いのみ"]
            )

        with col_filter2:
            sort_option = st.selectbox(
                "並び順",
                ["スコア順", "期間リターン順", "MA乖離順", "RSI順"]
            )

        # フィルタリング
        filtered_results = results
        if filter_option == "強いのみ":
            filtered_results = [r for r in results if r["strength"] == "強い"]
        elif filter_option == "普通のみ":
            filtered_results = [r for r in results if r["strength"] == "普通"]
        elif filter_option == "弱いのみ":
            filtered_results = [r for r in results if r["strength"] == "弱い"]

        # ソート
        if sort_option == "期間リターン順":
            filtered_results = sorted(filtered_results, key=lambda x: x["period_return"], reverse=True)
        elif sort_option == "MA乖離順":
            filtered_results = sorted(filtered_results, key=lambda x: x["ma_div_25"], reverse=True)
        elif sort_option == "RSI順":
            filtered_results = sorted(filtered_results, key=lambda x: x["rsi"], reverse=True)
        # スコア順はデフォルトでソート済み

        st.divider()

        # 結果一覧（カード形式）
        st.subheader(f"📋 業種一覧（{len(filtered_results)}件）")

        for result in filtered_results:
            # 強弱に応じて色分け
            if result["strength"] == "強い":
                strength_emoji = "🟢"
                strength_color = "success"
            elif result["strength"] == "弱い":
                strength_emoji = "🔴"
                strength_color = "error"
            else:
                strength_emoji = "🟡"
                strength_color = "warning"

            with st.expander(
                f"{strength_emoji} **{result['sector_name']}** ({result['sector_code']}) - スコア: {result['score']}",
                expanded=False
            ):
                # 基本情報
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "期間リターン",
                        f"{result['period_return']:.2f}%",
                        delta=f"{result['topix_relative_return']:+.2f}% vs TOPIX"
                    )

                with col2:
                    st.metric(
                        "MA乖離（25日）",
                        f"{result['ma_div_25']:.2f}%",
                        delta=f"{result['topix_relative_ma_25']:+.2f}% vs TOPIX"
                    )

                with col3:
                    st.metric(
                        "RSI",
                        f"{result['rsi']:.1f}",
                        delta=f"{result['topix_relative_rsi']:+.1f} vs TOPIX"
                    )

                # 詳細情報
                st.divider()
                st.write("**判定内訳:**")

                col_detail1, col_detail2, col_detail3 = st.columns(3)

                with col_detail1:
                    st.write(f"期間リターン: {'✅ +1' if result['topix_relative_return'] > 0 else '❌ -1'}")

                with col_detail2:
                    st.write(f"MA乖離: {'✅ +1' if result['topix_relative_ma_25'] > 0 else '❌ -1'}")

                with col_detail3:
                    st.write(f"RSI: {'✅ +1' if result['topix_relative_rsi'] > 0 else '❌ -1'}")

        # データテーブル（展開可能）
        st.divider()
        with st.expander("📊 全データをテーブル表示"):
            if not filtered_results:
                st.info("データがありません。")
            else:
                df = pd.DataFrame(filtered_results)

                # 表示用にカラムを整形
                df_display = df[[
                    "sector_name",
                    "period_return",
                    "ma_div_25",
                    "rsi",
                    "topix_relative_return",
                    "score",
                    "strength"
                ]].copy()

                df_display.columns = [
                    "業種名",
                    "期間リターン(%)",
                    "MA乖離25日(%)",
                    "RSI",
                    "TOPIX対比リターン(%)",
                    "スコア",
                    "判定"
                ]

                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )

    # 使い方ガイド
    with st.expander("📖 使い方ガイド"):
        st.markdown("""
        ### セクター強弱判定の使い方

        #### 1. 期間を選択
        - **プリセット**: 1ヶ月、3ヶ月、6ヶ月、1年から選択
        - **カスタム**: 任意の開始日・終了日を指定

        #### 2. 分析開始
        - 「🔍 分析開始」ボタンをクリック
        - J-Quants APIから東証33業種指数データを取得し、3つの指標で分析

        #### 3. 判定指標の説明

        ##### 期間リターン
        - 選択期間の騰落率
        - TOPIX対比でプラスなら +1、マイナスなら -1

        ##### 移動平均乖離（25日MA）
        - 現在価格と25日移動平均線の乖離率
        - TOPIX対比でプラスなら +1、マイナスなら -1

        ##### RSI（相対力指数）
        - 14日RSI（0〜100）
        - TOPIX対比でプラスなら +1、マイナスなら -1

        #### 4. 総合判定
        - **スコア**: 3つの指標の合計（-3〜+3）
        - **強い**: スコア >= 2
        - **普通**: -1 <= スコア <= 1
        - **弱い**: スコア <= -2

        ### 東証33業種分類
        水産・農林業、鉱業、建設業、食料品、繊維製品、パルプ・紙、化学、医薬品、石油・石炭製品、ゴム製品、ガラス・土石製品、鉄鋼、非鉄金属、金属製品、機械、電気機器、輸送用機器、精密機器、その他製品、電気・ガス業、陸運業、海運業、空運業、倉庫・運輸関連業、情報・通信業、卸売業、小売業、銀行業、証券・商品先物取引業、保険業、その他金融業、不動産業、サービス業

        ### 活用方法
        - 📊 **セクターローテーション戦略**: 強いセクターに投資、弱いセクターを避ける
        - 📊 **ポートフォリオバランス**: 保有銘柄のセクター偏りを確認
        - 📊 **マーケット分析**: 相場環境で優位なセクターを特定

        ### データソース
        - 東証33業種指数（J-Quants API）
        - 東京証券取引所の公式業種分類
        - Standard プラン以上で利用可能
        """)


def render_sector_rotation():
    """セクターローテーション分析を表示（TOPIX-17業種指数ベース）"""
    st.title("🔄 セクターローテーション分析")
    st.markdown("TOPIX-17業種指数を使用して、TOPIX対比で各業種セクターの相対リターンを分析します。")

    # APIクライアントチェック
    if not hasattr(st.session_state, 'client') or st.session_state.client is None:
        st.error("J-Quants APIクライアントが初期化されていません。")
        return

    # 期間選択
    st.subheader("📅 期間を選択")
    col1, col2 = st.columns([1, 3])

    with col1:
        preset = st.selectbox(
            "プリセット",
            ["1ヶ月", "3ヶ月", "6ヶ月", "1年", "カスタム"]
        )

    if preset == "カスタム":
        col2_1, col2_2 = st.columns(2)
        with col2_1:
            start_date = st.date_input("開始日", value=datetime.now() - timedelta(days=30))
        with col2_2:
            end_date = st.date_input("終了日", value=datetime.now())
    else:
        # プリセットから期間を計算
        end_date = datetime.now()
        if preset == "1ヶ月":
            start_date = end_date - timedelta(days=30)
        elif preset == "3ヶ月":
            start_date = end_date - timedelta(days=90)
        elif preset == "6ヶ月":
            start_date = end_date - timedelta(days=180)
        else:  # 1年
            start_date = end_date - timedelta(days=365)

    # 注意事項
    st.info("💡 TOPIX-17業種指数を使用します（J-Quants APIから直接取得）")

    # 計算ボタン
    if st.button("🔍 分析開始", type="primary", use_container_width=True):
        with st.spinner("TOPIX-17業種指数データを取得中..."):
            try:
                # デバッグ用エクスパンダー
                debug_expander = st.expander("🔍 デバッグ情報", expanded=True)

                with debug_expander:
                    st.write("### API接続テスト")

                    # 直接APIを呼び出してデバッグ
                    import io
                    import sys
                    from contextlib import redirect_stdout

                    # 標準出力をキャプチャ
                    f = io.StringIO()
                    with redirect_stdout(f):
                        sector_data = st.session_state.client.get_topix_17_sectors(
                            start_date.strftime("%Y-%m-%d"),
                            end_date.strftime("%Y-%m-%d")
                        )

                    # キャプチャした出力を表示
                    output = f.getvalue()
                    if output:
                        st.code(output)

                    st.write(f"取得データ件数: {len(sector_data) if sector_data else 0}")
                    if sector_data:
                        st.write("サンプルデータ（最初の3件）:")
                        st.json(sector_data[:3])

                # ステップ 1: TOPIX-17業種指数取得
                st.info("ステップ 1/3: TOPIX-17業種指数を取得中...")
                sector_returns = calculate_sector_returns_from_indices(
                    st.session_state.client,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")
                )

                if not sector_returns:
                    st.error("❌ TOPIX-17業種指数の取得に失敗しました")
                    st.warning("J-Quants APIのプランを確認してください")
                    return

                st.success(f"✅ {len(sector_returns)}業種の指数データを取得しました")

                # ステップ 2: TOPIXリターン計算
                st.info("ステップ 2/3: TOPIXリターンを計算中...")
                topix_return = calculate_topix_return(
                    st.session_state.client,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")
                )

                # ステップ 3: 相対リターン計算
                st.info("ステップ 3/3: 相対リターンを計算中...")
                relative_returns = calculate_relative_returns(
                    sector_returns,
                    topix_return
                )

                # セッション状態に保存
                st.session_state.sector_rotation_data = {
                    "relative_returns": relative_returns,
                    "topix_return": topix_return,
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d")
                }

                st.success("✅ 分析完了！")

            except Exception as e:
                st.error(f"❌ 分析エラー: {e}")

                # 詳細なエラー情報を表示
                import traceback
                with st.expander("🔍 詳細なエラー情報（デバッグ用）"):
                    st.code(traceback.format_exc())

                # トラブルシューティング
                st.warning("### トラブルシューティング")
                st.write("**考えられる原因:**")
                st.write("1. J-Quants APIの認証エラー")
                st.write("2. APIのレート制限")
                st.write("3. ネットワークエラー")

                st.write("**確認事項:**")
                st.write("- Secrets設定でJ-Quants APIキーが正しく設定されているか")
                st.write("- リフレッシュトークンが有効期限内か")

                # APIテスト
                st.write("### API接続テスト")
                try:
                    test_result = st.session_state.client.get_company_info("72030")
                    if test_result:
                        st.success("✅ API接続は正常です")
                        st.write(f"テスト結果: {test_result.get('CompanyName', 'N/A')}")
                    else:
                        st.error("❌ API接続に失敗しました")
                except Exception as api_error:
                    st.error(f"❌ API接続エラー: {api_error}")

    # 結果表示
    if "sector_rotation_data" in st.session_state:
        data = st.session_state.sector_rotation_data

        st.markdown("---")
        st.subheader("📊 分析結果")

        # TOPIXリターン表示
        col_topix1, col_topix2 = st.columns(2)
        with col_topix1:
            st.metric("TOPIX リターン", f"{data['topix_return']:.2f}%")
        with col_topix2:
            st.caption(f"期間: {data['start_date']} 〜 {data['end_date']}")
            st.caption(f"データ: TOPIX-17業種指数")

        st.divider()

        # セクター別リターン（バーチャート）
        st.subheader("📈 セクター別相対リターン（TOPIX対比）")

        # データフレーム作成
        df = pd.DataFrame([
            {
                "セクター": sector_data["sector_name"],
                "絶対リターン (%)": sector_data["absolute_return"],
                "相対リターン (%)": sector_data["relative_return"]
            }
            for sector_code, sector_data in data["relative_returns"].items()
        ])

        # 相対リターンでソート（降順）
        df = df.sort_values("相対リターン (%)", ascending=False)

        # バーチャート（Plotly）
        fig = px.bar(
            df,
            x="相対リターン (%)",
            y="セクター",
            orientation="h",
            color="相対リターン (%)",
            color_continuous_scale="RdYlGn",
            title="TOPIX対比の相対リターン"
        )

        fig.update_layout(
            yaxis={'categoryorder': 'total ascending'},
            height=800
        )

        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # トップ5 / ボトム5
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🟢 強いセクター Top 5")
            top5 = df.head(5)
            for i, row in top5.iterrows():
                st.metric(
                    row["セクター"],
                    f"{row['絶対リターン (%)']:.2f}%",
                    delta=f"{row['相対リターン (%)']:+.2f}% vs TOPIX"
                )

        with col2:
            st.subheader("🔴 弱いセクター Top 5")
            bottom5 = df.tail(5).iloc[::-1]
            for i, row in bottom5.iterrows():
                st.metric(
                    row["セクター"],
                    f"{row['絶対リターン (%)']:.2f}%",
                    delta=f"{row['相対リターン (%)']:+.2f}% vs TOPIX",
                    delta_color="inverse"
                )

        st.divider()

        # 詳細データテーブル
        with st.expander("📋 全セクター詳細データ"):
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

    # 使い方ガイド
    with st.expander("📖 使い方ガイド"):
        st.markdown("""
        ### セクターローテーション分析の使い方

        #### 1. 期間を選択
        - **プリセット**: 1ヶ月、3ヶ月、6ヶ月、1年から選択
        - **カスタム**: 任意の開始日・終了日を指定

        #### 2. 分析開始
        - 「🔍 分析開始」ボタンをクリック
        - J-Quants APIからTOPIX-17業種指数データを取得し、計算を実行

        #### 3. 結果の見方
        - **相対リターン**: TOPIX対比のリターン（プラス=TOPIXより強い、マイナス=TOPIXより弱い）
        - **強いセクター Top 5**: TOPIXを上回った業種
        - **弱いセクター Top 5**: TOPIXを下回った業種

        ### TOPIX-17業種分類
        1. 食品
        2. エネルギー資源
        3. 建設・資材
        4. 素材・化学
        5. 医薬品
        6. 自動車・輸送機
        7. 鉄鋼・非鉄
        8. 機械
        9. 電機・精密
        10. 情報通信・サービスその他
        11. 電力・ガス
        12. 運輸・物流
        13. 商社・卸売
        14. 小売
        15. 銀行
        16. 金融（除く銀行）
        17. 不動産

        ### 活用方法
        - 📊 **セクターローテーション戦略**: 強いセクターに投資
        - 📊 **ポートフォリオバランス**: 保有銘柄のセクター偏りを確認
        - 📊 **マーケット分析**: 相場環境で優位なセクターを特定

        ### データソース
        - TOPIX-17業種指数（J-Quants API）
        - 東京証券取引所の公式業種分類
        - 高速で正確な分析が可能
        """)


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

    # 3. 初期資金の設定（未設定の場合のみ読み込み）
    if "initial_capital" not in st.session_state:
        loaded_value = get_initial_capital()
        st.session_state.initial_capital = loaded_value
        print(f"DEBUG: 初回読み込み - initial_capital = {loaded_value}")

    # 4. 追加投資履歴の設定（未設定の場合のみ読み込み、マイグレーション含む）
    if "additional_investments" not in st.session_state:
        loaded_value = get_additional_investments()  # 内部でマイグレーション実行
        st.session_state.additional_investments = loaded_value
        print(f"DEBUG: 初回読み込み - additional_investments = {loaded_value}")

    # 4. サイドバー
    render_sidebar()

    # 5. メインコンテンツ
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
    # バリュエーション分析表示
    elif st.session_state.get("current_view") == "valuation_analysis":
        render_valuation_analysis()
    # 資産推移分析表示
    elif st.session_state.get("current_view") == "asset_tracking":
        render_asset_tracking()
    # セクターローテーション分析表示
    elif st.session_state.get("current_view") == "sector_rotation":
        render_sector_rotation()
    # セクター強弱判定表示
    elif st.session_state.get("current_view") == "sector_strength":
        render_sector_strength()
    # 仮説詳細表示
    elif "selected_hypothesis" in st.session_state and st.session_state.selected_hypothesis:
        render_hypothesis_detail(st.session_state.selected_hypothesis)
    # 仮説一覧表示（デフォルト）
    else:
        render_hypothesis_list()


if __name__ == "__main__":
    main()
