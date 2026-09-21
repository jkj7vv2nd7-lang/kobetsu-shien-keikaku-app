"""認証API v0.4（MFA対応）"""
import secrets
import time
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from app import auth, db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ログイン試行制限：5分間に10回まで（メモリ内・単一プロセス用）
LIMIT_N, LIMIT_WIN = 10, 300


def _limited(key: str) -> None:
    auth.limited(key, LIMIT_N, LIMIT_WIN)


class LoginBody(BaseModel):
    username: str
    password: str


class MfaBody(BaseModel):
    username: str = ""
    password: str = ""
    code: str = ""


@router.post("/seed")
def seed():
    auth.seed()
    return {"ok": True, "users": ["admin", "manager", "teacher", "viewer"]}


class SignupBody(BaseModel):
    username: str = ""
    password: str = ""
    school: str = ""


@router.post("/signup")
def signup(body: SignupBody, req: Request):
    """自己登録（担任権限）。委員会許可など組織承認がある場合の運用向け。"""
    import re as _re
    _limited(f"signup:{req.client.host if req.client else '?'}")
    uname = (body.username or "").strip()
    if not _re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", uname):
        raise HTTPException(400, "ユーザ名は半角英数・._- の3〜50字にしてください")
    if len(body.password) < 8 or len(body.password) > 200:
        raise HTTPException(400, "パスワードは8〜200字にしてください")
    with db.conn() as c:
        if c.execute("SELECT id FROM users WHERE username=?", (uname,)).fetchone():
            raise HTTPException(400, "そのユーザ名は使用済みです")
    u = auth.ensure_user(uname, body.password, "teacher", body.school.strip()[:100])
    tok = auth.issue_token(u["id"])
    db.audit(uname, "auth.signup", "", "")
    return {"token": tok, "username": uname, "role": "teacher"}


@router.post("/login")
def login(body: LoginBody, req: Request):
    if len(body.username) > 200 or len(body.password) > 200:
        raise HTTPException(400, "入力が長すぎます")
    _limited(f"login:{req.client.host if req.client else '?'}:{body.username}")
    u = auth.verify(body.username, body.password)
    if not u:
        return {"error": "認証失敗"}
    if u.get("totp_secret"):
        return {"mfa_required": True, "username": u["username"]}
    tok = auth.issue_token(u["id"])
    db.audit(u["username"], "auth.login", "", "")
    return {"token": tok, "username": u["username"], "role": u["role"], "school": u.get("school", ""),
            "must_change_pw": (False if auth.SIMPLE_MODE else bool(u.get("must_change_pw")))}


@router.post("/mfa/login")
def mfa_login(body: MfaBody, req: Request):
    _limited(f"mfa:{req.client.host if req.client else '?'}:{body.username}")
    u = auth.verify(body.username, body.password)
    if not u or not u.get("totp_secret"):
        return {"error": "認証失敗"}
    if not auth.verify_totp(u["totp_secret"], body.code):
        db.audit(body.username, "auth.mfa_fail", "", "")
        return {"error": "確認コード不一致"}
    tok = auth.issue_token(u["id"])
    db.audit(u["username"], "auth.login_mfa", "", "")
    return {"token": tok, "username": u["username"], "role": u["role"], "school": u.get("school", ""),
            "must_change_pw": (False if auth.SIMPLE_MODE else bool(u.get("must_change_pw")))}


@router.post("/mfa/setup")
def mfa_setup(user: dict = Depends(auth.current_user)):
    secret = auth.gen_totp_secret()
    with db.conn() as c:
        c.execute("UPDATE users SET totp_secret=? WHERE id=?", (secret, user["id"]))
    db.audit(user["username"], "auth.mfa_setup", "", "")
    return {"secret": secret, "otpauth_url": auth.otpauth_url(user["username"], secret),
            "note": "認証アプリで手動入力またはURL登録し、確認コードで有効化してください"}


@router.post("/mfa/verify")
def mfa_verify(body: MfaBody, user: dict = Depends(auth.current_user)):
    with db.conn() as c:
        r = c.execute("SELECT totp_secret FROM users WHERE id=?", (user["id"],)).fetchone()
        ok = auth.verify_totp(dict(r).get("totp_secret", ""), body.code)
    db.audit(user["username"], "auth.mfa_verify", "", "ok" if ok else "ng")
    return {"ok": ok}


@router.post("/mfa/disable")
def mfa_disable(body: MfaBody, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager")
    with db.conn() as c:
        c.execute("UPDATE users SET totp_secret='' WHERE username=?", (body.username,))
    db.audit(user["username"], "auth.mfa_disable", body.username, "")
    return {"ok": True}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), user: dict = Depends(auth.current_user)):
    if authorization and authorization.lower().startswith("bearer "):
        tok = authorization.split(None, 1)[1]
        with db.conn() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (tok,))
    db.audit(user["username"], "auth.logout", "", "")
    return {"ok": True}


class PwBody(BaseModel):
    old_password: str = ""
    new_password: str = ""


