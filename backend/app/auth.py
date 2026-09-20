"""認証 v0.4：pbkdf2＋トークンセッション＋TOTP(MFA・標準ライブラリのみ)。将来OIDC/SSO差し替え口あり。"""
from __future__ import annotations
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
import uuid
from fastapi import Header, HTTPException

from app import db

ROLES = ("admin", "manager", "teacher", "viewer")
TOKEN_TTL = 60 * 60 * 12


# ---------- TOTP (RFC 6238, SHA1, 30秒, 6桁) ----------

def gen_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_code(secret: str, at: float | None = None, step: int = 30) -> str:
    pad = "=" * (-len(secret) % 8)
    key = base64.b32decode(secret + pad)
    ctr = int((time.time() if at is None else at) // step)
    mac = hmac.new(key, struct.pack(">Q", ctr), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    num = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{num:06d}"


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    code = (code or "").strip()
    if not (secret and len(code) == 6 and code.isdigit()):
        return False
    now = time.time()
    return any(hmac.compare_digest(totp_code(secret, now + d * 30), code) for d in range(-window, window + 1))


def otpauth_url(username: str, secret: str, issuer: str = "支援計画アプリ") -> str:
    from urllib.parse import quote
    return f"otpauth://totp/{quote(issuer)}:{quote(username)}?secret={secret}&issuer={quote(issuer)}"


def _hash(pw: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 200_000).hex()


def set_password(user_id: str, new_password: str) -> None:
    salt = os.urandom(16).hex()
    with db.conn() as c:
        c.execute("UPDATE users SET pw_hash=?,salt=?,must_change_pw=0 WHERE id=?",
                  (_hash(new_password, salt), salt, user_id))


def ensure_user(username: str, password: str, role: str, school: str = "") -> dict:
    db.init_db()
    with db.conn() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if row:
            return dict(row)
        salt = os.urandom(16).hex()
        uid = uuid.uuid4().hex[:12]
        c.execute("INSERT INTO users(id,username,pw_hash,salt,role,school,totp_secret,must_change_pw,created_at) VALUES(?,?,?,?,?,?,?,1,?)",
                  (uid, username, _hash(password, salt), salt, role, school, "", time.time()))
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(row)


def seed() -> None:
    ensure_user("admin", "admin123", "admin", "全校")
    ensure_user("manager", "manager123", "manager", "全校")
    ensure_user("teacher", "teacher123", "teacher", "3年1組")
    ensure_user("viewer", "viewer123", "viewer", "")


def verify(username: str, password: str) -> dict | None:
    with db.conn() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            return None
        if _hash(password, row["salt"]) != row["pw_hash"]:
            return None
        return dict(row)


def issue_token(user_id: str) -> str:
    tok = secrets.token_hex(24)
    with db.conn() as c:
        c.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)",
                  (tok, user_id, time.time() + TOKEN_TTL))
        # 期限切れセッションの掃除（ついで）
        try:
            c.execute("DELETE FROM sessions WHERE expires_at<?", (time.time(),))
        except Exception:
            pass
    return tok


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="要ログイン（Bearer token）")
    tok = authorization.split(None, 1)[1]
    with db.conn() as c:
        s = c.execute("SELECT * FROM sessions WHERE token=?", (tok,)).fetchone()
        if not s or s["expires_at"] < time.time():
            raise HTTPException(status_code=401, detail="トークン無効・期限切れ")
        u = c.execute("SELECT * FROM users WHERE id=?", (s["user_id"],)).fetchone()
        if not u:
            raise HTTPException(status_code=401, detail="ユーザ不明")
        return dict(u)


def require_role(user: dict, *allowed: str) -> None:
    if user["role"] not in allowed and user["role"] != "admin":
        raise HTTPException(status_code=403, detail=f"権限不足（必要: {allowed}）")
