"""DB基盤 v0.4：既定SQLite（標準ライブラリのみ）。DATABASE_URL=postgresql://…でPostgres。

Postgres利用時は `pip install psycopg[binary]` が必要（requirements.txtに含む）。
"""
from __future__ import annotations
import os
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("DB_PATH", str(DATA / "app.db")))
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgresql")

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
  salt TEXT NOT NULL, role TEXT NOT NULL, school TEXT DEFAULT '',
  totp_secret TEXT DEFAULT '', must_change_pw INTEGER DEFAULT 0, ai_consent INTEGER DEFAULT 0, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS plans(
  id TEXT PRIMARY KEY, child_code TEXT NOT NULL, school TEXT DEFAULT '',
  grade TEXT DEFAULT '', class_type TEXT DEFAULT '', status TEXT DEFAULT 'draft',
  data_json TEXT NOT NULL DEFAULT '{}', created_by TEXT DEFAULT '',
  updated_by TEXT DEFAULT '', guardian_confirmed INTEGER DEFAULT 0,
  guardian_date TEXT DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS templates(
  id TEXT PRIMARY KEY, filename TEXT DEFAULT '', suffix TEXT DEFAULT '',
  label TEXT DEFAULT '', mapping_json TEXT DEFAULT '{}',
  created_by TEXT DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, username TEXT DEFAULT '',
  action TEXT NOT NULL, target TEXT DEFAULT '', detail TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS comments(
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, author TEXT NOT NULL,
  body TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS records(
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, author TEXT NOT NULL,
  date TEXT NOT NULL DEFAULT '', goal_ref TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS shares(
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, token TEXT UNIQUE NOT NULL,
  expires_at REAL NOT NULL, revoked INTEGER DEFAULT 0,
  created_by TEXT DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS consents(
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, consenter TEXT NOT NULL,
  method TEXT NOT NULL DEFAULT '', plan_hash TEXT NOT NULL DEFAULT '',
  agreed_at REAL NOT NULL, ip TEXT DEFAULT '', created_by TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS versions(
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, version_no INTEGER NOT NULL,
  data_json TEXT NOT NULL DEFAULT '{}', created_by TEXT DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS snippets(
  id TEXT PRIMARY KEY, category TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '', created_by TEXT DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS api_keys(
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, key_hash TEXT NOT NULL,
  label TEXT DEFAULT '', revoked INTEGER DEFAULT 0, created_at REAL NOT NULL);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
  salt TEXT NOT NULL, role TEXT NOT NULL, school TEXT DEFAULT '',
  totp_secret TEXT DEFAULT '', must_change_pw INTEGER DEFAULT 0, ai_consent INTEGER DEFAULT 0, created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS plans(
  id TEXT PRIMARY KEY, child_code TEXT NOT NULL, school TEXT DEFAULT '',
  grade TEXT DEFAULT '', class_type TEXT DEFAULT '', status TEXT DEFAULT 'draft',
  data_json TEXT NOT NULL DEFAULT '{}', created_by TEXT DEFAULT '',
  updated_by TEXT DEFAULT '', guardian_confirmed INTEGER DEFAULT 0,
  guardian_date TEXT DEFAULT '', created_at DOUBLE PRECISION NOT NULL,
  updated_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS templates(
  id TEXT PRIMARY KEY, filename TEXT DEFAULT '', suffix TEXT DEFAULT '',
  label TEXT DEFAULT '', mapping_json TEXT DEFAULT '{}',
  created_by TEXT DEFAULT '', created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS audit(
  id SERIAL PRIMARY KEY, at DOUBLE PRECISION NOT NULL, username TEXT DEFAULT '',
  action TEXT NOT NULL, target TEXT DEFAULT '', detail TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS comments(
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, author TEXT NOT NULL,
  body TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS records(
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, author TEXT NOT NULL,
  date TEXT NOT NULL DEFAULT '', goal_ref TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS shares(
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, token TEXT UNIQUE NOT NULL,
  expires_at DOUBLE PRECISION NOT NULL, revoked INTEGER DEFAULT 0,
  created_by TEXT DEFAULT '', created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS consents(
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, consenter TEXT NOT NULL,
  method TEXT NOT NULL DEFAULT '', plan_hash TEXT NOT NULL DEFAULT '',
  agreed_at DOUBLE PRECISION NOT NULL, ip TEXT DEFAULT '', created_by TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS versions(
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, version_no INTEGER NOT NULL,
  data_json TEXT NOT NULL DEFAULT '{}', created_by TEXT DEFAULT '', created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS snippets(
  id TEXT PRIMARY KEY, category TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '', created_by TEXT DEFAULT '', created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS api_keys(
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, key_hash TEXT NOT NULL,
  label TEXT DEFAULT '', revoked INTEGER DEFAULT 0, created_at DOUBLE PRECISION NOT NULL);
"""


def q(sql: str) -> str:
    """SQLite(?)→Postgres(%s)のプレースホルダ変換。"""
    return sql.replace("?", "%s") if USE_PG else sql


class _Conn:
    """sqlite3/psycopgの差を吸収する薄いラッパ。dict行・with対応。"""

    def __init__(self, raw):
        self._r = raw

    def execute(self, sql, params=()):
        cur = self._r.cursor()
        cur.execute(q(sql), params)
        return _Cur(cur)

    def executescript(self, sql):
        if USE_PG:
            # psycopg3は複文execute不可のため分割実行
            for stmt in (s.strip() for s in sql.split(";")):
                if stmt:
                    self._r.execute(stmt)
        else:
            self._r.executescript(sql)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        try:
            self._r.commit()
        finally:
            self._r.close()


class _Cur:
    def __init__(self, cur):
        self._c = cur
        try:
            names = [d[0] for d in (cur.description or [])]
        except Exception:
            names = []
        self._names = names

    def fetchone(self):
        r = self._c.fetchone()
        if r is None:
            return None
        if isinstance(r, dict):
            return r
        try:
            return dict(zip(self._names, r))
        except Exception:
            return r

    def fetchall(self):
        rows = self._c.fetchall()
        out = []
        for r in rows:
            if isinstance(r, dict):
                out.append(r)
            else:
                try:
                    out.append(dict(zip(self._names, r)))
                except Exception:
                    out.append(r)
        return out


def conn() -> _Conn:
    if USE_PG:
        import psycopg
        from psycopg.rows import dict_row
        return _Conn(psycopg.connect(DATABASE_URL, row_factory=dict_row))
    import sqlite3
    raw = sqlite3.connect(str(DB_PATH), timeout=30)
    raw.row_factory = sqlite3.Row
    return _Conn(raw)


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA_PG if USE_PG else SCHEMA_SQLITE)
    # 既存DBへの追加カラム（マイグレーション）
    with conn() as c:
        for ddl in ("ALTER TABLE users ADD COLUMN totp_secret TEXT DEFAULT ''",
                    "ALTER TABLE users ADD COLUMN must_change_pw INTEGER DEFAULT 0",
                    "ALTER TABLE users ADD COLUMN ai_consent INTEGER DEFAULT 0"):
            try:
                c.execute(ddl)
            except Exception:
                pass


def audit(username: str, action: str, target: str = "", detail: str = "") -> None:
    with conn() as c:
        c.execute("INSERT INTO audit(at,username,action,target,detail) VALUES(?,?,?,?,?)",
                  (time.time(), username or "", action, target or "", (detail or "")[:2000]))


def audit_list(limit: int = 200) -> list:
    with conn() as c:
        rows = c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
