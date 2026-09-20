# 汎用テンプレ取込仕様（v0.2・自治体不問）

## 対応形式
- `.txt` / `.docx` / `.xlsx`（将来PDFは読取専用・差し込み不可と明示）

## 取込フロー
1. `POST /api/templates/upload` で原本を保存（`backend/data/templates/{id}/original.*`）
2. サーバが差し込み口（slot）を自動抽出して返す
3. UIで `slot_id → 共通field_id（or custom_*）` をマッピング保存
4. `POST /api/merge/preview` で差し込み＋厳密チェック

## slot抽出ルール v0.2
- 共通：`{{field_id}}` があれば最優先でslot化
- docx：`＿＿＿`/`___`/`（　）`/`【　】`/`［　］`を含む段落・表セル、空欄セル＋見出し行をslot候補化
- xlsx：値が空・`＿`/`___`を含むセルで、同一行左セル or 同一列上セルに見出し文字列があるものをslot候補化
  - slot_id例：`docx_p3_t2_r1c2` / `xlsx_Sheet1_B5`
  - label例：左/上セルの文字列をそのまま保持（UI表示用）

## マッピング例
```json
{"xlsx_Sheet1_B5": "guidance_long_goal", "xlsx_Sheet1_B6": "short_goal_1"}
```

## 差し込み
- txt/docx：`{{field}}`置換＋slot位置への値挿入（docxは段落・表セル単位）
- xlsx：slotセルへ値を書込（書式保持、openpyxl）
- 未マッピングslot残存・必須欠落があれば出力ブロック＋理由返却
