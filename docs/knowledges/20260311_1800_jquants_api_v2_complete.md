# J-Quants API V2 完全ガイド

**作成日**: 2026-03-11
**検証済み**: ✅

---

## 概要

J-Quants API V2は、日本株の株価・財務データを提供するAPIです。V1からの主な変更点は認証方式の簡略化とエンドポイント名の変更です。

---

## 認証

### V2の認証方式（APIキー方式）

```python
headers = {"x-api-key": "your_api_key_here"}
response = requests.get(url, headers=headers)
```

- **ヘッダー名**: `x-api-key`
- **APIキー**: ダッシュボードから発行
- **有効期限**: なし（再発行・削除のみ可能）
- **V1との違い**: トークン方式（ID Token/Refresh Token）は廃止

---

## エンドポイント一覧

### ベースURL
```
https://api.jquants.com/v2
```

### 1. 株価データ（日次バー）

**エンドポイント**: `/equities/bars/daily`

**パラメータ**:
- `code`: 銘柄コード（4桁、例: `7203`）
- `start_dt`: 開始日（YYYYMMDD形式、例: `20260310`）
- `end_dt`: 終了日（YYYYMMDD形式、オプション）

**リクエスト例**:
```python
url = "https://api.jquants.com/v2/equities/bars/daily"
params = {"code": "7203", "start_dt": "20260310"}
headers = {"x-api-key": "your_api_key"}
response = requests.get(url, params=params, headers=headers)
```

**レスポンス構造**:
```json
{
  "data": [
    {
      "Date": "2026-03-10",
      "Code": "72030",
      "O": 6067.0,
      "H": 6188.0,
      "L": 6015.0,
      "C": 6140.0,
      "AdjO": 1213.4,
      "AdjH": 1237.6,
      "AdjL": 1203.0,
      "AdjC": 1228.0,
      "AdjVo": 64590500.0
    }
  ]
}
```

**主要列**:
- `Date`: 日付（文字列、YYYY-MM-DD）
- `Code`: 銘柄コード（5桁、文字列）
- `O`, `H`, `L`, `C`: 生の四本値
- `AdjO`, `AdjH`, `AdjL`, `AdjC`: 調整済み四本値
- `AdjVo`: 調整済み出来高

**注意点**:
- レスポンスのCodeは5桁（例: `72030`）
- パラメータのcodeは4桁（例: `7203`）
- データは1〜2日遅れ
- `end_dt`を省略すると最新データまで取得

---

### 2. 財務データ（サマリー）

**エンドポイント**: `/fins/summary`（V1の`/fins/statements`から変更）

**パラメータ**:
- `code`: 銘柄コード（4桁、例: `7203`）

**リクエスト例**:
```python
url = "https://api.jquants.com/v2/fins/summary"
params = {"code": "7203"}
headers = {"x-api-key": "your_api_key"}
response = requests.get(url, params=params, headers=headers)
```

**レスポンス構造**:
```json
{
  "data": [
    {
      "DiscDate": "2016-05-11",
      "Code": "72030",
      "CurPerEn": "2016-03-31",
      "Sales": "28403118000000",
      "OP": "2853971000000",
      "NP": "2312694000000",
      "EPS": "724.65"
    }
  ]
}
```

**主要列**:
- `DiscDate`: 開示日（YYYY-MM-DD）
- `Code`: 銘柄コード（5桁）
- `CurPerEn`: 会計期間終了日（YYYY-MM-DD）
- `Sales`: 売上高（文字列、要数値変換）
- `OP`: 営業利益（文字列、要数値変換）
- `OdP`: 経常利益
- `NP`: 純利益
- `EPS`: 1株あたり利益
- `BPS`: 1株あたり純資産

**注意点**:
- **数値が文字列型**で返ってくる → `pd.to_numeric()`で変換必要
- 最新データから過去順にソート済み
- `.iloc[0]`で最新決算を取得

---

### 3. 銘柄情報

**エンドポイント**: `/listed/info`

**パラメータ**:
- `code`: 銘柄コード（4桁、例: `7203`）

**リクエスト例**:
```python
url = "https://api.jquants.com/v2/listed/info"
params = {"code": "7203"}
headers = {"x-api-key": "your_api_key"}
response = requests.get(url, params=params, headers=headers)
```

**レスポンス構造**:
```json
{
  "data": [
    {
      "Code": "72030",
      "CompanyName": "トヨタ自動車株式会社",
      "MarketCode": "111"
    }
  ]
}
```

---

## V1 → V2 移行対応表

| 機能 | V1エンドポイント | V2エンドポイント |
|------|-----------------|-----------------|
| 株価四本値 | `/prices/daily_quotes` | `/equities/bars/daily` |
| 財務サマリー | `/fins/statements` | `/fins/summary` |
| 銘柄一覧 | `/listed/info` | `/listed/info` |

