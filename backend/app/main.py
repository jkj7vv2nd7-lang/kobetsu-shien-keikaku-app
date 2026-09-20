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
try:
    from app.seed_data import seed_snippets
    seed_snippets()
except Exception:
    pass

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


@app.get("/api/share/{token}")
def public_share(token: str):
    """保護者共有リンク（ログイン不要・期限・取消・閲覧記録つき）。"""
    import re as _re
    import time as _t
    if not _re.fullmatch(r"[A-Za-z0-9_-]{1,64}", token or ""):
        from fastapi import HTTPException as _HE
        raise _HE(404, "not found")
    with db.conn() as c:
        s = c.execute("SELECT * FROM shares WHERE token=?", (token,)).fetchone()
        if not s:
            from fastapi import HTTPException as _HE
            raise _HE(404, "not found")
        s = dict(s)
        if s["revoked"] or s["expires_at"] < _t.time():
            from fastapi import HTTPException as _HE
            raise _HE(410, "リンクの期限切れ・取消済み")
        p = c.execute("SELECT child_code,grade,class_type,status,data_json FROM plans WHERE id=?", (s["plan_id"],)).fetchone()
        if not p:
            from fastapi import HTTPException as _HE
            raise _HE(404, "not found")
        p = dict(p)
    try:
        data = json.loads(p.pop("data_json") or "{}")
    except Exception:
        data = {}
    # PII項目は保護者本人の確認用に含める（リンク自体が合意形成の手段）
    db.audit("share", "share.view", s["plan_id"], token[:8] + "...")
    return {"child_code": p["child_code"], "grade": p["grade"], "class_type": p["class_type"],
            "status": p["status"], "data": data}


