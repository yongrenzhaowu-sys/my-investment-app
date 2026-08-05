# 実装計画: 投資判断支援アプリの機能追加

**作成日**: 2026-07-15 19:00
**目的**: 追加資金の永続化とオプション取引の損益記録機能を追加

---

## 背景

### 現状の問題

#### 問題1: 追加資金の永続化
- 追加資金の反映がしばらくすると消えてしまう
- 原因: ローカルファイル（`data/settings.json`）に保存しているが、Streamlit Cloudでは再起動時に消える
- 仮説データや売買履歴はGoogle Sheetsに保存されているが、追加資金は保存されていない

#### 問題2: オプション取引の損益記録
- 簿外でオプション取引を行っているが、記録する機能がない
- 簡易的でいいので、日付・取引内容・損益を記録したい

---

## 実装内容

### 機能1: 追加資金の永続化

#### 目的
追加資金をGoogle Sheetsに保存し、Streamlit Cloudでの再起動後も保持する。

#### 実装ステップ

##### 1. Google Sheetsの準備
- スプレッドシートに新しいシート「追加資金」を追加（手動）
- カラム構成:
  ```
  | date       | amount   |
  |------------|----------|
  | 2026-01-15 | 500000   |
  | 2026-05-01 | 1000000  |
  ```

##### 2. simple_gsheets_client.pyの拡張
- `load_additional_investments()`: 追加資金をGoogle Sheetsから読み込み
- `save_additional_investments()`: 追加資金をGoogle Sheetsに保存

**実装**:
```python
def load_additional_investments(self) -> List[Dict]:
    """
    追加資金をGoogle Sheetsから読み込み

    Returns:
        [{"date": "YYYY-MM-DD", "amount": 金額}, ...]
    """
    if not self.additional_investments_read_url:
        return []

    try:
        import time
        url = self.additional_investments_read_url + f"?_={int(time.time() * 1000)}"
        df = pd.read_csv(url)

        if df.empty:
            return []

        investments = []
        for idx, row in df.iterrows():
            if pd.isna(row.get("date")):
                continue

            investments.append({
                "date": str(row["date"]),
                "amount": float(row["amount"])
            })

        return sorted(investments, key=lambda x: x["date"])

    except Exception as e:
        st.warning(f"追加資金の読み込みエラー: {e}")
        return []

def save_additional_investments(self, investments: List[Dict]) -> None:
    """
    追加資金をGoogle Sheetsに保存

    Args:
        investments: [{"date": "YYYY-MM-DD", "amount": 金額}, ...]
    """
    if not self.write_url:
        st.error("書き込み用URLが設定されていません")
        return

    try:
        payload = {
            "action": "save_additional_investments",
            "data": investments
        }

        response = requests.post(self.write_url, json=payload, timeout=10)

        if response.status_code != 200:
            st.error(f"追加資金の保存エラー: {response.status_code}")
        else:
            st.success("追加資金を保存しました")

    except Exception as e:
        st.error(f"追加資金の保存エラー: {e}")
```

##### 3. settings.pyの修正
- `get_additional_investments()`: Google Sheets優先、フォールバックでローカルJSON
- `add_additional_investment()`: Google Sheetsにも保存
- `remove_additional_investment()`: Google Sheetsからも削除

