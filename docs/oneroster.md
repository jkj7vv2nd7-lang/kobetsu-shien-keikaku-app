# OneRoster連携メモ（v0.12・users.csv取込）

## 対応範囲
`POST /api/admin/oneroster` にOneRoster 1.1 `users.csv` の内容をJSON `{csv: "..."}` で送信。
- 教職員（role=teacher/administrator）→ アプリユーザ自動作成（初回PWはランダム、管理者が再設定またはSSO利用）
- 児童生徒（role=student）→ 計画下書き自動作成（管理番号=sourcedId、学年=grades）
- 氏名列（givenName/familyName）は**保存しない**（個人情報最小化。必要時は計画の氏名欄に手入力）
- 上限：CSV 2MB・1000件、監査記録あり

## 対応列
sourcedId（必須）, enabledUser, givenName, familyName, role [teacher|student|administrator], grades, orgSourcedIds

## 未対応（将来）
- classes.csv / enrollments.csv（学級・履修の紐付け）
- demographics（性別・生年月日等の属性連携）
- rostering API（REST差分同期）
- APPLIC相互接続確認（正式申請・テストが別途必要。`docs/applic-checklist.md`参照）