@router.post("/password")
def change_password(body: PwBody, user: dict = Depends(auth.current_user)):
    if len(body.new_password) < 8:
        raise HTTPException(400, "新しいパスワードは8文字以上にしてください")
    import hashlib
    with db.conn() as c:
        r = c.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        d = dict(r)
        chk = hashlib.pbkdf2_hmac("sha256", body.old_password.encode("utf-8"),
                                  bytes.fromhex(d["salt"]), 200_000).hex()
        if chk != d["pw_hash"]:
            raise HTTPException(400, "現在のパスワードが違います")
    auth.set_password(user["id"], body.new_password)
    db.audit(user["username"], "auth.password", "", "")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(auth.current_user)):
    return {"username": user["username"], "role": user["role"], "school": user.get("school", ""),
            "mfa": bool(user.get("totp_secret")),
            "must_change_pw": (False if auth.SIMPLE_MODE else bool(user.get("must_change_pw"))),
            "ai_consent": bool(user.get("ai_consent")),
            "simple_mode": auth.SIMPLE_MODE}


class ConsentAiBody(BaseModel):
    agree: bool = False


@router.post("/ai-consent")
def ai_consent(body: ConsentAiBody, user: dict = Depends(auth.current_user)):
    """生成AI利用の同意記録（文科省ガイドライン準拠の運用）。"""
    with db.conn() as c:
        c.execute("UPDATE users SET ai_consent=? WHERE id=?", (1 if body.agree else 0, user["id"]))
    db.audit(user["username"], "auth.ai_consent", "", "agree" if body.agree else "withdraw")
    return {"ok": True, "ai_consent": bool(body.agree)}


@router.get("/sso/me")
def sso_me(req: Request):
    """プロキシ経由SSO（ヘッダ信頼・自動プロビジョニング）。

    学校のSSOゲートウェイ（Entra Application Proxy等）が利用者IDを
    ヘッダ付与する構成用。.env設定例：
      SSO_TRUSTED_HEADER=X-Remote-User
      SSO_TRUSTED_NETWORKS=10.0.0.0/8,127.0.0.1/32
      SSO_DEFAULT_ROLE=teacher
      SSO_ADMINS=admin1,admin2
    """
    import ipaddress
    import os as _os
    header = _os.getenv("SSO_TRUSTED_HEADER", "")
    if not header:
        raise HTTPException(403, "SSO未設定")
    login_id = (req.headers.get(header, "") or req.headers.get(header.lower(), "")).strip()
    if not login_id:
        raise HTTPException(401, "SSOヘッダなし")
    nets = [n.strip() for n in _os.getenv("SSO_TRUSTED_NETWORKS", "127.0.0.1/32").split(",") if n.strip()]
    host = req.client.host if req.client else ""
    trusted = "*" in nets
    if not trusted:
        try:
            ip = ipaddress.ip_address(host)
            trusted = any(ip in ipaddress.ip_network(n, strict=False) for n in nets)
        except ValueError:
            trusted = False
    if not trusted:
        raise HTTPException(403, "信頼されない経路からのSSO")
    admins = [a.strip() for a in _os.getenv("SSO_ADMINS", "").split(",") if a.strip()]
    role = "admin" if login_id in admins else _os.getenv("SSO_DEFAULT_ROLE", "teacher")
    if role not in auth.ROLES:
        role = "teacher"
    with db.conn() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (login_id,)).fetchone()
        if not row:
            u = auth.ensure_user(login_id, secrets.token_hex(16), role, "")
            db.audit(login_id, "auth.sso_provision", "", role)
        else:
            u = dict(row)
    tok = auth.issue_token(u["id"])
    db.audit(u["username"], "auth.login_sso", "", "")
    return {"token": tok, "username": u["username"], "role": u["role"]}


class KeyBody(BaseModel):
    username: str = ""
    label: str = ""


@router.get("/keys")
def list_keys(user: dict = Depends(auth.current_user)):
    with db.conn() as c:
        if user["role"] in ("admin", "manager"):
            rows = c.execute("SELECT k.id,k.label,k.revoked,k.created_at,u.username FROM api_keys k JOIN users u ON u.id=k.user_id ORDER BY k.created_at DESC LIMIT 200").fetchall()
        else:
            rows = c.execute("SELECT k.id,k.label,k.revoked,k.created_at,u.username FROM api_keys k JOIN users u ON u.id=k.user_id WHERE u.id=? ORDER BY k.created_at DESC LIMIT 200", (user["id"],)).fetchall()
        return [dict(r) for r in rows]


@router.post("/keys")
def issue_key(body: KeyBody, user: dict = Depends(auth.current_user)):
    """使用者本人のAPIキーを発行（平文はこの応答でのみ表示）。管理職以外は自分自身の分のみ。"""
    if user["role"] not in ("admin", "manager") and body.username.strip() != user["username"]:
        raise HTTPException(403, "自分のキー以外は管理職が発行します")
    with db.conn() as c:
        r = c.execute("SELECT * FROM users WHERE username=?", (body.username.strip(),)).fetchone()
        if not r:
            raise HTTPException(404, "ユーザが見つかりません")
        raw = auth.issue_api_key(dict(r)["id"], body.label)
    db.audit(user["username"], "auth.key_issue", body.username.strip(), body.label[:50])
    return {"api_key": raw, "note": "この画面でのみ表示されます。控えてください"}


@router.delete("/keys/{kid}")
def revoke_key(kid: str, user: dict = Depends(auth.current_user)):
    with db.conn() as c:
        r = c.execute("SELECT user_id FROM api_keys WHERE id=?", (kid,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        if user["role"] not in ("admin", "manager") and dict(r)["user_id"] != user["id"]:
            raise HTTPException(403, "自分のキー以外は管理職が取消します")
        c.execute("UPDATE api_keys SET revoked=1 WHERE id=?", (kid,))
    db.audit(user["username"], "auth.key_revoke", kid, "")
    return {"ok": True}
