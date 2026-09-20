# SSO連携メモ（v0.7）

## 対応方式：プロキシ経由ヘッダSSO
学校のSSOゲートウェイ（Microsoft Entra Application Proxy、Google Workspace経由等）が
利用者IDをHTTPヘッダで付与する構成に対応。`GET /api/auth/sso/me` がトークンを発行する。

## 設定（`backend/.env`）
- `SSO_TRUSTED_HEADER=X-Remote-User`（未設定時はSSO無効）
- `SSO_TRUSTED_NETWORKS=10.0.0.0/8,127.0.0.1/32`（信頼する送信元のみ。`*`は閉域テスト用）
- `SSO_DEFAULT_ROLE=teacher`（初回自動プロビジョニング時のロール）
- `SSO_ADMINS=admin1,admin2`（管理者にするID）

## 注意
- ゲートウェイ側で必ず利用者認証＋ヘッダ付与・偽造防止（mTLS/共有シークレット等）を設定すること
- アプリは送信元IPの検証のみ行う。直接公開時は前段プロキシ以外からの到達を遮断すること
- 初回ログイン時にユーザ自動作成（パスワードはランダム）。ロール変更は管理者がDBで調整
- 本格OIDC（認可コードフロー）は将来対応。IdP導入時に `auth.py` の差し替え口を利用する
