# セクターローテーション分析機能

**作成日**: 2026-04-30 20:00
**目的**: J-Quants APIを使用して、TOPIX対比で各業種セクターの相対リターンを可視化し、現在強いセクターを特定できるようにする

## 背景

セクターローテーション分析により：
- 相場環境で優位なセクターを特定
- ポートフォリオのセクターバランスを確認
- セクター間の資金移動を可視化

## J-Quants APIで取得可能なデータ

### 1. セクター情報（33業種分類）
**エンドポイント**: `/listed/info`

```json
{
  "Code": "72030",
  "Sector33Code": "5050",
  "Sector33CodeName": "情報・通信業",
  ...
}
```

**33業種分類**:
- 0050: 水産・農林業
- 1050: 鉱業
- 2050: 建設業
- 3050: 食料品
- 3100: 繊維製品
- 3150: パルプ・紙
- 3200: 化学
- 3250: 医薬品
- 3300: 石油・石炭製品
- 3350: ゴム製品
- 3400: ガラス・土石製品
- 3450: 鉄鋼
- 3500: 非鉄金属
- 3550: 金属製品
- 3600: 機械
- 3650: 電気機器
- 3700: 輸送用機器
- 3750: 精密機器
- 3800: その他製品
- 4050: 電気・ガス業
- 5050: 情報・通信業
- 5100: 運輸・郵便業
- 5150: 卸売業
- 5200: 小売業
- 5250: 銀行業
- 5300: 証券、商品先物取引業
- 5350: 保険業
- 5400: その他金融業
- 5450: 不動産業
- 6050: サービス業

### 2. 株価データ
**エンドポイント**: `/prices/daily_quotes`

```json
{
  "Code": "72030",
  "Date": "2026-04-30",
  "Close": 1500.0,
  "MarketCapitalization": 1000000,
  ...
}
```

### 3. TOPIXデータ
**エンドポイント**: `/indices/topix`

```json
{
  "Date": "2026-04-30",
  "Close": 2800.0,
  ...
}
```

## 実装計画

### Phase 1: セクター情報取得モジュール

**ファイル**: workspace/apps/investment-tracker/src/sector_data.py（新規）

#### 1.1 セクターマスター取得

```python
def get_sector_master(client: JQuantsClient) -> Dict[str, Dict]:
    """
    全銘柄のセクター情報を取得

    Returns:
        {
            "72030": {
                "code": "72030",
                "name": "スプリックス",
                "sector_code": "5050",
                "sector_name": "情報・通信業"
            },
            ...
        }
    """
```

#### 1.2 セクター別銘柄リスト

```python
def get_stocks_by_sector(client: JQuantsClient) -> Dict[str, List[str]]:
    """
    セクターごとの銘柄コードリストを取得

    Returns:
        {
            "5050": ["72030", "43900", ...],  # 情報・通信業
            "6050": ["46890", ...],  # サービス業
            ...
        }
    """
```

### Phase 2: リターン計算モジュール

**ファイル**: workspace/apps/investment-tracker/src/sector_returns.py（新規）

#### 2.1 セクター別リターン計算

```python
def calculate_sector_returns(
    client: JQuantsClient,
    start_date: str,
    end_date: str,
    method: str = "equal_weight"  # "equal_weight" or "market_cap_weight"
) -> Dict[str, float]:
    """
    各セクターのリターンを計算

    Args:
        client: J-Quants APIクライアント
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        method: 加重方法（等加重 or 時価総額加重）

    Returns:
        {
            "5050": 5.2,  # 情報・通信業: +5.2%
            "6050": -2.1,  # サービス業: -2.1%
            ...
        }
    """
```

**計算方法**:
- **等加重**: セクター内の全銘柄の平均リターン
- **時価総額加重**: セクター内の時価総額加重平均リターン（より正確）

#### 2.2 TOPIXリターン計算

```python
def calculate_topix_return(
    client: JQuantsClient,
    start_date: str,
    end_date: str
) -> float:
    """
    TOPIXのリターンを計算

    Args:
        client: J-Quants APIクライアント
        start_date: 開始日
        end_date: 終了日

    Returns:
        TOPIXリターン（%）
    """
```

#### 2.3 相対リターン計算

```python
def calculate_relative_returns(
    sector_returns: Dict[str, float],
    topix_return: float
) -> Dict[str, Dict]:
    """
    TOPIX対比の相対リターンを計算

    Args:
        sector_returns: セクターリターン
        topix_return: TOPIXリターン

    Returns:
        {
            "5050": {
                "absolute_return": 5.2,
                "relative_return": 3.5,  # TOPIX+3.5%
                "sector_name": "情報・通信業"
            },
            ...
        }
    """
```

