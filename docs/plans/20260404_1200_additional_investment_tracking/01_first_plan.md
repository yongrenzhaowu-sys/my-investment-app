# 追加投資額トラッキング機能の実装計画

**作成日時**: 2026-04-04 12:00
**ステータス**: 計画中

---

## 📋 背景と要件

### 現状の問題
- 楽天証券と楽天銀行の間で資金がスイープされる（自動入出金）
- 初期資金 + 利益確定額を超える投資を行った場合、**投資可能額がマイナス**になる
- このマイナス分は、実際には楽天銀行から追加で入金された資金（追加投資）

### 要件
- 投資可能額がマイナスになった場合、**追加投資額**として明示的に管理したい
- 追加投資額を含めた正しい投資可能額を表示したい

---

## 🎯 実装方針

### 1. データモデルの拡張

#### settings.json
```json
{
  "initial_capital": 1000000,
  "additional_capital": 0  // 追加投資額（新規）
}
```

### 2. 計算ロジックの修正

#### 現在の計算式（profit_calculator.py）
```python
available_capital = initial_capital - current_investment + after_tax_profit
```

#### 修正後の計算式
```python
available_capital = initial_capital + additional_capital - current_investment + after_tax_profit
```

**変数の定義**：
- `initial_capital`: 最初に投入した資金
- `additional_capital`: 楽天銀行からスイープで追加された資金
- `current_investment`: 現在の保有額（購入価格 × 株数）
- `after_tax_profit`: 税引き後利益の累計

### 3. UIの追加・修正

#### 3.1 損益サマリー画面
**追加表示項目**：
- 初期資金
- **追加投資額**（新規）
- 合計投資額（初期資金 + 追加投資額）
- 利益確定額（税引き後）
- 投資可能額

**レイアウト案**：
```
┌─────────────────────────────────────┐
│ 総資産: ¥X,XXX,XXX (+X.XX%)        │
├─────────────────────────────────────┤
│ 保有証券 | 現金 | 合計投資額        │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│ 初期資金 | 追加投資額 | 利益確定額  │
└─────────────────────────────────────┘
```

#### 3.2 追加投資額の設定UI
**場所**: 「⚙️ 初期資金設定」のエキスパンダー内
**機能**:
- 現在の追加投資額を表示
- 手動で追加投資額を入力・更新
- **自動計算ボタン**: 投資可能額がマイナスの場合、そのマイナス分を追加投資額として記録

**実装案**：
```python
with st.expander("⚙️ 初期資金・追加投資額設定"):
    # 初期資金設定（既存）
    st.subheader("初期資金")
    ...

    # 追加投資額設定（新規）
    st.subheader("追加投資額")
    st.info(f"**現在の追加投資額**: ¥{st.session_state.additional_capital:,}")

    # 投資可能額がマイナスの場合、警告と自動計算ボタン
    if available_capital < 0:
        st.warning(f"⚠️ 投資可能額がマイナスです: ¥{available_capital:,}")
        if st.button("🔄 追加投資額を自動計算"):
            # マイナス分を追加投資額として記録
            new_additional = st.session_state.additional_capital + abs(available_capital)
            st.session_state.additional_capital = new_additional
            save_settings({"additional_capital": new_additional})
            st.success(f"✅ 追加投資額を ¥{new_additional:,} に更新しました")

    # 手動入力
    new_additional = st.number_input(
        "追加投資額を手動で設定（円）",
        value=int(st.session_state.additional_capital),
        step=100_000
    )
    if st.button("更新", key="update_additional_capital"):
        st.session_state.additional_capital = new_additional
        save_settings({"additional_capital": new_additional})
        st.success(f"✅ 追加投資額を ¥{new_additional:,} に更新しました")
```

---

## 🔧 実装手順

### ステップ1: `src/settings.py` の修正
- `get_additional_capital()` 関数を追加
- デフォルト値: 0円

### ステップ2: `src/profit_calculator.py` の修正
- `calculate_available_capital()` 関数に `additional_capital` パラメータを追加
- 計算式を修正

### ステップ3: `app.py` の修正
1. セッション状態の初期化に `additional_capital` を追加
2. 損益サマリー画面に追加投資額を表示
3. 設定UIに追加投資額の入力・更新機能を追加
4. 自動計算ボタンを実装

---

## ✅ 完了基準

- [ ] 追加投資額がsettings.jsonに保存される
- [ ] 投資可能額の計算に追加投資額が反映される
- [ ] 損益サマリー画面に追加投資額が表示される
- [ ] 投資可能額がマイナスの場合、警告が表示される
- [ ] 自動計算ボタンで追加投資額を自動的に記録できる
- [ ] 手動で追加投資額を変更できる
- [ ] ページ遷移後も値が保持される
- [ ] ブラウザリロード後も値が保持される

---

## 🚨 注意事項

### ルックアヘッドバイアス防止
- この機能はバックテストには関係しない（実運用のみ）
- データの利用可能性を意識する必要はない

### セキュリティ
- settings.jsonに追加投資額を保存（既存の初期資金と同じ扱い）
- 秘密情報ではないため、環境変数は不要

### 後方互換性
- settings.jsonに `additional_capital` がない場合、デフォルト値 0 を使用
- 既存の初期資金設定には影響を与えない

---

## 📝 次のステップ

1. この計画をレビュー
2. 承認後、実装開始
3. テスト
4. セッション記録作成