@app.get("/api/audit")
def audit_list(limit: int = 200, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager")
    return db.audit_list(limit)


@app.post("/api/admin/roster")
def roster_import(body: dict, user: dict = Depends(auth.current_user)):
    """名簿CSV相当の一括取込（年度当初用）。rows:[{child_code,grade,class_type,school}]。200件上限。"""
    auth.require_role(user, "admin", "manager")
    import time as _t
    import uuid as _uuid
    rows = (body or {}).get("rows", [])
    if not isinstance(rows, list) or len(rows) > 200:
        from fastapi import HTTPException as _HE
        raise _HE(400, "rowsは配列・200件以内にしてください")
    created, skipped = [], []
    with db.conn() as c:
        for r in rows:
            code = str((r or {}).get("child_code", "")).strip()[:100]
            if not code:
                skipped.append({"row": r, "reason": "管理番号なし"})
                continue
            if c.execute("SELECT id FROM plans WHERE child_code=?", (code,)).fetchone():
                skipped.append({"child_code": code, "reason": "既存"})
                continue
            pid = _uuid.uuid4().hex[:12]
            data = {"child_code": code, "grade": str(r.get("grade", ""))[:100],
                    "class_type": str(r.get("class_type", ""))[:100]}
            c.execute("""INSERT INTO plans(id,child_code,school,grade,class_type,status,data_json,
                         created_by,updated_by,guardian_confirmed,guardian_date,created_at,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (pid, code, str(r.get("school", user.get("school", "")))[:100],
                       data["grade"], data["class_type"], "draft",
                       json.dumps(data, ensure_ascii=False), user["username"], user["username"],
                       0, "", _t.time(), _t.time()))
            created.append({"id": pid, "child_code": code})
    db.audit(user["username"], "admin.roster", "", f"created={len(created)} skipped={len(skipped)}")
    return {"created": created, "skipped": skipped}


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
    from app.routers.handover import csv_safe as _csv_safe
    for r in rows:
        w.writerow([r["id"], _dt.datetime.fromtimestamp(r["at"]).strftime("%Y-%m-%d %H:%M:%S"),
                    _csv_safe(r["username"]), _csv_safe(r["action"]), _csv_safe(r["target"]), _csv_safe(r["detail"])])
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
    overdue: list = []
    due_soon: list = []
    no_date = 0
    import datetime as _dt
    today = _dt.date.today()
    for p in items:
        by_status[p.get("status", "draft")] = by_status.get(p.get("status", "draft"), 0) + 1
        try:
            data = json.loads(p.get("data_json") or "{}")
            if validate_plan(data)["blocked"]:
                blocked += 1
        except Exception:
            blocked += 1
            continue
        rv = str(data.get("next_review_date", "") or "").strip().replace("/", "-")
        if not rv:
            no_date += 1
            continue
        try:
            rd = _dt.date.fromisoformat(rv)
        except ValueError:
            continue
        info = {"id": p["id"], "child_code": p["child_code"], "next_review_date": rv}
        if rd < today:
            overdue.append(info)
        elif (rd - today).days <= 30:
            due_soon.append(info)
    recent = [{"id": p["id"], "child_code": p["child_code"], "grade": p["grade"],
               "status": p["status"], "updated_at": p["updated_at"]} for p in items[:10]]
    return {"total": len(items), "by_status": by_status, "blocked": blocked, "recent": recent,
            "overdue": overdue, "due_soon": due_soon, "no_review_date": no_date}


@app.post("/api/admin/oneroster")
def oneroster_import(body: dict, user: dict = Depends(auth.current_user)):
    """OneRoster users.csv 取込（教職員→ユーザ、児童生徒→計画下書き）。

    対応列：sourcedId, enabledUser, givenName, familyName, role [teacher|student|administrator],
    grades, orgSourcedIds。詳細は docs/oneroster.md。
    """
    import csv as _csv
    import io as _io
    import time as _t
    import uuid as _uuid
    auth.require_role(user, "admin", "manager")
    text = ((body or {}).get("csv", "") or "")
    if len(text) > 2 * 1024 * 1024:
        from fastapi import HTTPException as _HE
        raise _HE(400, "CSVは2MB以内にしてください")
    try:
        rows = list(_csv.DictReader(_io.StringIO(text)))
    except Exception as e:  # noqa: BLE001
        from fastapi import HTTPException as _HE
        raise _HE(400, f"CSV解析失敗: {str(e)[:200]}")
    if len(rows) > 1000:
        from fastapi import HTTPException as _HE
        raise _HE(400, "1000件以内にしてください")
    teachers, students, skipped = [], [], []
    with db.conn() as c:
        for i, r in enumerate(rows):
            sid = str(r.get("sourcedId", "") or "").strip()[:100]
            role = str(r.get("role", "") or "").strip().lower()
            if not sid or role not in ("teacher", "student", "administrator"):
                skipped.append({"line": i + 2, "reason": "sourcedId/role不正"})
                continue
            if str(r.get("enabledUser", "TRUE")).strip().upper() == "FALSE":
                skipped.append({"sourcedId": sid, "reason": "無効ユーザ"})
                continue
            if role in ("teacher", "administrator"):
                uname = sid
                app_role = "admin" if role == "administrator" else "teacher"
                if not c.execute("SELECT id FROM users WHERE username=?", (uname,)).fetchone():
                    from app import auth as _auth
                    _auth.ensure_user(uname, _uuid.uuid4().hex, app_role, "")
                    teachers.append(uname)
                else:
                    skipped.append({"sourcedId": sid, "reason": "既存ユーザ"})
            else:
                grades = str(r.get("grades", "") or "").strip()[:20]
                if not c.execute("SELECT id FROM plans WHERE child_code=?", (sid,)).fetchone():
                    pid = _uuid.uuid4().hex[:12]
                    data = {"child_code": sid, "grade": grades, "class_type": ""}
                    c.execute("""INSERT INTO plans(id,child_code,school,grade,class_type,status,data_json,
                                 created_by,updated_by,guardian_confirmed,guardian_date,created_at,updated_at)
                                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                              (pid, sid, "", grades, "", "draft", json.dumps(data, ensure_ascii=False),
                               user["username"], user["username"], 0, "", _t.time(), _t.time()))
                    students.append({"id": pid, "child_code": sid})
                else:
                    skipped.append({"sourcedId": sid, "reason": "既存計画"})
    db.audit(user["username"], "admin.oneroster", "", f"teachers={len(teachers)} students={len(students)} skipped={len(skipped)}")
    return {"teachers": teachers, "students": students, "skipped": skipped}


@app.get("/api/admin/archive")
def archive_all(user: dict = Depends(auth.current_user)):
    """全計画の一括出力（年度アーカイブ用・管理職のみ）。"""
    import io as _io
    import time as _t
    import zipfile as _zf
    from fastapi.responses import Response as _Resp
    auth.require_role(user, "admin", "manager")
    buf = _io.BytesIO()
    with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as zf:
        with db.conn() as c:
            plans = [dict(r) for r in c.execute("SELECT * FROM plans ORDER BY child_code").fetchall()]
            for p in plans:
                zf.writestr(f"plans/{p['child_code']}_{p['id']}.json",
                            json.dumps(p, ensure_ascii=False, indent=2, default=str))
    payload = buf.getvalue()
    db.audit(user["username"], "admin.archive", "", f"{len(plans)}件")
    return _Resp(content=payload, media_type="application/zip",
                 headers={"Content-Disposition": f"attachment; filename=archive_{_t.strftime('%Y%m%d')}.zip"})
