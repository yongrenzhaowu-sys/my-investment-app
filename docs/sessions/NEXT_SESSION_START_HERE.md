# 次回セッション開始ガイド

**前回セッション**: 2026-03-14 16:00（Google Sheets統合完全実装）
**次回タスク**: 銘柄名表示の修正 → 初期資金永続化 → 部分売却 → NISA対応 → 投資指標

---

## 📍 現在の状態

### ✅ 完成したもの

**投資判断支援アプリ**（`apps/investment-tracker/`）
- ログイン機能（パスワード認証）✅
- 仮説登録（銘柄コード、購入日、購入価格、購入数量、理由、KPI）✅
- 仮説編集機能（購入情報の修正）✅
- アルファ計算（個別 vs S&P500）✅
- グラフ表示（Plotly）✅
- KPIチェック（営業利益率）✅
- 売却機能（売却日、価格、理由、税金計算20.315%）✅
- 売買履歴（フィルター、ソート）✅
- 損益サマリー（実現損益、含み損益、合計損益、余力、年間損益）✅
- 株数対応（すべての計算で株数を考慮）✅
- **Google Sheets統合**（データ永続化）✅
- **セッション状態マスター化**（連続登録問題の根本的解決）✅

### 🔧 デプロイ済み

- **GitHubリポジトリ**: https://github.com/yongrenzhaowu-sys/my-investment-app
- **Streamlit Cloud**: デプロイ済み、動作確認済み ✅
- **現在の設定**: `USE_GSHEETS = true`（Google Sheets保存）

### 📊 データ保存先

- **本番環境**: Google Sheets
- **セッション内**: Streamlitセッション状態（マスターデータ）
- **動作**: 即座に反映、連続登録OK、データ消失なし

---

## 🎉 前回の成果（2026-03-14）

### Google Sheets統合完全実装

#### 完了した作業
1. ✅ Google Spreadsheetsセットアップ
2. ✅ CSV公開URL取得
3. ✅ Apps Scriptデプロイ
4. ✅ Streamlit CloudのSecrets設定
5. ✅ sharesフィールド対応
6. ✅ ヘッダー行のスペース問題修正
7. ✅ NaN値の処理追加
8. ✅ エラーハンドリング強化
9. ✅ **セッション状態マスター化**（連続登録問題の根本的解決）

#### 解決した問題
- ✅ データ読み込みエラー「'purchase_date'」
- ✅ NaN値のエラー「cannot convert float NaN to integer」
- ✅ 2銘柄目以降が表示されない
- ✅ **連続登録でデータが消える、2重登録される** ← 最重要問題を解決！

#### 技術的なブレークスルー
**セッション状態マスター化**により、Google SheetsのCSV公開遅延問題を完全に回避：
- セッション状態をマスターデータとして使用
- Google Sheetsへの保存は非同期（バックグラウンド）
- 即座に画面に反映、待機不要
- 連続登録でもデータ消失なし

---

## 🚨 既知の問題点（次回修正）

### 問題1: 銘柄名が表示されない ⚠️
- **現状**: 「銘柄XXXXX」と表示される
- **原因**: API呼び出しまたはレスポンス処理の問題
- **優先度**: 高（次回最優先）

### 問題2: 初期資金設定が保存されない ⚠️
- **現状**: ログインごとに1,000,000円にリセット
- **原因**: セッション状態で管理
- **解決策**: settings.jsonに永続化

### 問題3: 部分売却ができない ⚠️
- **現状**: 全株売却のみ
- **解決策**: 売却数量フィールドを追加

### 問題4: NISA口座に対応していない ⚠️
- **現状**: すべて課税口座（税率20.315%）
- **要望**: NISA口座は税金0%

### 問題5: 投資指標がない ⚠️
- **現状**: アルファとリターンのみ
- **要望**: シャープレシオ、最大ドローダウン、勝率など

---

## 🎯 次回タスク（優先順位順）

### 【最優先】タスク6: 銘柄名表示の修正（30分）

**目的**: 「銘柄XXXXX」を正しい銘柄名に修正

**調査手順**:

#### ステップ1: 現在の実装を確認
```bash
# src/api.py の get_company_info() を確認
```

#### ステップ2: J-Quants API V2のレスポンス確認
- エンドポイント: `/v2/listed/info`
- レスポンスのキー名を確認（CompanyName, company_name, Name, CompanyNameJP等）

#### ステップ3: エラーログ確認
- Streamlit Cloudのログで、API呼び出しのエラーを確認

#### ステップ4: 修正実装
```python
# src/api.py の get_company_info() を修正
def get_company_info(self, code: str) -> dict:
    # レスポンスのキー名を正しく修正
    # エラーハンドリング強化
    # デバッグログ追加
```

---

### タスク7: 初期資金設定の永続化（30分）

**実装**:

