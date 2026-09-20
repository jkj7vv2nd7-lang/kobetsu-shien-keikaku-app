# 個別支援・指導計画作成支援アプリ v0.10

特別支援学級・特別支援学校で作成する**個別の教育支援計画・個別の指導計画**を、
AIの支援を受けながら作成・印刷できるWebアプリです。
文科省参考様式を起点に、各自治体の様式（Excel/Word）を取り込んで差し込み印刷できます。

> 先生向けの詳しい操作手順は **[MANUAL.md](MANUAL.md)** をご覧ください。

## 特長
- 自治体様式の取込→自動映射→プレビュー→Excel/PDF出力（新潟県様式の映射済み）
- AI支援（匿名化が前提）：文案下書き、欄ごとの推敲、表現チェック、引継ぎ要約、糊しろ提案
- やさしい日本語チェック（保護者に伝わる文章に）
- 提出→承認フロー、支援会議メモ、引継ぎ出力（同意必須）、監査ログ
- 新潟県教委ハンドブック準拠（目標の具体性・個人内評価・糊しろ・同意管理）

## 構成
- `backend/`：FastAPI（Python）
- `frontend/`：Next.js（TypeScript）
- `src/`：検査・匿名化・差し込みのコアロジック
- `templates/`：文科省試作様式・新潟県様式＋映射
- `MANUAL.md`：操作マニュアル、`docs/`：設計・運用・公開手順

## すぐ試す（ローカル）
```powershell
pip install -r backend\requirements.txt
python backend\seed_niigata.py
python -m uvicorn app.main:app --app-dir backend --reload
# 別ターミナル
cd frontend; npm install; npm run dev
```
`http://localhost:3000` を開き `teacher` / `teacher123` でログイン（初回はPW変更）。
公開手順は [docs/DEPLOY.md](docs/DEPLOY.md) を参照。

## セキュリティの考え方
- 氏名・住所・連絡先はLLMに送信しません（印刷専用・送信前検査あり）
- AI文案の自動確定なし、保護者確認が必須、操作は監査記録
- 初期パスワード・2段階認証・バックアップは `docs/operations.md` に従って設定してください
- 試験公開であり、実児童データでの利用前に所属の情報管理規定の確認が必要です

## 技術スタック
Python 3.12+ / FastAPI / SQLite（Postgres切替可）/ Next.js 15 / React 19 / Docker
