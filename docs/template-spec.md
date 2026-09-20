# 自治体様式取り込み＋差し込み仕様（v0.1）

## 方式
1. 自治体の xlsx/docx を `templates/<prefecture>/<city>/<year>/` に登録
2. セル/段落内の差し込み箇所を `{{field_id}}` に置換（例：`{{long_goal}}`）
3. `src/schema/field_master.json` の共通IDにマッピング。自治体独自項目は `custom_*` で拡張
4. 差し込み実行 → 必須・文字数・形式チェック → プレビュー → PDF/原本出力

## 共通フィールド（抜粋）
- child_code（匿名管理番号、実名は別管理）
- grade, class_type（通常/通級/特別支援学級/特別支援学校）
- profile_strengths（好き・得意）, profile_needs（苦手・配慮点）
- guardian_wish, child_wish
- support_history, related_agencies（放デイ・医療・福祉等）
- support_long_goal（3年目安）, guidance_long_goal（1年）, short_goals[3], supports[], eval_method, eval_date
- conference_memo（参加者・目的・内容）, guardian_confirmed（bool＋日付）

## 文科省初期テンプレ
- `templates/mext/support_plan.txt`：個別の教育支援計画（プロフィール＋支援シート相当）
- `templates/mext/guidance_plan.txt`：個別の指導計画（実態→長期→短期→手立て→評価）
- 将来 docx/xlsx 化してもフィールドIDは同一に保つ。

## チェック規則
- 欠落フィールドがあれば印刷ブロック
- `{{...}}` 残存があれば出力拒否
- 年度・自治体コードの不一致は警告
