# J-Quants API V2 認証方式とStreamlitアプリ開発

**日時**: 2026-03-11 14:00
**トピック**: J-Quants API V2認証とStreamlitアプリ開発

## 背景

投資判断支援アプリをStreamlitで開発する際、J-Quants APIの認証方式について検討した。

## 学んだこと

### J-Quants API V1 vs V2

#### V1（リフレッシュトークン方式）
- メールアドレス/パスワードでログイン → リフレッシュトークン取得
- リフレッシュトークン → IDトークン取得
- IDトークンをAuthorizationヘッダーに設定
- トークンの有効期限管理が必要（24時間）

#### V2（APIキー方式）✅ 推奨
- APIキーを直接使用（シンプル）
- HTTPヘッダー `x-api-key` に設定
- 有効期限なし（永続的に使用可能）
- より簡潔な実装

### 認証コード（V2）

```python
import os

class JQuantsAuth:
    BASE_URL = "https://api.jquants.com/v2"

    def __init__(self):
        self.api_key = os.environ.get("JQUANTS_API_KEY")
        if not self.api_key:
            raise ValueError("JQUANTS_API_KEY が設定されていません")

    def get_headers(self) -> dict:
        return {"x-api-key": self.api_key}
```

### エンドポイントの違い

#### V1
- `/prices/daily_quotes`: 日次株価
- `/fins/statements`: 財務データ
- `/listed/info`: 銘柄情報

#### V2
- `/bars/daily`: 日次株価（パラメータ: `start_dt`, `end_dt` YYYYMMDD形式）
- `/fins/statements`: 財務データ（同じ）
- `/listed/info`: 銘柄情報（同じ）

### レスポンス形式の違い

#### V2 日次株価
```json
{
  "daily_bars": [
    {
      "Date": "2026-01-15",
      "Code": "72030",
      "AdjO": 2500.0,
      "AdjH": 2550.0,
      "AdjL": 2480.0,
      "AdjC": 2530.0,
      "AdjVo": 1000000
    }
  ]
}
```

調整済み終値は `AdjC` フィールド。

## Streamlitアプリ開発のベストプラクティス

### 環境変数管理
- Windows環境変数から読み込み（`os.environ.get()`）
- APIキーを絶対に表示しない
- マスク表示機能を実装（例: `IHae...zqXI`）

### セッション状態管理
- `st.session_state` で認証オブジェクトを保持
- 初回のみ認証、以降は再利用

```python
def initialize_session_state():
    if "auth" not in st.session_state:
        st.session_state.auth = JQuantsAuth()
        st.session_state.client = JQuantsClient(st.session_state.auth)
```

### データ保存
- JSON形式でローカル保存（`data/hypotheses.json`）
- `.gitignore` に追加（個人情報保護）

### モバイル最適化
- `st.set_page_config(layout="wide")`: レスポンシブレイアウト
- `use_container_width=True`: ボタンを画面幅に合わせる
- `st.columns()`: カード配置を柔軟に調整

## トラブルシューティング

### 文字エンコーディングエラー
**問題**: Windows cp932で絵文字が表示できない

```python
# ❌ エラー
print('✅ All modules imported successfully')
# UnicodeEncodeError: 'cp932' codec can't encode character '\u2705'

# ✅ 正しい
print('OK: All modules imported successfully')
```

**対策**: ASCII文字のみ使用、または環境変数 `PYTHONIOENCODING=utf-8` を設定

### 環境変数が読み込まれない
**問題**: PowerShellで設定した環境変数が認識されない

**対策**:
1. PowerShellを再起動
2. User環境変数を設定（Machine環境変数は管理者権限が必要）

```powershell
[System.Environment]::SetEnvironmentVariable('JQUANTS_API_KEY', 'your_key', 'User')
```

3. 確認:
```powershell
[System.Environment]::GetEnvironmentVariable('JQUANTS_API_KEY', 'User')
```

## 参考リンク

- J-Quants API V2ドキュメント: https://jpx.gitbook.io/j-quants-ja/api-reference/
- Streamlit公式ドキュメント: https://docs.streamlit.io/
- yfinance: https://pypi.org/project/yfinance/

## 次のステップ

1. 実際の株価データでアルファ計算をテスト
2. 財務データAPIのレスポンス形式を確認
3. 営業利益率の計算ロジックを検証
4. iPhone実機でレイアウトテスト
