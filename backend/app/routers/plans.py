"""計画CRUD＋承認フロー v0.3"""
from __future__ import annotations
import json
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
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


def can_access(user: dict, plan: dict) -> bool:
    """計画の参照・操作可否（一覧の絞り込みと同一基準）。"""
    if user["role"] in ("admin", "manager"):
        return True
    return plan.get("created_by") == user["username"] or (plan.get("school") or "") == (user.get("school") or "")


def _get_plan_or_403(pid: str, user: dict) -> dict:
    with db.conn() as c:
        r = c.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
        if not r:
            raise HTTPException(404, "plan not found")
        p = dict(r)
    if not can_access(user, p):
        raise HTTPException(403, "参照権限がありません")
    return p


def _check_size(body: PlanBody) -> None:
    raw = json.dumps(body.data or {}, ensure_ascii=False)
    if len(raw) > 500 * 1024:
        raise HTTPException(400, "入力データが大きすぎます（500KB以内）")
    for k in (body.child_code, body.school, body.grade, body.class_type):
        if len(k or "") > 100:
            raise HTTPException(400, "基本項目は100字以内にしてください")


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
def list_plans(q: str = "", user: dict = Depends(auth.current_user)):
    like = f"%{(q or '')[:50]}%"
    with db.conn() as c:
        if user["role"] in ("admin", "manager"):
            rows = c.execute("SELECT * FROM plans WHERE (?='' OR child_code LIKE ? OR grade LIKE ?) ORDER BY updated_at DESC LIMIT 500",
                             (q or "", like, like)).fetchall()
        else:
            rows = c.execute("SELECT * FROM plans WHERE (created_by=? OR school=?) AND (?='' OR child_code LIKE ? OR grade LIKE ?) ORDER BY updated_at DESC LIMIT 500",
                             (user["username"], user.get("school", ""), q or "", like, like)).fetchall()
        return [_row_to_plan(dict(r)) for r in rows]