#### ステップ1: settings管理モジュール作成
```python
# apps/investment-tracker/src/settings.py
import json
import os

def load_settings():
    """設定を読み込み"""
    file_path = "data/settings.json"
    if not os.path.exists(file_path):
        return {"initial_capital": 1000000}
    with open(file_path, "r") as f:
        return json.load(f)

def save_settings(settings):
    """設定を保存"""
    with open("data/settings.json", "w") as f:
        json.dump(settings, f, indent=2)
```

#### ステップ2: .gitignoreに追加
```
apps/investment-tracker/data/settings.json
```

#### ステップ3: app.pyで使用
```python
from src.settings import load_settings, save_settings

# 損益サマリー画面で
settings = load_settings()
initial_capital = settings.get("initial_capital", 1000000)

# 初期資金更新時
settings["initial_capital"] = new_capital
save_settings(settings)
```

#### ステップ4: Google Sheets対応
- settings.jsonもGoogle Sheetsに保存するか検討
- または、ローカルファイルのみで管理

---

### タスク8: 部分売却機能の実装（1時間）

**実装**:

#### ステップ1: 売却フォームに売却数量フィールド追加
```python
# app.py の render_sell_form()
shares = hypo.get("shares", 100)
sell_shares = st.number_input(
    "売却数量（株）",
    min_value=1,
    max_value=shares,
    value=shares,  # デフォルトは全株
    step=100
)
```

#### ステップ2: 部分売却処理
```python
# 残株数を計算
remaining_shares = shares - sell_shares

if remaining_shares > 0:
    # 部分売却: 仮説を更新
    hypo["shares"] = remaining_shares
    hypotheses = [hypo if h["id"] == hypothesis_id else h for h in hypotheses]
    save_hypotheses(hypotheses)
else:
    # 全株売却: 仮説から削除
    hypotheses = [h for h in hypotheses if h["id"] != hypothesis_id]
    save_hypotheses(hypotheses)
```

#### ステップ3: 売買履歴に売却数量を記録
```python
# src/trading_history.py の add_sell_record()
def add_sell_record(hypothesis, sell_date, sell_price, sell_shares, sell_reason):
    # ...
    record = TradingRecord(
        # ...
        shares=sell_shares,  # 売却した株数のみ記録
        # ...
    )
```

---

### タスク9: NISA口座対応（1時間）

**実装**:

#### ステップ1: 仮説登録フォームにチェックボックス追加
```python
# app.py の render_sidebar()
is_nisa = st.checkbox("NISA口座", value=False)

new_hypothesis = {
    # ...
    "is_nisa": is_nisa,
    # ...
}
```

#### ステップ2: 税金計算を修正
```python
# src/models.py の calculate_tax()
def calculate_tax(profit: float, is_nisa: bool = False) -> float:
    """
    株式譲渡所得税を計算

    Args:
        profit: 実現損益
        is_nisa: NISA口座フラグ

    Returns:
        税金額（NISA口座または損失時は0）
    """
    if is_nisa or profit <= 0:
        return 0.0

    tax_rate = 0.20315
    return profit * tax_rate
```

#### ステップ3: 売却フォームでNISA表示
```python
# app.py の render_sell_form()
is_nisa = hypo.get("is_nisa", False)
if is_nisa:
    st.success("✅ NISA口座（税金0%）")
else:
    st.info("課税口座（税率20.315%）")
```

#### ステップ4: 損益サマリーでNISA/課税口座を区別
```python
# 実現損益セクション
nisa_records = [r for r in history if r.get("is_nisa", False)]
taxable_records = [r for r in history if not r.get("is_nisa", False)]

st.write(f"NISA口座: {len(nisa_records)}件")
st.write(f"課税口座: {len(taxable_records)}件")
```

#### ステップ5: Google Sheetsスキーマ更新
- hypothesesシートに `is_nisa` 列を追加
- Apps Scriptを更新

#### ステップ6: 既存データの移行
- デフォルト: `is_nisa = false`（課税口座）
- 編集機能でNISA銘柄を手動で更新

---

### タスク10: 投資指標の追加（1時間）

**実装する指標**:

#### 1. シャープレシオ
```python
# src/metrics.py（新規作成）
import numpy as np

def calculate_sharpe_ratio(returns, risk_free_rate=0.001):
    """
    シャープレシオを計算

    Args:
        returns: リターンのリスト
        risk_free_rate: リスクフリーレート（年率0.1%想定）

    Returns:
        シャープレシオ
    """
    if len(returns) < 2:
        return 0.0

    avg_return = np.mean(returns)
    std_return = np.std(returns)

    if std_return == 0:
        return 0.0

    return (avg_return - risk_free_rate) / std_return
```

