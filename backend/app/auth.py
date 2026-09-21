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

# 簡易運用モード（委員会許可など組織の承認を前提に手間を省く）。既定OFF
SIMPLE_MODE = os.getenv("SIMPLE_MODE", "0") == "1"
if SIMPLE_MODE:
    TOKEN_TTL = 60 * 60 * 24 * 30  # 30日

# 簡易レート制限（メモリ内・単一プロセス用）
_RATE: dict = {}


def limited(key: str, n: int = 10, window: int = 300) -> None:
    from fastapi import HTTPException as _HE
    now = time.time()
    lst = [t for t in _RATE.get(key, []) if now - t < window]
    if len(lst) >= n:
        raise _HE(429, "試行回数超過。しばらくして再試行してください。")
    lst.append(now)
    _RATE[key] = lst
    if len(_RATE) > 10000:
        _RATE.clear()


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
    key = ""
    if authorization and authorization.lower().startswith("bearer "):
        key = authorization.split(None, 1)[1]
    if not key:
        raise HTTPException(status_code=401, detail="要ログイン（Bearer token）")
    # 1) セッショントークン
    with db.conn() as c:
        s = c.execute("SELECT * FROM sessions WHERE token=?", (key,)).fetchone()
        if s and s["expires_at"] >= time.time():
            u = c.execute("SELECT * FROM users WHERE id=?", (s["user_id"],)).fetchone()
            if u:
                return dict(u)
        # 2) APIキー（sk-...）
        if key.startswith("sk-"):
            import hashlib as _hl
            h = _hl.sha256(key.encode()).hexdigest()
            k = c.execute("SELECT * FROM api_keys WHERE key_hash=? AND revoked=0", (h,)).fetchone()
            if k:
                u = c.execute("SELECT * FROM users WHERE id=?", (dict(k)["user_id"],)).fetchone()
                if u:
                    return dict(u)
    raise HTTPException(status_code=401, detail="トークン無効・期限切れ")


def issue_api_key(user_id: str, label: str = "") -> tuple:
    """APIキー発行。平文はこの戻り値でのみ参照可（DBはハッシュ保存）。"""
    import hashlib as _hl
    raw = "sk-" + secrets.token_hex(24)
    h = _hl.sha256(raw.encode()).hexdigest()
    with db.conn() as c:
        c.execute("INSERT INTO api_keys(id,user_id,key_hash,label,revoked,created_at) VALUES(?,?,?,?,?,?)",
                  ("k" + secrets.token_hex(6), user_id, h, label[:100], 0, time.time()))
    return raw


def require_role(user: dict, *allowed: str) -> None:
    if user["role"] not in allowed and user["role"] != "admin":
        raise HTTPException(status_code=403, detail=f"権限不足（必要: {allowed}）")