**実装**:
```python
def get_additional_investments() -> List[Dict]:
    """
    追加投資履歴を取得（Google Sheets優先）

    Returns:
        [{"date": "YYYY-MM-DD", "amount": 金額}, ...]
    """
    # Google Sheetsを試す
    try:
        import streamlit as st
        from src.simple_gsheets_client import get_simple_gsheets_client

        if st.secrets.get("USE_GSHEETS", False):
            client = get_simple_gsheets_client()
            if client:
                investments = client.load_additional_investments()
                if investments:
                    return investments
    except Exception:
        pass

    # フォールバック: ローカルJSON
    settings = migrate_additional_capital()
    return settings.get("additional_investments", [])

def add_additional_investment(date: str, amount: float) -> bool:
    """
    追加投資を記録（Google Sheets + ローカルJSON）
    """
    # ローカルJSONに保存
    settings = load_settings()
    if "additional_investments" not in settings:
        settings["additional_investments"] = []

    settings["additional_investments"].append({"date": date, "amount": amount})
    settings["additional_investments"] = sorted(
        settings["additional_investments"],
        key=lambda x: x["date"]
    )

    success = save_settings(settings)

    # Google Sheetsにも保存
    try:
        import streamlit as st
        from src.simple_gsheets_client import get_simple_gsheets_client

        if st.secrets.get("USE_GSHEETS", False):
            client = get_simple_gsheets_client()
            if client:
                client.save_additional_investments(settings["additional_investments"])
    except Exception as e:
        st.warning(f"Google Sheetsへの保存に失敗: {e}")

    return success
```

##### 4. app.pyの修正
- 追加資金登録時に`add_additional_investment()`を呼び出す（既存のまま）
- アプリ起動時に`get_additional_investments()`で読み込む（既存のまま）

**確認点**: 既存のコードが正しく動作するか確認。

##### 5. secrets.tomlの更新
```toml
# 追加資金シートのCSV公開URL
ADDITIONAL_INVESTMENTS_READ_URL = "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/gviz/tq?tqx=out:csv&sheet=追加資金"
```

##### 6. Google Apps Scriptの更新
`save_additional_investments`アクションを追加:
```javascript
if (action === "save_additional_investments") {
  const sheet = ss.getSheetByName("追加資金");
  sheet.clear();
  sheet.appendRow(["date", "amount"]);

  data.forEach(function(item) {
    sheet.appendRow([item.date, item.amount]);
  });

  return ContentService.createTextOutput(JSON.stringify({status: "success"}))
    .setMimeType(ContentService.MimeType.JSON);
}
```

---

### 機能2: オプション取引の損益記録

#### 目的
簿外で行ったオプション取引の損益を簡易的に記録する。

#### データ構造
```
| id   | date       | description      | profit  | created_at          |
|------|------------|------------------|---------|---------------------|
| abc1 | 2026-07-10 | プットオプション売却 | 50000   | 2026-07-10 12:00:00 |
| abc2 | 2026-07-12 | コールオプション買戻 | -20000  | 2026-07-12 15:30:00 |
```

#### 実装ステップ

##### 1. Google Sheetsの準備
- スプレッドシートに新しいシート「オプション取引」を追加（手動）

