# 公開手順書（GitHub＋Vercel・試験公開用）

## 前提
- GitHubアカウント、Vercelアカウント
- バックエンド（FastAPI）の置き場所（下記いずれか）
  - A案：学内・自宅サーバ／VPSでDocker起動（推奨・データ国内管理）
  - B案：Render等のPaaSにDockerデプロイ

> 注意：Vercelはフロントエンド（Next.js）専用です。バックエンドは別ホストが必要です。
> またSQLiteはサーバ再起動で消える場合があるため、試験後にPostgres移行（`docs/production-postgres.md`）を検討してください。

## 1. GitHubへプッシュ
```powershell
cd "C:\Users\masan\開発中のアプリ\個別支援＿個別指導計画作成"
git add -A
git status --short   # .env / *.db / node_modules / .next が含まれていないことを確認
git commit -m "v0.9 試験公開：操作マニュアル同梱"
git branch -M main
git remote add origin https://github.com/<ユーザ>/<リポジトリ>.git
git push -u origin main
```
確認ポイント：
- `backend/.env` が存在してもコミット対象外（`.gitignore`済み）
- `backend/data/*.db`、`backend/backups/` は対象外
- 初期パスワードは周知の默认值のため、公開前に `docs/operations.md` の手順で変更方針を決めること

## 2. バックエンドの起動（A案：VPS等でDocker）
```bash
git clone https://github.com/<ユーザ>/<リポジトリ>.git
cd <リポジトリ>
cp backend/.env.example backend/.env   # LLM_PROVIDER=mock のままでOK
docker compose up -d --build
python backend/seed_niigata.py  # 別途：コンテナ外からAPI経由でも可
```
- API疎通：`http://<サーバ>:8000/api/health` が `{"ok": true, ...}` を返すこと
- HTTPS化はリバースプロキシ（nginx等）＋証明書で行うこと（試験公開の必須条件）

## 3. フロントエンドをVercelに公開
1. Vercelで「Add New Project」→GitHubリポジトリを選択
2. Root Directoryに `frontend` を指定（FrameworkはNext.js自動判定）
3. Environment Variablesに `NEXT_PUBLIC_API_URL=https://<バックエンドの公開URL>` を設定
4. Deploy → 発行URL（例：`https://○○.vercel.app`）を開く
5. ログイン画面が出れば成功。`teacher` / `teacher123` で試用し、すぐパスワード変更すること

## 4. 公開後の必須作業
- [ ] 初期パスワードの全変更、管理職のMFA有効化
- [ ] HTTPS必須（HTTPのまま個人情報を扱わない）
- [ ] バックアップ先の確保（`python backend/backup.py backup`）
- [ ] 試験利用の旨を利用者に明示（実データ利用は情報管理規定の確認後に）
