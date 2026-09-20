"""AI支援API v0.8：下書き・チェック・要約・糊しろ。匿名化＋PII除去を強制。"""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import db, auth
from app.core import llm

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from core.anonymize import anonymize, assert_safe_for_llm, sanitize_for_llm, scrub_text  # noqa: E402
from core.checks import check_expression, check_consistency  # noqa: E402
from core.plain import check_plain, propose_plain  # noqa: E402
from core.guide import check_goal_quality, SUMMARY_FORMAT  # noqa: E402
from core.norishiro import propose_norishiro  # noqa: E402

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AiBody(BaseModel):
    kind: str = "guidance_long_goal"
    facts: str = ""
    plan_id: str = ""
    child_name: str = ""
    school_name: str = ""
    provider: str | None = None


def _plan_facts(plan_id: str) -> tuple:
    """plan_id指定時はDBから非PII項目のみでfactsを構成する。"""
    with db.conn() as c:
        r = c.execute("SELECT data_json FROM plans WHERE id=?", (plan_id,)).fetchone()
        if not r:
            return "", []
        data = json.loads(dict(r)["data_json"] or "{}")
    clean, removed = sanitize_for_llm(data)
    parts = [f"【{k}】{v}" for k, v in clean.items() if isinstance(v, str) and v.strip()]
    return "\n".join(parts), removed


def _guard(body: AiBody):
    facts = body.facts
    secrets: list = []
    if body.plan_id and not facts:
        facts, secrets = _plan_facts(body.plan_id)
    anon = anonymize(facts, child_name=body.child_name, school_name=body.school_name)
    text = scrub_text(anon.text, secrets + [body.child_name, body.school_name])
    problems = assert_safe_for_llm(text, [body.child_name, body.school_name])
    anon.text = text
    return anon, problems


@router.post("/draft")
def draft(body: AiBody, user: dict = Depends(auth.current_user)):
    anon, problems = _guard(body)
    if problems:
        return {"blocked": True, "issues": problems}
    try:
        r = llm.generate(body.kind, anon.text, provider=body.provider)
    except Exception as e:  # noqa: BLE001
        return {"blocked": True, "issues": [str(e)]}
    db.audit(user["username"], "ai.draft", body.plan_id or body.kind,
             f"provider={r.get('provider')} external={r.get('sent_to_external')}")
    return {"blocked": False, "anonymized": anon.text, "warnings": anon.warnings, **r}


@router.post("/check")
def check(body: AiBody, user: dict = Depends(auth.current_user)):
    anon, problems = _guard(body)
    if problems:
        return {"blocked": True, "issues": problems}
    issues = check_expression(anon.text) + check_plain(anon.text) + check_goal_quality(anon.text)
    proposal = propose_plain(anon.text)
    db.audit(user["username"], "ai.check", body.plan_id or "", f"{len(issues)}件")
    return {"blocked": False, "issues": issues, "anonymized": anon.text, "proposal": proposal}


@router.post("/summary")
def summary(body: AiBody, user: dict = Depends(auth.current_user)):
    """引継ぎ要約：facts=前年度記録等。plan_id指定時は非PII項目から自動構成。"""
    anon, problems = _guard(body)
    if problems:
        return {"blocked": True, "issues": problems}
    prompt = SUMMARY_FORMAT + "\n" + anon.text
    try:
        r = llm.generate("summary", prompt, provider=body.provider)
    except Exception as e:  # noqa: BLE001
        return {"blocked": True, "issues": [str(e)]}
    db.audit(user["username"], "ai.summary", body.plan_id or "", f"provider={r.get('provider')}")
    return {"blocked": False, "anonymized": anon.text, **r}


@router.post("/norishiro")
def norishiro(body: AiBody, user: dict = Depends(auth.current_user)):
    """糊しろ提案：規則ベース・外部送信なし。plan_id推奨。"""
    data: dict = {}
    if body.plan_id:
        with db.conn() as c:
            r = c.execute("SELECT data_json FROM plans WHERE id=?", (body.plan_id,)).fetchone()
            if not r:
                raise HTTPException(404, "plan not found")
            raw = json.loads(dict(r)["data_json"] or "{}")
            clean, _ = sanitize_for_llm(raw)
            data = clean
    proposals = propose_norishiro(data or {"profile_strengths": body.facts})
    db.audit(user["username"], "ai.norishiro", body.plan_id or "", f"{len(proposals)}件")
    return {"blocked": False, "proposals": proposals, "sent_to_external": False}
