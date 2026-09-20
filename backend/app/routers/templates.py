"""様式API（DB管理化）＋ファイル保存は data/templates/{id}/"""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import db, auth
from app.core import template_engine

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from core.checks import check_expression, check_consistency, check_required  # noqa: E402
from core.merge import merge as merge_txt  # noqa: E402
from core.plain import check_plain  # noqa: E402

router = APIRouter(prefix="/api/templates", tags=["templates"])
BASE = Path(__file__).resolve().parents[2]
TDATA = BASE / "data" / "templates"
TDATA.mkdir(parents=True, exist_ok=True)


def _tdir(tid: str) -> Path:
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9_-]{1,32}", tid or ""):
        raise HTTPException(400, "不正なtemplate_id")
    return TDATA / tid


def _safe_name(value: str, fallback: str = "out") -> str:
    import re as _re
    s = _re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())[:40].strip("_")
    return s or fallback


class MappingBody(BaseModel):
    mapping: dict
    label: str = ""


class MergeBody(BaseModel):
    plan_id: str = ""
    data: dict = {}
    mapping: dict = {}
    template_id: str = ""


@router.get("")
def list_templates(user: dict = Depends(auth.current_user)):
    with db.conn() as c:
        rows = c.execute("SELECT * FROM templates ORDER BY created_at DESC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["mapping"] = json.loads(d.pop("mapping_json", "{}") or "{}")
            out.append(d)
        return out


@router.post("/upload")
async def upload(file: UploadFile = File(...), user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(400, "ファイルは10MB以内にしてください")
    tid = uuid.uuid4().hex[:8]
    d = _tdir(tid)
    d.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "template").suffix.lower() or ".txt"
    if suffix not in (".txt", ".docx", ".xlsx"):
        raise HTTPException(400, "対応形式は .txt/.docx/.xlsx です")
    dest = _tdir(tid) / f"original{suffix}"
    dest.write_bytes(raw)
    try:
        if suffix == ".txt":
            slots = template_engine.extract_txt(dest.read_text(encoding="utf-8", errors="ignore"))
        elif suffix == ".docx":
            slots = template_engine.extract_docx(str(dest))
        else:
            slots = template_engine.extract_xlsx(str(dest))
    except Exception as e:  # noqa: BLE001 - 破損・偽装ファイルは400
        raise HTTPException(400, f"ファイル解析失敗（破損の可能性）: {str(e)[:200]}")
    (d / "slots.json").write_text(json.dumps(slots, ensure_ascii=False, indent=2), encoding="utf-8")
    with db.conn() as c:
        c.execute("INSERT INTO templates(id,filename,suffix,label,mapping_json,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                  (tid, file.filename, suffix, file.filename, "{}", user["username"], time.time()))
    db.audit(user["username"], "template.upload", tid, file.filename or "")
    return {"template_id": tid, "slots": slots}


@router.get("/{tid}/slots")
def slots(tid: str, user: dict = Depends(auth.current_user)):
    f = _tdir(tid) / "slots.json"
    if not f.exists():
        raise HTTPException(404, "not found")
    with db.conn() as c:
        r = c.execute("SELECT mapping_json FROM templates WHERE id=?", (tid,)).fetchone()
        mapping = json.loads(dict(r)["mapping_json"]) if r else {}
    return {"template_id": tid, "slots": json.loads(f.read_text(encoding="utf-8")), "mapping": mapping}


@router.post("/{tid}/mapping")
def save_mapping(tid: str, body: MappingBody, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    (_tdir(tid) / "mapping.json").write_text(json.dumps(body.mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    with db.conn() as c:
        c.execute("UPDATE templates SET mapping_json=?,label=? WHERE id=?",
                  (json.dumps(body.mapping, ensure_ascii=False), body.label or "", tid))
    db.audit(user["username"], "template.mapping", tid, f"{len(body.mapping)}件")
    return {"ok": True}


@router.post("/{tid}/merge")
def merge_template(tid: str, body: MergeBody, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    if len(body.mapping or {}) > 2000:
        raise HTTPException(400, "マッピングが多すぎます（2000件以内）")
    data, mapping, suffix = _resolve(tid, body, user)
    issues = _validate(data)
    if any(i.get("level") == "error" for i in issues):
        raise HTTPException(400, {"message": "検証エラー", "issues": issues})
    src = str(_tdir(tid) / f"original{suffix}")
    import uuid as _uuid
    out = _tdir(tid) / f"filled_{_safe_name(str(data.get('child_code', '')))}_{_uuid.uuid4().hex[:6]}{suffix}"
    try:
        if suffix == ".txt":
            tpl = Path(src).read_text(encoding="utf-8")
            Path(out).write_text(merge_txt(tpl, data), encoding="utf-8")
        elif suffix == ".docx":
            template_engine.merge_docx(src, str(out), data, mapping)
        else:
            template_engine.merge_xlsx(src, str(out), data, mapping)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # 古い出力物の整理（最新3件を保持）
    try:
        olds = sorted(_tdir(tid).glob(f"filled_*{suffix}"), key=lambda p: p.stat().st_mtime)
        for old in olds[:-3]:
            old.unlink(missing_ok=True)
    except Exception:
        pass
    db.audit(user["username"], "template.merge", tid, out.name)
    return {"blocked": False, "issues": issues, "output": out.name,
            "download": f"/api/templates/{tid}/file/{out.name}"}


def _resolve(tid: str, body: MergeBody, user: dict | None = None):
    """plan/data・mapping・suffixを確定して返す。plan_id指定時は参照権限も確認。"""
    data = dict(body.data or {})
    if body.plan_id:
        from app.routers.plans import _get_plan_or_403
        if user is None:
            raise HTTPException(401, "要ログイン")
        p = _get_plan_or_403(body.plan_id, user)
        data = json.loads(p["data_json"] or "{}")
    mapping = dict(body.mapping or {})
    with db.conn() as c:
        t = c.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()
        if not t:
            raise HTTPException(404, "template not found")
        if not mapping:
            mapping = json.loads(dict(t)["mapping_json"] or "{}")
        suffix = dict(t)["suffix"]
    return data, mapping, suffix


def _validate(data: dict) -> list:
    issues = check_required(data) + check_consistency(data)
    issues += check_expression(" ".join(str(v) for v in data.values()))
    issues += check_plain(" ".join(str(v) for v in data.values() if isinstance(v, str)))
    return issues


@router.post("/{tid}/preview")
def preview(tid: str, body: MergeBody, user: dict = Depends(auth.current_user)):
    """ファイルを作らず、slot→値の解決結果と不足を返す（差し込み前確認用）。"""
    data, mapping, suffix = _resolve(tid, body, user)
    f = _tdir(tid) / "slots.json"
    slots = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    rows = []
    mapped_fields = set()
    for s in slots:
        sid = s.get("slot_id", "")
        spec = mapping.get(sid)
        field = (spec.get("field") if isinstance(spec, dict) else spec) or s.get("field_hint", "")
        val = data.get(field, "") if field else ""
        if field:
            mapped_fields.add(field)
        rows.append({"slot_id": sid, "label": s.get("label", ""), "kind": s.get("kind", ""),
                     "sheet": s.get("sheet", ""), "cell": s.get("cell", ""),
                     "field": field or "(未割当)", "value": val if not isinstance(val, bool) else ("確認済" if val else "未確認"),
                     "empty": not (str(val).strip() if not isinstance(val, bool) else val)})
    unmapped = [s.get("slot_id") for s in slots if s.get("slot_id") not in mapping and not s.get("field_hint")]
    issues = _validate(data)
    if body.plan_id:
        db.audit(user["username"], "template.preview", tid, body.plan_id)
    return {"slots": rows, "unmapped": unmapped, "issues": issues,
            "blocked": any(i.get("level") == "error" for i in issues),
            "suffix": suffix}


@router.post("/{tid}/pdf")
def template_pdf(tid: str, body: MergeBody, user: dict = Depends(auth.current_user)):
    """新潟様式のPDF直接生成。検証エラー時はブロック。"""
    from fastapi.responses import Response
    from app import pdfgen
    auth.require_role(user, "admin", "manager", "teacher")
    if tid != "niigata01":
        raise HTTPException(400, "PDF直接生成は新潟様式（niigata01）のみ対応。他様式はExcel出力→印刷→PDFを利用してください。")
    data, _, _ = _resolve(tid, body, user)
    issues = _validate(data)
    if any(i.get("level") == "error" for i in issues):
        raise HTTPException(400, {"message": "検証エラー", "issues": issues})
    try:
        blob = pdfgen.build_niigata_pdf(data)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    db.audit(user["username"], "template.pdf", tid, str(data.get("child_code", "")))
    return Response(content=blob, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=niigata_{_safe_name(str(data.get('child_code', '')))}.pdf"})


@router.get("/{tid}/file/{name}")
def download(tid: str, name: str, user: dict = Depends(auth.current_user)):
    auth.require_role(user, "admin", "manager", "teacher")
    safe = Path(name).name
    if safe != name or ".." in name or "/" in name or "\\" in name:
        raise HTTPException(400, "不正なファイル名")
    f = _tdir(tid) / safe
    if not f.exists():
        raise HTTPException(404, "not found")
    db.audit(user["username"], "template.download", tid, safe)
    return FileResponse(str(f), filename=safe)
