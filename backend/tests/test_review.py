"""見直しアラート・日々の記録のテスト"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("r_teacher", "r_teacher123", "teacher", "")
    cc = TestClient(app)
    t = cc.post("/api/auth/login", json={"username": "r_teacher", "password": "r_teacher123"}).json()["token"]
    return cc, {"Authorization": f"Bearer {t}"}


def _full(**kw):
    d = {"child_code": "R-1", "grade": "小4", "class_type": "通級",
         "profile_strengths": "a", "profile_needs": "b", "guardian_wish": "c",
         "support_long_goal": "d", "guidance_long_goal": "e", "short_goal_1": "f",
         "supports": "g", "eval_method": "h", "guardian_confirmed": True}
    d.update(kw)
    return d


def test_records_crud_and_validation():
    cc, th = _client()
    pid = cc.post("/api/plans", json={"child_code": "R-1", "grade": "小4", "class_type": "通級",
                                       "data": _full()}, headers=th).json()["id"]
    assert cc.post(f"/api/plans/{pid}/records", json={"date": "2026-09-01", "goal_ref": "短期目標1",
                                                       "body": "予定表を見て動けた。"}, headers=th).status_code == 200
    rows = cc.get(f"/api/plans/{pid}/records", headers=th).json()
    assert len(rows) == 1 and rows[0]["goal_ref"] == "短期目標1"
    assert cc.post(f"/api/plans/{pid}/records", json={"date": "9/1", "body": "x"}, headers=th).status_code == 400
    assert cc.post(f"/api/plans/{pid}/records", json={"date": "", "body": "  "}, headers=th).status_code == 400


def test_review_alerts():
    import datetime
    cc, th = _client()
    past = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
    soon = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    p1 = cc.post("/api/plans", json={"child_code": "R-2", "grade": "小4", "class_type": "通級",
                                      "data": _full(**{"child_code": "R-2", "next_review_date": past})}, headers=th).json()["id"]
    p2 = cc.post("/api/plans", json={"child_code": "R-3", "grade": "小4", "class_type": "通級",
                                      "data": _full(**{"child_code": "R-3", "next_review_date": soon})}, headers=th).json()["id"]
    s = cc.get("/api/stats/summary", headers=th).json()
    assert any(x["id"] == p1 for x in s["overdue"])
    assert any(x["id"] == p2 for x in s["due_soon"])
