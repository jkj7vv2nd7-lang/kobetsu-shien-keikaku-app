# アーキテクチャ設計（v0.1）

## 全体構成（クラウドWebアプリ）

```
[Browser] --TLS--> [Web App (Next.js想定)] --> [API (Python/FastAPI想定)]
                                                    |-- [DB (Postgres, 暗号化, JPリージョン)]
                                                    |-- [Template Engine]
                                                    |-- [AI Gateway (匿名化 → LLM → 検証)]
                                                    |-- [Audit Log / Storage (PDF出力物)]
```

現リポジトリの `src/core/` は、このうちAI前処理・チェック・差し込みの
ドメインロジックをPython標準ライブラリのみで先行実装したもの。
将来のNext.js/FastAPI化でもそのまま移植可能。

## テンプレート＋差し込み方式
- `templates/mext/` に文科省参考様式相当のプレースホルダ付テンプレートを配置
- 自治体様式は xlsx/docx をアップロード → `{{field_id}}` マーカー付与 →
  `src/schema/field_master.json` の共通フィールドIDにマッピング
- 共通フィールドID例：`child_code, grade, strengths, needs, long_goal, short_goal_1..3, supports, eval_plan, guardian_wish, conference_memo`
- 出力：プレビュー（HTML）→ PDF（印刷用）→ 原本docx/xlsx保持。年度・自治体・学校種でバージョン管理。
- 差し込み時は必須項目・文字数・日付を厳密チェックし、欠落があれば印刷ブロック＋修正指示。

## AI Gateway（匿名化が前提）
1. 入力PIIを `anonymize.py` で仮名化（氏名→【児童A】、学校→【学校X】等）。対応表はDB/メモリ内のみ、LLM送信対象外。
2. 仮名化文のみをLLMへ送信（プロンプトに個人特定情報の復元禁止を明示）。
3. 戻り文を `checks.py` で再検証（差別的・断定的医療表現・曖昧語・目標不整合）。
4. 教員が必ず承認・編集して確定。AI文の自動確定はしない。利用履歴を監査ログに記録。

## 厳密チェック層
- 構造チェック：必須・文字数・選択肢・日付前後関係
- 表現チェック：NGリスト（障害を否定的に断定する語等）＋曖昧語（「頑張る」「見守る」のみ等）検出
- 整合性チェック：支援計画の長期目標 ↔ 指導計画の短期目標・手立て・評価方法の対応関係
- 承認フロー：作成者 → 学年主任/管理職の二重チェック → 保護者確認フラグ

## セキュリティ
詳細は `docs/security.md` 参照。原則：
RBAC / スコープ分離 / 暗号化 / 監査 / PII最小化 / 削除ポリシー / バックアップ。
AI送信前匿名化はサーバ側で強制し、クライアント側回避を不可にする。
