# 投資判断支援アプリ StreamlitDuplicateElementKey 修正

## やったこと
- `apps/investment-tracker/` の構文・import・ローカルAppTestを確認 → ローカルでは再現せず
- 報告されたエラー: `StreamlitDuplicateElementKey`（app.py `render_hypothesis_list` の `key=f"detail_{hypo['id']}"`）
- 原因: Streamlit Cloud ではGoogle Sheets（CSV）から仮説を読むため、同一 `id` の行が重複していると、ボタンの key が衝突する（ローカルJSONには重複なし）
- 修正: `app.py` の `load_hypotheses()` で `id` 重複を除去（後の行を優先）し、除外件数を warning 表示

## 決めたこと
- 重複除去は読み込み層（`load_hypotheses`）で行い、Sheets/ローカル両方に効かせる

## 次にやること
- デプロイ後に Cloud で解消を確認
- シート側の重複行の原因調査（保存時の二重POST、Apps Script の追記挙動など）。重複除去後は次回保存でシートも整理される
- 未使用の `src/gsheets_client.py`（`streamlit_gsheets` 未インストール）は整理候補

## 重要なパス
- `apps/investment-tracker/app.py`（`load_hypotheses`）
- `apps/investment-tracker/src/simple_gsheets_client.py`