##### 2. src/option_trades.pyの作成
```python
"""オプション取引管理モジュール"""
import json
import os
from typing import List, Dict
from datetime import datetime
import uuid


def get_option_trades_file_path() -> str:
    """オプション取引ファイルのパスを取得"""
    return os.path.join(os.path.dirname(__file__), "..", "data", "option_trades.json")


def load_option_trades_local() -> List[Dict]:
    """オプション取引をローカルJSONから読み込み"""
    file_path = get_option_trades_file_path()

    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"WARNING: オプション取引の読み込みに失敗: {e}")
        return []


def save_option_trades_local(trades: List[Dict]) -> bool:
    """オプション取引をローカルJSONに保存"""
    file_path = get_option_trades_file_path()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(trades, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"WARNING: オプション取引の保存に失敗: {e}")
        return False


def load_option_trades() -> List[Dict]:
    """オプション取引を読み込み（Google Sheets優先）"""
    # Google Sheetsを試す
    try:
        import streamlit as st
        from src.simple_gsheets_client import get_simple_gsheets_client

        if st.secrets.get("USE_GSHEETS", False):
            client = get_simple_gsheets_client()
            if client:
                trades = client.load_option_trades()
                if trades:
                    return trades
    except Exception:
        pass

    # フォールバック: ローカルJSON
    return load_option_trades_local()


def add_option_trade(date: str, description: str, profit: float) -> bool:
    """
    オプション取引を追加

    Args:
        date: 取引日（YYYY-MM-DD）
        description: 取引内容
        profit: 損益（円）

    Returns:
        成功時True
    """
    trades = load_option_trades_local()

    trade = {
        "id": str(uuid.uuid4()),
        "date": date,
        "description": description,
        "profit": profit,
        "created_at": datetime.now().isoformat()
    }

    trades.append(trade)

    # 日付順にソート
    trades = sorted(trades, key=lambda x: x["date"], reverse=True)

    success = save_option_trades_local(trades)

    # Google Sheetsにも保存
    try:
        import streamlit as st
        from src.simple_gsheets_client import get_simple_gsheets_client

        if st.secrets.get("USE_GSHEETS", False):
            client = get_simple_gsheets_client()
            if client:
                client.save_option_trades(trades)
    except Exception as e:
        print(f"Google Sheetsへの保存に失敗: {e}")

    return success


def delete_option_trade(trade_id: str) -> bool:
    """
    オプション取引を削除

    Args:
        trade_id: 取引ID

    Returns:
        成功時True
    """
    trades = load_option_trades_local()
    trades = [t for t in trades if t["id"] != trade_id]

    success = save_option_trades_local(trades)

    # Google Sheetsにも保存
    try:
        import streamlit as st
        from src.simple_gsheets_client import get_simple_gsheets_client

        if st.secrets.get("USE_GSHEETS", False):
            client = get_simple_gsheets_client()
            if client:
                client.save_option_trades(trades)
    except Exception as e:
        print(f"Google Sheetsへの保存に失敗: {e}")

    return success


def calculate_option_profit() -> float:
    """
    オプション損益合計を計算

    Returns:
        損益合計（円）
    """
    trades = load_option_trades()
    return sum(t["profit"] for t in trades)
```

##### 3. simple_gsheets_client.pyの拡張
```python
def load_option_trades(self) -> List[Dict]:
    """オプション取引をGoogle Sheetsから読み込み"""
    if not self.option_trades_read_url:
        return []

    try:
        import time
        url = self.option_trades_read_url + f"?_={int(time.time() * 1000)}"
        df = pd.read_csv(url)

        if df.empty:
            return []

        trades = []
        for idx, row in df.iterrows():
            if pd.isna(row.get("id")):
                continue

            trades.append({
                "id": str(row["id"]),
                "date": str(row["date"]),
                "description": str(row["description"]),
                "profit": float(row["profit"]),
                "created_at": str(row.get("created_at", ""))
            })

        return sorted(trades, key=lambda x: x["date"], reverse=True)

    except Exception as e:
        st.warning(f"オプション取引の読み込みエラー: {e}")
        return []

def save_option_trades(self, trades: List[Dict]) -> None:
    """オプション取引をGoogle Sheetsに保存"""
    if not self.write_url:
        st.error("書き込み用URLが設定されていません")
        return

    try:
        payload = {
            "action": "save_option_trades",
            "data": trades
        }

        response = requests.post(self.write_url, json=payload, timeout=10)

        if response.status_code != 200:
            st.error(f"オプション取引の保存エラー: {response.status_code}")

    except Exception as e:
        st.error(f"オプション取引の保存エラー: {e}")
```

##### 4. app.pyの修正
**サイドバーに追加**:
```python
# オプション取引記録
st.sidebar.markdown("---")
st.sidebar.subheader("オプション取引記録")

with st.sidebar.form("option_trade_form"):
    option_date = st.date_input("取引日", datetime.now())
    option_description = st.text_input("取引内容", placeholder="プットオプション売却など")
    option_profit = st.number_input("損益（円）", step=1000, format="%d")

    if st.form_submit_button("記録"):
        from src.option_trades import add_option_trade

        if add_option_trade(
            date=option_date.strftime("%Y-%m-%d"),
            description=option_description,
            profit=option_profit
        ):
            st.success("オプション取引を記録しました")
            st.rerun()
        else:
            st.error("記録に失敗しました")
```

