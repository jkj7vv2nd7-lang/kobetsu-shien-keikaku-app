"""Postgres移行の実機確認スクリプト。サーバ側で実行:
   DATABASE_URL=postgresql://app:app@db:5432/plans python backend/check_postgres.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config as _config  # noqa: E402
_config.load_dotenv()  # noqa: E402

url = os.getenv("DATABASE_URL", "")
print("DATABASE_URL:", (url.split("@")[-1] if "@" in url else "(未設定・SQLiteモード)"))

from app import db, auth  # noqa: E402

print("USE_PG:", db.USE_PG)
db.init_db()
print("init_db: OK")
auth.seed()
print("seed: OK")

with db.conn() as c:
    n = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()
    print("users:", dict(n))
    import uuid as _uuid
    sid = "smoke_" + _uuid.uuid4().hex[:8]
    c.execute("INSERT INTO plans(id,child_code,school,grade,class_type,status,data_json,created_by,updated_by,guardian_confirmed,guardian_date,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (sid, "S-1", "全校", "小4", "特別支援学級", "draft", "{}", "admin", "admin", 0, "", 1.0, 1.0))
    r = c.execute("SELECT id,child_code,status FROM plans WHERE id=?", (sid,)).fetchone()
    print("plan roundtrip:", dict(r))
    c.execute("DELETE FROM plans WHERE id=?", (sid,))
db.audit("smoke", "check_postgres", "", "ok")
print("audit:", db.audit_list(1)[0]["action"])
print("ALL OK")
