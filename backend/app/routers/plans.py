"""計画CRUD＋承認フロー v0.3"""
from __future__ import annotations
import json
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import db, auth

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from core.checks import check_expression, check_consistency, check_required  # noqa: E402
from core.plain import check_plain  # noqa: E402
from core.guide import check_goal_quality  # noqa: E402

router = APIRouter(prefix="/api/plans", tags=["plans"])
STATUSES = ("draft", "review", "approved")


class PlanBody(BaseModel):
    child_code: str = ""
    school: str = ""
    grade: str = ""
    class_type: str = ""
    data: dict = {}


def _row_to_plan(r: dict) -> dict:
    d = dict(r)
    try:
        d["data"] = json.loads(d.pop("data_json", "{}") or "{}")
    except Exception:
        d["data"] = {}
    return d


def validate_plan(data: dict) -> dict:
    issues = check_required(data) + check_consistency(data)
    issues += check_expression(" ".join(str(v) for v in data.values()))
    issues += check_plain(" ".join(str(v) for v in data.values() if isinstance(v, str)))
    goals = " ".join(str(data.get(k, "")) for k in
                     ("support_long_goal", "guidance_long_goal", "short_goal_1", "short_goal_2",
                      *[f"goal_{n}" for n in range(1, 10)]))
    issues += check_goal_quality(goals)
    errors = [i for i in issues if i.get("level") == "error"]
    return {"issues": issues, "blocked": bool(errors)}


@router.get("")
def list_plans(user: dict = Depends(auth.current_user)):
    with db.conn() as c:
        if user["role"] in ("admin", "manager"):
            rows = c.execute("SELECT * FROM plans ORDER BY updated_at DESC LIMIT 500").fetchall()
        else:
            rows = c.execute("SELECT * FROM plans WHERE created_by=? OR school=? ORDER BY updated_at DESC LIMIT 500",
                             (user["username"], user.get("school", ""))).fetchall()
        return [_row_to_plan(dict(r)) for r in rows]