**メイン画面に追加**:
```python
# オプション損益サマリー
from src.option_trades import load_option_trades, calculate_option_profit, delete_option_trade

st.subheader("オプション取引")

option_trades = load_option_trades()
total_option_profit = calculate_option_profit()

col1, col2 = st.columns(2)
with col1:
    st.metric("取引回数", f"{len(option_trades)}回")
with col2:
    st.metric("損益合計", f"¥{total_option_profit:,.0f}")

if option_trades:
    st.markdown("#### 取引履歴")

    for trade in option_trades:
        with st.expander(f"{trade['date']} - {trade['description']}"):
            st.write(f"**損益**: ¥{trade['profit']:,.0f}")
            st.write(f"**記録日時**: {trade['created_at']}")

            if st.button(f"削除", key=f"delete_option_{trade['id']}"):
                if delete_option_trade(trade['id']):
                    st.success("削除しました")
                    st.rerun()
                else:
                    st.error("削除に失敗しました")
```

##### 5. secrets.tomlの更新
```toml
# オプション取引シートのCSV公開URL
OPTION_TRADES_READ_URL = "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/gviz/tq?tqx=out:csv&sheet=オプション取引"
```

##### 6. Google Apps Scriptの更新
`save_option_trades`アクションを追加:
```javascript
if (action === "save_option_trades") {
  const sheet = ss.getSheetByName("オプション取引");
  sheet.clear();
  sheet.appendRow(["id", "date", "description", "profit", "created_at"]);

  data.forEach(function(item) {
    sheet.appendRow([
      item.id,
      item.date,
      item.description,
      item.profit,
      item.created_at
    ]);
  });

  return ContentService.createTextOutput(JSON.stringify({status: "success"}))
    .setMimeType(ContentService.MimeType.JSON);
}
```

---

## テスト計画

### 機能1: 追加資金の永続化
- [ ] ローカル環境で追加資金を登録 → `data/settings.json`に保存されるか確認
- [ ] Google Sheets環境で追加資金を登録 → シートに保存されるか確認
- [ ] アプリ再起動後に追加資金が保持されるか確認

### 機能2: オプション取引の損益記録
- [ ] オプション取引を記録 → ローカルJSON/Google Sheetsに保存されるか確認
- [ ] 損益合計が正しく計算されるか確認
- [ ] 取引を削除できるか確認
- [ ] アプリ再起動後にオプション取引が保持されるか確認

---

## ファイル構成

### 新規作成
```
apps/investment-tracker/
├── src/
│   └── option_trades.py          # オプション取引管理（新規）
├── data/
│   └── option_trades.json        # オプション取引データ（新規、ローカルのみ）
```

### 更新
```
apps/investment-tracker/
├── app.py                         # UI追加
├── src/
│   ├── simple_gsheets_client.py  # 追加資金とオプション取引のメソッド追加
│   └── settings.py               # Google Sheets対応
```

### Google Sheets
```
スプレッドシート
├── 保有銘柄（既存）
├── 売買履歴（既存）
├── 追加資金（新規）
└── オプション取引（新規）
```

---

## リスクと対策

### リスク1: Google Sheetsの読み込みエラー
- 対策: ローカルJSONにフォールバック
- 既存の仕組みと同じ

### リスク2: Google Apps Scriptの更新忘れ
- 対策: 実装計画に明記、ドキュメント化

### リスク3: 既存機能への影響
- 対策: 既存のコードは極力変更しない
- 追加のみで対応

---

## 次のステップ

1. Google Sheetsに新しいシート追加（手動）
2. `src/option_trades.py`を作成
3. `src/simple_gsheets_client.py`を更新
4. `src/settings.py`を更新
5. `app.py`を更新
6. ローカルテスト
7. Google Apps Scriptを更新（ユーザーが手動で実施）
8. Streamlit Cloudにデプロイ
9. 動作確認

---

**作成者**: Claude Code
**最終更新**: 2026-07-15 19:00
