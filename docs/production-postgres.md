# 本番Postgres移行手順書（v0.6）

## 状態
- コード対応済み：`DATABASE_URL=postgresql://…` で自動切替（`backend/app/db.py`）
- 確認済み：SQLiteモードの全テスト16件、同一コードパスのsmoke（`backend/check_postgres.py`）、SQLのPG互換レビュー（`?`→`%s`変換、SERIAL、DOUBLE PRECISION、複文分割）
- 未確認：Postgres実サーバでの接続（本PCにDocker・PGサーバなしのため）。サーバ側で下記を実行すること

## サーバ側手順
```bash
docker compose up -d db
export DATABASE_URL=postgresql://app:app@db:5432/plans
pip install -r backend/requirements.txt
python backend/check_postgres.py   # ALL OKを確認
python backend/seed_niigata.py
python -m pytest backend/tests -q
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

## 注意
- `backend/data/*.db` は本番で使わない（Postgres利用時は無視される）
- バックアップは `pg_dump` を定期実行し、暗号化保管すること
- LLMのAPIキーは `backend/.env`（`.env.example`参照）に保持し、リポジトリに含めないこと
- 初期パスワード（admin123等）は初回起動時に必ず変更すること