@router.post("")
def create_plan(body: PlanBody, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    _check_size(body)
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
    return _row_to_plan(_get_plan_or_403(pid, user))


@router.put("/{pid}")
def update_plan(pid: str, body: PlanBody, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    _check_size(body)
    src = _get_plan_or_403(pid, user)
    with db.conn() as c:
        if src["status"] == "approved" and user["role"] not in ("admin", "manager"):
            raise HTTPException(403, "承認済みは管理職のみ修正可")
        full = dict(body.data or {})
        full.update({"child_code": body.child_code or src["child_code"],
                     "grade": body.grade or src["grade"],
                     "class_type": body.class_type or src["class_type"]})
        now = time.time()
        # 更新前のスナップショットを履歴に保存（最新20件保持）
        prev_no = c.execute("SELECT COALESCE(MAX(version_no),0) AS m FROM versions WHERE plan_id=?", (pid,)).fetchone()
        nxt = dict(prev_no)["m"] + 1
        c.execute("INSERT INTO versions(id,plan_id,version_no,data_json,created_by,created_at) VALUES(?,?,?,?,?,?)",
                  (uuid.uuid4().hex[:12], pid, nxt, src["data_json"], user["username"], now))
        olds = [dict(r)["id"] for r in c.execute("SELECT id FROM versions WHERE plan_id=? ORDER BY version_no DESC", (pid,)).fetchall()][20:]
        for oid in olds:
            c.execute("DELETE FROM versions WHERE id=?", (oid,))
        c.execute("""UPDATE plans SET child_code=?,school=?,grade=?,class_type=?,data_json=?,
                     updated_by=?,guardian_confirmed=?,guardian_date=?,updated_at=?,status=CASE WHEN status='approved' THEN 'review' ELSE status END
                     WHERE id=?""",
                   (full["child_code"], body.school or src["school"], full["grade"], full["class_type"],
                   json.dumps(full, ensure_ascii=False), user["username"],
                   1 if full.get("guardian_confirmed") else 0, str(full.get("guardian_date", "")), now, pid))
    db.audit(user["username"], "plan.update", pid, full["child_code"])
    return {"id": pid, **validate_plan(full)}


@router.post("/{pid}/validate")
def validate(pid: str, user: dict = Depends(auth.current_user)):
    p = _get_plan_or_403(pid, user)
    return validate_plan(json.loads(p["data_json"] or "{}"))


@router.post("/{pid}/status")
def set_status(pid: str, body: dict, user: dict = Depends(auth.current_user)):
    """body: {"status": "review"|"approved"|"draft"}。承認はmanager以上＋検証エラーなしが条件。"""
    to = (body or {}).get("status", "")
    if to not in STATUSES:
        raise HTTPException(400, f"statusは {STATUSES}")
    if to == "approved":
        auth.require_role(user, "admin", "manager")
    src = _get_plan_or_403(pid, user)
    with db.conn() as c:
        data = json.loads(src["data_json"] or "{}")
        v = validate_plan(data)
        if to in ("review", "approved") and v["blocked"]:
            raise HTTPException(400, f"検証エラーありのため{to}にできません")
        c.execute("UPDATE plans SET status=?,updated_by=?,updated_at=? WHERE id=?",
                  (to, user["username"], time.time(), pid))
    db.audit(user["username"], f"plan.status->{to}", pid, "")
    return {"id": pid, "status": to, **v}


class CommentBody(BaseModel):
    body: str = ""


class RecordBody(BaseModel):
    date: str = ""
    goal_ref: str = ""
    body: str = ""


@router.get("/{pid}/comments")
def list_comments(pid: str, user: dict = Depends(auth.current_user)):
    _get_plan_or_403(pid, user)
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
    _get_plan_or_403(pid, user)
    with db.conn() as c:
        cid = uuid.uuid4().hex[:12]
        c.execute("INSERT INTO comments(id,plan_id,author,body,created_at) VALUES(?,?,?,?,?)",
                  (cid, pid, user["username"], body.body.strip(), time.time()))
    db.audit(user["username"], "plan.comment", pid, body.body.strip()[:100])
    return {"id": cid}


@router.post("/{pid}/duplicate")
def duplicate_plan(pid: str, user: dict = Depends(auth.current_user)):
    """年度更新用に複製。状態はdraft、保護者確認・引継ぎ同意はリセット、前年度IDを記録。"""
    auth.require_role(user, "admin", "manager", "teacher")
    src = _get_plan_or_403(pid, user)
    with db.conn() as c:
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


class ShareBody(BaseModel):
    days: int = 7


@router.get("/{pid}/shares")
def list_shares(pid: str, user: dict = Depends(auth.current_user)):
    _get_plan_or_403(pid, user)
    with db.conn() as c:
        rows = c.execute("SELECT id,plan_id,expires_at,revoked,created_by,created_at FROM shares WHERE plan_id=? ORDER BY created_at DESC", (pid,)).fetchall()
        return [dict(r) for r in rows]


@router.post("/{pid}/shares")
def create_share(pid: str, body: ShareBody, user: dict = Depends(auth.current_user)):
    """保護者共有リンク発行（期限付き・取消可・閲覧記録）。planはreview以上が条件。"""
    _get_plan_or_403(pid, user)
    auth.require_role(user, "admin", "manager", "teacher")
    import secrets as _secrets
    days = max(1, min(int(body.days or 7), 30))
    with db.conn() as c:
        st = c.execute("SELECT status FROM plans WHERE id=?", (pid,)).fetchone()
        if not st or dict(st)["status"] not in ("review", "approved"):
            raise HTTPException(400, "共有は提出(review)以降の計画のみ可能です")
        active = c.execute("SELECT COUNT(*) AS n FROM shares WHERE plan_id=? AND revoked=0 AND expires_at>?",
                           (pid, time.time())).fetchone()
        if dict(active)["n"] >= 20:
            raise HTTPException(400, "有効な共有リンクが上限（20件）です。不要分を取消してください")
        # 期限切れ共有の掃除（ついで）
        try:
            c.execute("DELETE FROM shares WHERE expires_at<? OR revoked=1", (time.time(),))
        except Exception:
            pass
        sid = uuid.uuid4().hex[:12]
        tok = _secrets.token_urlsafe(24)
        now = time.time()
        c.execute("INSERT INTO shares(id,plan_id,token,expires_at,revoked,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                  (sid, pid, tok, now + days * 86400, 0, user["username"], now))
    db.audit(user["username"], "plan.share_create", pid, f"{days}日")
    return {"id": sid, "token": tok, "path": f"/share/{tok}", "days": days}


@router.delete("/{pid}/shares/{sid}")
def revoke_share(pid: str, sid: str, user: dict = Depends(auth.current_user)):
    _get_plan_or_403(pid, user)
    auth.require_role(user, "admin", "manager", "teacher")
    with db.conn() as c:
        c.execute("UPDATE shares SET revoked=1 WHERE id=? AND plan_id=?", (sid, pid))
    db.audit(user["username"], "plan.share_revoke", pid, sid)
    return {"ok": True}


@router.get("/{pid}/records")
def list_records(pid: str, user: dict = Depends(auth.current_user)):
    """日々の指導記録（目標紐付け）の一覧。"""
    _get_plan_or_403(pid, user)
    with db.conn() as c:
        rows = c.execute("SELECT id,plan_id,author,date,goal_ref,body,created_at FROM records WHERE plan_id=? ORDER BY date DESC, created_at DESC LIMIT 500", (pid,)).fetchall()
        return [dict(r) for r in rows]


@router.post("/{pid}/records")
def add_record(pid: str, body: RecordBody, user: dict = Depends(auth.current_user)):
    _get_plan_or_403(pid, user)
    auth.require_role(user, "admin", "manager", "teacher")
    if not body.body.strip():
        raise HTTPException(400, "本文は必須です")
    if len(body.body) > 2000:
        raise HTTPException(400, "本文は2000字以内にしてください")
    import datetime as _dt
    d = (body.date or "").strip()
    if d:
        try:
            _dt.date.fromisoformat(d.replace("/", "-"))
        except ValueError:
            raise HTTPException(400, "日付はYYYY-MM-DD形式にしてください")
    with db.conn() as c:
        rid = uuid.uuid4().hex[:12]
        c.execute("INSERT INTO records(id,plan_id,author,date,goal_ref,body,created_at) VALUES(?,?,?,?,?,?,?)",
                  (rid, pid, user["username"], d, (body.goal_ref or "")[:100], body.body.strip(), time.time()))
    db.audit(user["username"], "plan.record", pid, d)
    return {"id": rid}


def plan_hash(data: dict) -> str:
    """合意内容の特定用ハッシュ（正規化JSONのSHA256）。法的電子署名ではない。"""
    import hashlib
    canon = json.dumps(data or {}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:32]


class ConsentBody(BaseModel):
    consenter: str = ""
    method: str = ""  # 対面 / 共有リンク / 書面


@router.get("/{pid}/consents")
def list_consents(pid: str, user: dict = Depends(auth.current_user)):
    _get_plan_or_403(pid, user)
    with db.conn() as c:
        rows = c.execute("SELECT id,consenter,method,plan_hash,agreed_at,ip,created_by FROM consents WHERE plan_id=? ORDER BY agreed_at DESC", (pid,)).fetchall()
        return [dict(r) for r in rows]


@router.post("/{pid}/consents")
def add_consent(pid: str, body: ConsentBody, req: Request, user: dict = Depends(auth.current_user)):
    _get_plan_or_403(pid, user)
    auth.require_role(user, "admin", "manager", "teacher")
    if not body.consenter.strip():
        raise HTTPException(400, "合意者氏名は必須です")
    if body.method not in ("対面", "共有リンク", "書面"):
        raise HTTPException(400, "方法は 対面/共有リンク/書面 から選択してください")
    ip = req.client.host if req.client else ""
    with db.conn() as c:
        r = c.execute("SELECT data_json FROM plans WHERE id=?", (pid,)).fetchone()
        h = plan_hash(json.loads(dict(r)["data_json"] or "{}"))
        cid = uuid.uuid4().hex[:12]
        now = time.time()
        c.execute("INSERT INTO consents(id,plan_id,consenter,method,plan_hash,agreed_at,ip,created_by) VALUES(?,?,?,?,?,?,?,?)",
                  (cid, pid, body.consenter.strip()[:100], body.method, h, now, ip, user["username"]))
        c.execute("UPDATE plans SET data_json=? WHERE id=?",
                  (json.dumps({**json.loads(dict(r)["data_json"] or "{}"), "guardian_confirmed": True}, ensure_ascii=False), pid))
    db.audit(user["username"], "plan.consent", pid, f"{body.method} {h[:8]}")
    return {"id": cid, "plan_hash": h}


@router.get("/{pid}/versions")
def list_versions(pid: str, user: dict = Depends(auth.current_user)):
    """変更履歴（変更キーつき）。"""
    _get_plan_or_403(pid, user)
    with db.conn() as c:
        rows = [dict(r) for r in c.execute("SELECT version_no,data_json,created_by,created_at FROM versions WHERE plan_id=? ORDER BY version_no DESC", (pid,)).fetchall()]
    out = []
    prev = None
    for r in sorted(rows, key=lambda x: x["version_no"]):
        try:
            cur = json.loads(r["data_json"] or "{}")
        except Exception:
            cur = {}
        changed = sorted([k for k in set(cur) | set(prev or {}) if (prev or {}).get(k) != cur.get(k)]) if prev is not None else []
        out.append({"version_no": r["version_no"], "created_by": r["created_by"],
                    "created_at": r["created_at"], "changed_keys": changed})
        prev = cur
    return list(reversed(out))


@router.post("/{pid}/restore/{version_no}")
def restore_version(pid: str, version_no: int, user: dict = Depends(auth.current_user)):
    """指定版に復元（復元自体も履歴に残る）。承認済みは管理職のみ。"""
    auth.require_role(user, "admin", "manager", "teacher")
    src = _get_plan_or_403(pid, user)
    if src["status"] == "approved" and user["role"] not in ("admin", "manager"):
        raise HTTPException(403, "承認済みは管理職のみ修正可")
    with db.conn() as c:
        r = c.execute("SELECT data_json FROM versions WHERE plan_id=? AND version_no=?", (pid, version_no)).fetchone()
        if not r:
            raise HTTPException(404, "version not found")
        data = json.loads(dict(r)["data_json"] or "{}")
        now = time.time()
        prev_no = c.execute("SELECT COALESCE(MAX(version_no),0) AS m FROM versions WHERE plan_id=?", (pid,)).fetchone()
        c.execute("INSERT INTO versions(id,plan_id,version_no,data_json,created_by,created_at) VALUES(?,?,?,?,?,?)",
                  (uuid.uuid4().hex[:12], pid, dict(prev_no)["m"] + 1, src["data_json"], user["username"], now))
        c.execute("UPDATE plans SET data_json=?,updated_by=?,updated_at=?,status=CASE WHEN status='approved' THEN 'review' ELSE status END WHERE id=?",
                  (json.dumps(data, ensure_ascii=False), user["username"], now, pid))
    db.audit(user["username"], "plan.restore", pid, f"v{version_no}")
    return {"id": pid, **validate_plan(data)}


class SnippetBody(BaseModel):
    category: str = ""
    title: str = ""
    body: str = ""


@router.get("/snippets/all")
def list_snippets(category: str = "", user: dict = Depends(auth.current_user)):
    with db.conn() as c:
        if category:
            rows = c.execute("SELECT * FROM snippets WHERE category=? ORDER BY created_at DESC LIMIT 500", (category,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM snippets ORDER BY category, created_at DESC LIMIT 500").fetchall()
        return [dict(r) for r in rows]


@router.post("/snippets/all")
def create_snippet(body: SnippetBody, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    if not body.title.strip() or not body.body.strip():
        raise HTTPException(400, "タイトル・本文は必須です")
    if len(body.body) > 2000:
        raise HTTPException(400, "本文は2000字以内にしてください")
    with db.conn() as c:
        sid = uuid.uuid4().hex[:12]
        c.execute("INSERT INTO snippets(id,category,title,body,created_by,created_at) VALUES(?,?,?,?,?,?)",
                  (sid, body.category.strip()[:50], body.title.strip()[:100], body.body.strip(),
                   user["username"], time.time()))
    db.audit(user["username"], "snippet.create", sid, body.title.strip()[:50])
    return {"id": sid}


@router.delete("/snippets/all/{sid}")
def delete_snippet(sid: str, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    with db.conn() as c:
        c.execute("DELETE FROM snippets WHERE id=?", (sid,))
    db.audit(user["username"], "snippet.delete", sid, "")
    return {"ok": True}


def _readiness(data: dict) -> list:
    """提出前チェックリスト（受け入れ視点）。level: must（提出条件）/want（推奨）。"""
    items = []
    v = validate_plan(data)
    items.append({"item": "必須・整合性エラーなし", "level": "must",
                  "ok": not v["blocked"], "hint": "保存・検証のerrorを解消してください"})
    items.append({"item": "保護者確認フラグ", "level": "must",
                  "ok": bool(data.get("guardian_confirmed")),
                  "hint": "保護者への説明・合意の上でチェックしてください"})
    items.append({"item": "了承日・記入日の入力", "level": "must",
                  "ok": bool(str(data.get("consent_date", "") or "").strip()) and bool(str(data.get("written_date", "") or "").strip()),
                  "hint": "様式の了承欄・記入日を入力してください"})
    plain_warns = [i for i in v["issues"] if i.get("rule") == "やさしい日本語" and i.get("level") == "warn"]
    items.append({"item": "専門用語の見直し", "level": "want",
                  "ok": len(plain_warns) == 0, "hint": f"残り{len(plain_warns)}件。AI推敲で言い換えを検討"})
    goals = " ".join(str(data.get(k, "")) for k in ("guidance_long_goal", "short_goal_1"))
    items.append({"item": "目標の具体性（基準・条件）", "level": "want",
                  "ok": any(h in goals for h in ("回", "分", "時間", "自分から", "自分で", "までに")),
                  "hint": "回数・時間・場面を入れると評価しやすくなります"})
    items.append({"item": "次回見直し日の設定", "level": "want",
                  "ok": bool(str(data.get("next_review_date", "") or "").strip()),
                  "hint": "期限アラートに使います"})
    return items


@router.get("/{pid}/readiness")
def readiness(pid: str, user: dict = Depends(auth.current_user)):
    p = _get_plan_or_403(pid, user)
    data = json.loads(p["data_json"] or "{}")
    items = _readiness(data)
    return {"items": items, "must_ok": all(i["ok"] for i in items if i["level"] == "must")}


@router.get("/{pid}/review-summary")
def review_summary(pid: str, user: dict = Depends(auth.current_user)):
    """審査用サマリ（管理職・委員向け）：検証・履歴・意見・合意を一括表示。"""
    p = _get_plan_or_403(pid, user)
    data = json.loads(p["data_json"] or "{}")
    v = validate_plan(data)
    counts: dict = {}
    for i in v["issues"]:
        counts[i.get("level", "?")] = counts.get(i.get("level", "?"), 0) + 1
    with db.conn() as c:
        n_ver = c.execute("SELECT COUNT(*) AS n FROM versions WHERE plan_id=?", (pid,)).fetchone()
        comments = [dict(r) for r in c.execute("SELECT author,body,created_at FROM comments WHERE plan_id=? ORDER BY created_at DESC LIMIT 20", (pid,)).fetchall()]
        consents = [dict(r) for r in c.execute("SELECT consenter,method,plan_hash,agreed_at FROM consents WHERE plan_id=? ORDER BY agreed_at DESC", (pid,)).fetchall()]
        records = c.execute("SELECT COUNT(*) AS n FROM records WHERE plan_id=?", (pid,)).fetchone()
    return {"id": pid, "child_code": p["child_code"], "status": p["status"],
            "blocked": v["blocked"], "issue_counts": counts,
            "errors": [i for i in v["issues"] if i.get("level") == "error"][:20],
            "versions": dict(n_ver)["n"], "comments": comments, "consents": consents,
            "records": dict(records)["n"], "readiness": _readiness(data)}