| 項目 | V1 | V2 |
|------|----|----|
| 認証 | `Authorization: Bearer {idToken}` | `x-api-key: {api_key}` |
| レスポンス | `{"daily_quotes": [...]}` | `{"data": [...]}` |

---

## 実装パターン

### パターン1: 認証クラス

```python
class JQuantsAuth:
    BASE_URL = "https://api.jquants.com/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_headers(self) -> dict:
        return {"x-api-key": self.api_key}
```

### パターン2: 株価取得

```python
def get_daily_quotes(code: str, from_date: str, to_date: str = None):
    url = "https://api.jquants.com/v2/equities/bars/daily"

    # 5桁→4桁変換
    code_param = code[:4] if len(code) == 5 else code

    params = {"code": code_param, "start_dt": from_date.replace("-", "")}
    if to_date:
        params["end_dt"] = to_date.replace("-", "")

    response = session.get(url, params=params)
    data = response.json()

    df = pd.DataFrame(data["data"])

    # 銘柄コードでフィルタ
    df = df[df["Code"] == code].copy()

    # 日付範囲でフィルタ
    df["Date"] = pd.to_datetime(df["Date"])
    df = df[df["Date"] >= pd.to_datetime(from_date)].copy()

    return df
```

### パターン3: 財務データ取得＆営業利益率計算

```python
def get_operating_margin(code: str):
    url = "https://api.jquants.com/v2/fins/summary"

    # 5桁→4桁変換
    code_param = code[:4] if len(code) == 5 else code

    params = {"code": code_param}
    response = session.get(url, params=params)
    data = response.json()

    df = pd.DataFrame(data["data"])

    if df.empty:
        return None

    latest = df.iloc[0]

    # 数値変換（重要！）
    op = pd.to_numeric(latest["OP"], errors='coerce')
    sales = pd.to_numeric(latest["Sales"], errors='coerce')

    if pd.isna(op) or pd.isna(sales) or sales == 0:
        return None

    operating_margin = (op / sales) * 100
    return operating_margin
```

---

## よくある問題と解決策

### 問題1: 403 Forbidden エラー

**原因**: エンドポイントURLが間違っている

**解決策**:
- `/bars/daily` → `/equities/bars/daily` に修正
- `/fins/statements` → `/fins/summary` に修正

### 問題2: データが取得できない

**原因**:
1. 銘柄コードのフィルタリング不足
2. 日付範囲が現在日（データなし）

**解決策**:
1. レスポンスのCode列でフィルタリング
2. `end_dt`を省略してAPIに最新データを任せる

### 問題3: 型エラー（str / str）

**原因**: 財務データの数値が文字列型

**解決策**:
```python
value = pd.to_numeric(latest["Sales"], errors='coerce')
```

### 問題4: 銘柄コードの桁数

**原因**: APIは4桁を期待、データは5桁

**解決策**:
```python
# APIリクエスト時: 5桁→4桁
code_param = code[:4] if len(code) == 5 else code

# レスポンスフィルタ時: 5桁で照合
df = df[df["Code"] == code].copy()  # codeは5桁
```

---

## パフォーマンス最適化

### 1. キャッシュ戦略
- 株価データ: 日次で更新（1日1回取得）
- 財務データ: 四半期で更新（3ヶ月1回）

### 2. レート制限
- プランにより異なる
- リトライ処理を実装

### 3. バッチ取得
- 銘柄コードなしで全銘柄取得
- フィルタリングはクライアント側

---

## セキュリティ

### APIキーの管理
```python
# ❌ 悪い例
api_key = "your_api_key_here"  # コードに直書き

# ✅ 良い例
api_key = os.environ.get("JQUANTS_API_KEY")

# ✅ Streamlitの場合
api_key = st.secrets["JQUANTS_API_KEY"]
```

### ログ出力
```python
# ❌ 悪い例
print(f"API Key: {api_key}")

# ✅ 良い例
masked = f"{api_key[:4]}...{api_key[-4:]}"
print(f"API Key: {masked}")
```

---

## 参考リンク

- [J-Quants API V2ドキュメント](https://jpx-jquants.com/ja/spec)
- [V1→V2移行ガイド](https://jpx-jquants.com/ja/spec/migration-v1-v2)
- [財務データAPI](https://jpx.gitbook.io/j-quants-ja/api-reference/statements)
- [GitHub: jquants-api-client-python](https://github.com/J-Quants/jquants-api-client-python)

---

## 更新履歴

- 2026-03-11: 初版作成（投資判断支援アプリ開発時に検証）
