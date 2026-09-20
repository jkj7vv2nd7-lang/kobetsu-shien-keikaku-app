"""相談支援ファイル連携 v0.7：引継ぎデータのCSV/JSON出力。

新潟県の「相談支援ファイル」（出生〜発達経過・支援の一元化）への橋渡しとして、
計画の引継ぎ項目を外部持ち出し用に出力する。CSVはExcel互換（BOM付きUTF-8）。
ハンドブックp21の通り、引継ぎ先への情報提供は保護者同意が前提のため、
同意フラグなしの出力はブロックする。
"""
from __future__ import annotations
import csv
import io
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app import db, auth

router = APIRouter(prefix="/api/plans", tags=["handover"])

FIELDS = [
    ("child_code", "管理番号"), ("grade", "学年"), ("class_type", "在籍形態"),
    ("history", "生育歴・療育教育歴"), ("life", "生活の様子"), ("wish", "願い・希望"),
    ("strengths", "得意・興味関心"), ("support_long_goal", "長期目標（支援）"),
    ("guidance_long_goal", "長期目標（指導）"), ("effective_supports", "有効だった工夫と条件"),
    ("episode", "対応エピソード"), ("related_agencies", "関係機関"),
    ("eval_handover", "評価・引継ぎ事項"), ("start_ease", "糊しろ（4月のおさらい課題）"),
    ("guardian_wish", "保護者の願い"), ("child_wish", "本人の願い"),
    ("handover_to", "引継ぎ先"), ("handover_consent_date", "引継ぎ同意日"),
]


def _load(pid: str) -> tuple:
    with db.conn() as c:
        r = c.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
        if not r:
            raise HTTPException(404, "plan not found")
        p = dict(r)
    data = json.loads(p.get("data_json") or "{}")
    return p, data


@router.get("/{pid}/handover")
def handover(pid: str, format: str = "csv", user: dict = Depends(auth.current_user)):
    p, data = _load(pid)
    consent = bool(data.get("handover_consent")) or bool(data.get("guardian_confirmed"))
    if not consent:
        raise HTTPException(400, "引継ぎ出力には保護者の同意フラグ（引継ぎ同意または保護者確認）が必要です")
    if format == "json":
        with db.conn() as c:
            comments = [dict(r) for r in
                        c.execute("SELECT author,body,created_at FROM comments WHERE plan_id=? ORDER BY created_at",
                                  (pid,)).fetchall()]
        body = {"plan": {"id": p["id"], "child_code": p["child_code"], "grade": p["grade"],
                         "class_type": p["class_type"], "status": p["status"]},
                "data": {k: data.get(k, "") for k, _ in FIELDS},
                "comments": comments}
        payload = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        media = "application/json"
        ext = "json"
    elif format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["項目", "内容"])
        for key, label in FIELDS:
            v = data.get(key, p.get(key, ""))
            w.writerow([label, "" if v is None else str(v)])
        payload = "\ufeff".encode("utf-8") + buf.getvalue().encode("utf-8")
        media = "text/csv"
        ext = "csv"
    else:
        raise HTTPException(400, "formatは csv|json")
    db.audit(user["username"], "plan.handover", pid, f"format={format}")
    import re as _re
    safe = _re.sub(r"[^A-Za-z0-9_-]+", "_", str(p.get("child_code", "")).strip())[:40].strip("_") or "out"
    return Response(content=payload, media_type=media,
                    headers={"Content-Disposition": f"attachment; filename=handover_{safe}.{ext}"})
