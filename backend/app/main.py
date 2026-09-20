"""FastAPI backend v0.9。起動: python -m uvicorn app.main:app --app-dir backend --reload"""
from __future__ import annotations
import json
import os
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from app import config as _config
_config.load_dotenv()

from app import db, auth
from app.core import llm
from app.routers import auth_router, plans, templates, ai, handover
from app.routers.plans import validate_plan

db.init_db()
auth.seed()

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

app = FastAPI(title="支援・指導計画 API v0.9")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router.router)
app.include_router(plans.router)
app.include_router(templates.router)
app.include_router(ai.router)
app.include_router(handover.router)


@app.get("/api/health")
def health():
    import shutil
    info: dict = {"ok": True, "llm_provider": llm.PROVIDER, "db": "postgres" if db.USE_PG else "sqlite"}
    try:
        with db.conn() as c:
            info["users"] = dict(c.execute("SELECT COUNT(*) AS n FROM users").fetchone())["n"]
            info["plans"] = dict(c.execute("SELECT COUNT(*) AS n FROM plans").fetchone())["n"]
    except Exception as e:  # noqa: BLE001
        info["ok"] = False
        info["db_error"] = str(e)[:200]
    try:
        from app import pdfgen
        pdfgen.font_path()
        info["pdf_font"] = True
    except Exception:
        info["pdf_font"] = False
    try:
        du = shutil.disk_usage(str(db.DATA))
        info["disk_free_mb"] = du.free // (1024 * 1024)
    except Exception:
        pass
    return info


@app.get("/api/audit")
def audit_list(limit: int = 200, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager")
    return db.audit_list(limit)


@app.get("/api/audit/export")
def audit_export(user: dict = Depends(auth.current_user)):
    import csv as _csv
    import io as _io
    from fastapi.responses import Response as _Resp
    auth.require_role(user, "admin", "manager")
    rows = db.audit_list(5000)
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["id", "日時", "ユーザ", "操作", "対象", "詳細"])
    import datetime as _dt
    for r in rows:
        w.writerow([r["id"], _dt.datetime.fromtimestamp(r["at"]).strftime("%Y-%m-%d %H:%M:%S"),
                    r["username"], r["action"], r["target"], r["detail"]])
    payload = "\ufeff".encode("utf-8") + buf.getvalue().encode("utf-8")
    db.audit(user["username"], "audit.export", "", f"{len(rows)}件")
    return _Resp(content=payload, media_type="text/csv",
                 headers={"Content-Disposition": "attachment; filename=audit.csv"})


@app.get("/api/stats/summary")
def stats_summary(user: dict = Depends(auth.current_user)):
    """ダッシュボード用：状態別件数・検証ブロック件数・最近更新。"""
    with db.conn() as c:
        if user["role"] in ("admin", "manager"):
            rows = c.execute("SELECT * FROM plans ORDER BY updated_at DESC LIMIT 500").fetchall()
        else:
            rows = c.execute("SELECT * FROM plans WHERE created_by=? OR school=? ORDER BY updated_at DESC LIMIT 500",
                             (user["username"], user.get("school", ""))).fetchall()
        items = [dict(r) for r in rows]
    by_status: dict = {}
    blocked = 0
    for p in items:
        by_status[p.get("status", "draft")] = by_status.get(p.get("status", "draft"), 0) + 1
        try:
            data = json.loads(p.get("data_json") or "{}")
            if validate_plan(data)["blocked"]:
                blocked += 1
        except Exception:
            blocked += 1
    recent = [{"id": p["id"], "child_code": p["child_code"], "grade": p["grade"],
               "status": p["status"], "updated_at": p["updated_at"]} for p in items[:10]]
    return {"total": len(items), "by_status": by_status, "blocked": blocked, "recent": recent}