### Phase 3: UI実装（Streamlit）

**ファイル**: workspace/apps/investment-tracker/app.py（修正）

#### 3.1 メニュー追加

**変更箇所**: render_sidebar()（行194付近）

```python
menu = st.sidebar.radio(
    "選択してください",
    [
        "📋 仮説登録",
        "📊 損益サマリー",
        "📜 売買履歴",
        "📈 バリュエーション分析",
        "💰 資産推移分析",
        "🔄 セクターローテーション"  # 新規追加
    ],
    label_visibility="collapsed"
)
```

#### 3.2 セクターローテーション画面

**新規関数**: render_sector_rotation()

```python
def render_sector_rotation():
    """セクターローテーション分析を表示"""
    st.title("🔄 セクターローテーション分析")
    st.markdown("TOPIX対比で各業種セクターの相対リターンを分析します。")

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
            start_date = st.date_input("開始日")
        with col2_2:
            end_date = st.date_input("終了日")
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

    # 加重方法選択
    col3, _ = st.columns([1, 3])
    with col3:
        method = st.selectbox(
            "加重方法",
            ["時価総額加重", "等加重"],
            help="時価総額加重: より正確だが計算時間がかかる"
        )

    # 計算ボタン
    if st.button("🔍 分析開始", type="primary", use_container_width=True):
        with st.spinner("セクター別リターンを計算中..."):
            try:
                # セクターリターン計算
                sector_returns = calculate_sector_returns(
                    st.session_state.client,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    method="market_cap_weight" if method == "時価総額加重" else "equal_weight"
                )

                # TOPIXリターン計算
                topix_return = calculate_topix_return(
                    st.session_state.client,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")
                )

                # 相対リターン計算
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

                st.success("分析完了！")

            except Exception as e:
                st.error(f"分析エラー: {e}")

    # 結果表示
    if "sector_rotation_data" in st.session_state:
        data = st.session_state.sector_rotation_data

        st.markdown("---")
        st.subheader("📊 分析結果")

        # TOPIXリターン表示
        st.metric("TOPIX リターン", f"{data['topix_return']:.2f}%")
        st.caption(f"期間: {data['start_date']} 〜 {data['end_date']}")

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
```

### Phase 4: キャッシュ戦略

大量のAPIコールを避けるため、キャッシュを活用：

#### 4.1 セクターマスターのキャッシュ

```python
@st.cache_data(ttl=86400)  # 24時間キャッシュ
def get_sector_master_cached(client):
    return get_sector_master(client)
```

#### 4.2 株価データのキャッシュ

```python
@st.cache_data(ttl=3600)  # 1時間キャッシュ
def get_sector_prices_cached(client, start_date, end_date):
    return get_sector_prices(client, start_date, end_date)
```

## 実装順序

1. ✅ **sector_data.py 作成**
   - get_sector_master()
   - get_stocks_by_sector()

2. ✅ **sector_returns.py 作成**
   - calculate_sector_returns()
   - calculate_topix_return()
   - calculate_relative_returns()

3. ✅ **app.py 修正**
   - メニュー追加
   - render_sector_rotation() 追加

4. ✅ **テスト・調整**
   - 計算精度の確認
   - パフォーマンスの最適化

## テスト項目

### 基本動作
- [ ] セクターマスターが正しく取得できる
- [ ] 株価データが正しく取得できる
- [ ] TOPIXデータが正しく取得できる

### 計算精度
- [ ] セクターリターンが正しく計算される
- [ ] TOPIXリターンが正しく計算される
- [ ] 相対リターンが正しく計算される

### UI/UX
- [ ] 期間選択が直感的
- [ ] バーチャートが見やすい
- [ ] トップ5/ボトム5が適切に表示される

### パフォーマンス
- [ ] 1ヶ月データの取得・計算が30秒以内
- [ ] キャッシュが効いている

## リスク

### 中リスク
- APIレート制限に引っかかる可能性
- 大量の株価データ取得に時間がかかる

### 対策
- キャッシュを活用
- バッチ処理で効率化
- プログレスバーで進捗を表示

## 完了条件

- [x] sector_data.py 作成完了
- [x] sector_returns.py 作成完了
- [x] app.py 修正完了
- [x] 基本動作テスト完了
- [x] docs/sessions/にセッションサマリー保存
- [x] GitHubにプッシュ