#### 2. 最大ドローダウン
```python
def calculate_max_drawdown(portfolio_values):
    """
    最大ドローダウンを計算

    Args:
        portfolio_values: 時系列の評価額リスト

    Returns:
        最大ドローダウン（%）
    """
    if len(portfolio_values) < 2:
        return 0.0

    cummax = np.maximum.accumulate(portfolio_values)
    drawdown = (portfolio_values - cummax) / cummax
    return abs(np.min(drawdown)) * 100
```

#### 3. 勝率
```python
def calculate_win_rate(trading_history):
    """
    勝率を計算

    Args:
        trading_history: 売買履歴

    Returns:
        勝率（%）
    """
    if not trading_history:
        return 0.0

    wins = sum(1 for r in trading_history if r["realized_profit"] > 0)
    total = len(trading_history)

    return (wins / total) * 100
```

#### 4. 平均保有日数
```python
def calculate_avg_holding_days(trading_history):
    """
    平均保有日数を計算

    Args:
        trading_history: 売買履歴

    Returns:
        平均保有日数
    """
    if not trading_history:
        return 0

    total_days = sum(r["holding_days"] for r in trading_history)
    return total_days / len(trading_history)
```

#### 5. 累計リターン
```python
def calculate_total_return(
    initial_capital,
    current_investment,
    unrealized_profit,
    cumulative_sales
):
    """
    累計リターンを計算

    Args:
        initial_capital: 初期資金
        current_investment: 現在保有額
        unrealized_profit: 含み損益
        cumulative_sales: 累計売却額（税引き後）

    Returns:
        累計リターン（%）
    """
    current_value = current_investment + unrealized_profit + cumulative_sales
    return ((current_value - initial_capital) / initial_capital) * 100
```

#### 6. 損益サマリー画面に表示
```python
# app.py の render_profit_summary()
from src.metrics import (
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_win_rate,
    calculate_avg_holding_days,
    calculate_total_return
)

st.subheader("📈 投資指標")

col1, col2, col3, col4 = st.columns(4)

with col1:
    sharpe = calculate_sharpe_ratio([...])
    st.metric("シャープレシオ", f"{sharpe:.2f}")

with col2:
    max_dd = calculate_max_drawdown([...])
    st.metric("最大DD", f"{max_dd:.2f}%")

with col3:
    win_rate = calculate_win_rate(trading_history)
    st.metric("勝率", f"{win_rate:.1f}%")

with col4:
    avg_days = calculate_avg_holding_days(trading_history)
    st.metric("平均保有日数", f"{avg_days:.0f}日")
```

---

## 📂 重要なファイル

### 既存ファイル
- `apps/investment-tracker/app.py` - メインアプリ
- `apps/investment-tracker/src/api.py` - J-Quants API接続
- `apps/investment-tracker/src/models.py` - データモデル
- `apps/investment-tracker/src/trading_history.py` - 売買履歴管理
- `apps/investment-tracker/src/profit_calculator.py` - 損益計算
- `apps/investment-tracker/src/simple_gsheets_client.py` - Google Sheets接続

### 次回作成するファイル
- `apps/investment-tracker/src/settings.py` - 設定管理（初期資金など）
- `apps/investment-tracker/src/metrics.py` - 投資指標計算

### データファイル（.gitignoreで保護）
- `apps/investment-tracker/data/hypotheses.json` - 保持中の仮説（ローカルバックアップ）
- `apps/investment-tracker/data/trading_history.json` - 売買履歴
- `apps/investment-tracker/data/settings.json` - 設定（次回作成）
- `apps/investment-tracker/.streamlit/secrets.toml` - APIキー、パスワード

### Google Sheets
- **スプレッドシート**: investment-tracker-data
- **シート**: hypotheses（現在）、trading_history（将来）、settings（将来）

---

## 🔗 リンク

### GitHubリポジトリ
- https://github.com/yongrenzhaowu-sys/my-investment-app

### Streamlit Cloud
- デプロイ済み、動作確認済み

### 参考ドキュメント
- `apps/investment-tracker/SIMPLE_GSHEETS_SETUP.md` - Google Sheets統合手順
- `docs/plans/20260312_0000_trading_history/01_plan.md` - 売買履歴機能の計画
- `docs/sessions/20260314_1600_gsheets_integration_complete.md` - 今回の完全記録

---

## 💡 次回セッション開始時のメッセージ

Claudeに以下のように伝えてください:

```
前回の続きから始めたいです。
docs/sessions/NEXT_SESSION_START_HERE.md を確認してください。

優先タスク:
1. 銘柄名表示の修正（「銘柄XXXXX」問題）
2. 初期資金設定の永続化
3. 部分売却機能
4. NISA口座対応
5. 投資指標追加
```

---

## 📊 推定工数

- タスク6（銘柄名修正）: 30分
- タスク7（初期資金永続化）: 30分
- タスク8（部分売却）: 1時間
- タスク9（NISA対応）: 1時間
- タスク10（投資指標）: 1時間

**合計**: 約4時間

---

お疲れさまでした！次回は銘柄名表示の修正から始めましょう。🎉