@router.post("")
def create_plan(body: PlanBody, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    if not body.child_code.strip():
        raise HTTPException(400, "child_code（管理番号）は必須。実名は入れないこと。")
    pid = uuid.uuid4().hex[:12]
    now = time.time()
    full = dict(body.data or {})
    full.update({"child_code": body.child_code, "grade": body.grade, "class_type": body.class_type,
                 "guardian_confirmed": bool(full.get("guardian_confirmed", False))})
    with db.conn() as c:
        c.execute("""INSERT INTO plans(id,child_code,school,grade,class_type,status,data_json,
                     created_by,updated_by,guardian_confirmed,guardian_date,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (pid, body.child_code, body.school or user.get("school", ""), body.grade, body.class_type,
                   "draft", json.dumps(full, ensure_ascii=False), user["username"], user["username"],
                   1 if full.get("guardian_confirmed") else 0, str(full.get("guardian_date", "")), now, now))
    db.audit(user["username"], "plan.create", pid, body.child_code)
    return {"id": pid, **validate_plan(full)}


@router.get("/{pid}")
def get_plan(pid: str, user: dict = Depends(auth.current_user)):
    with db.conn() as c:
        r = c.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        return _row_to_plan(dict(r))


@router.put("/{pid}")
def update_plan(pid: str, body: PlanBody, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    with db.conn() as c:
        r = c.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        if dict(r)["status"] == "approved" and user["role"] not in ("admin", "manager"):
            raise HTTPException(403, "承認済みは管理職のみ修正可")
        full = dict(body.data or {})
        full.update({"child_code": body.child_code or dict(r)["child_code"],
                     "grade": body.grade or dict(r)["grade"],
                     "class_type": body.class_type or dict(r)["class_type"]})
        now = time.time()
        c.execute("""UPDATE plans SET child_code=?,school=?,grade=?,class_type=?,data_json=?,
                     updated_by=?,guardian_confirmed=?,guardian_date=?,updated_at=?,status=CASE WHEN status='approved' THEN 'review' ELSE status END
                     WHERE id=?""",
                  (full["child_code"], body.school or dict(r)["school"], full["grade"], full["class_type"],
                   json.dumps(full, ensure_ascii=False), user["username"],
                   1 if full.get("guardian_confirmed") else 0, str(full.get("guardian_date", "")), now, pid))
    db.audit(user["username"], "plan.update", pid, full["child_code"])
    return {"id": pid, **validate_plan(full)}


@router.post("/{pid}/validate")
def validate(pid: str, user: dict = Depends(auth.current_user)):
    with db.conn() as c:
        r = c.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        data = json.loads(dict(r)["data_json"] or "{}")
        return validate_plan(data)


@router.post("/{pid}/status")
def set_status(pid: str, body: dict, user: dict = Depends(auth.current_user)):
    """body: {"status": "review"|"approved"|"draft"}。承認はmanager以上＋検証エラーなしが条件。"""
    to = (body or {}).get("status", "")
    if to not in STATUSES:
        raise HTTPException(400, f"statusは {STATUSES}")
    if to == "approved":
        auth.require_role(user, "admin", "manager")
    with db.conn() as c:
        r = c.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        data = json.loads(dict(r)["data_json"] or "{}")
        v = validate_plan(data)
        if to in ("review", "approved") and v["blocked"]:
            raise HTTPException(400, f"検証エラーありのため{to}にできません")
        c.execute("UPDATE plans SET status=?,updated_by=?,updated_at=? WHERE id=?",
                  (to, user["username"], time.time(), pid))
    db.audit(user["username"], f"plan.status->{to}", pid, "")
    return {"id": pid, "status": to, **v}


class CommentBody(BaseModel):
    body: str = ""


@router.get("/{pid}/comments")
def list_comments(pid: str, user: dict = Depends(auth.current_user)):
    with db.conn() as c:
        rows = c.execute("SELECT id,plan_id,author,body,created_at FROM comments WHERE plan_id=? ORDER BY created_at",
                         (pid,)).fetchall()
        return [dict(r) for r in rows]


@router.post("/{pid}/comments")
def add_comment(pid: str, body: CommentBody, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    if not body.body.strip():
        raise HTTPException(400, "本文は必須です")
    if len(body.body) > 2000:
        raise HTTPException(400, "本文は2000字以内にしてください")
    with db.conn() as c:
        if not c.execute("SELECT id FROM plans WHERE id=?", (pid,)).fetchone():
            raise HTTPException(404, "plan not found")
        cid = uuid.uuid4().hex[:12]
        c.execute("INSERT INTO comments(id,plan_id,author,body,created_at) VALUES(?,?,?,?,?)",
                  (cid, pid, user["username"], body.body.strip(), time.time()))
    db.audit(user["username"], "plan.comment", pid, body.body.strip()[:100])
    return {"id": cid}


@router.post("/{pid}/duplicate")
def duplicate_plan(pid: str, user: dict = Depends(auth.current_user)):
    """年度更新用に複製。状態はdraft、保護者確認・引継ぎ同意はリセット、前年度IDを記録。"""
    auth.require_role(user, "admin", "manager", "teacher")
    with db.conn() as c:
        r = c.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
        if not r:
            raise HTTPException(404, "plan not found")
        src = dict(r)
        data = json.loads(src["data_json"] or "{}")
        data["guardian_confirmed"] = False
        data["handover_consent"] = False
        data["prev_plan_id"] = pid
        nid = uuid.uuid4().hex[:12]
        now = time.time()
        c.execute("""INSERT INTO plans(id,child_code,school,grade,class_type,status,data_json,
                     created_by,updated_by,guardian_confirmed,guardian_date,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (nid, src["child_code"], src["school"], "", src["class_type"], "draft",
                   json.dumps(data, ensure_ascii=False), user["username"], user["username"],
                   0, "", now, now))
        # コメント（支援会議メモ）も引き継ぐ
        for cm in c.execute("SELECT author,body,created_at FROM comments WHERE plan_id=? ORDER BY created_at",
                            (pid,)).fetchall():
            d = dict(cm)
            c.execute("INSERT INTO comments(id,plan_id,author,body,created_at) VALUES(?,?,?,?,?)",
                      (uuid.uuid4().hex[:12], nid, d["author"], d["body"], d["created_at"]))
    db.audit(user["username"], "plan.duplicate", nid, f"from={pid}")
    return {"id": nid, "from": pid}
