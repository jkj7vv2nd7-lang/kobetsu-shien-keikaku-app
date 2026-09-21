"""提出前チェック・審査サマリのテスト"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("a_teacher", "a_teacher123", "teacher", "")
    auth_mod.ensure_user("a_manager", "a_manager123", "manager", "")
    cc = TestClient(app)
    t = cc.post("/api/auth/login", json={"username": "a_teacher", "password": "a_teacher123"}).json()["token"]
    m = cc.post("/api/auth/login", json={"username": "a_manager", "password": "a_manager123"}).json()["token"]
    return cc, {"Authorization": f"Bearer {t}"}, {"Authorization": f"Bearer {m}"}


def _full(code, **kw):
    d = {"child_code": code, "grade": "小4", "class_type": "通級",
         "profile_strengths": "a", "profile_needs": "b", "guardian_wish": "c",
         "support_long_goal": "d", "guidance_long_goal": "予定表を見て5分で支度する",
         "short_goal_1": "f", "supports": "g", "eval_method": "h",
         "guardian_confirmed": True, "written_date": "令和8年4月", "consent_date": "令和8年5月",
         "next_review_date": "2027-03-01"}
    d.update(kw)
    return d


def test_readiness_and_summary():
    cc, th, mh = _client()
    pid = cc.post("/api/plans", json={"child_code": "A-1", "grade": "小4", "class_type": "通級",
                                       "data": _full("A-1")}, headers=th).json()["id"]
    r = cc.get(f"/api/plans/{pid}/readiness", headers=th).json()
    assert r["must_ok"] is True
    assert any(i["item"] == "目標の具体性（基準・条件）" and i["ok"] for i in r["items"])
    s = cc.get(f"/api/plans/{pid}/review-summary", headers=mh).json()
    assert s["blocked"] is False and s["versions"] == 0 and s["records"] == 0
    # 未入力計画はmust NG
    pid2 = cc.post("/api/plans", json={"child_code": "A-2", "grade": "小4", "class_type": "通級",
                                        "data": {"profile_strengths": "a"}}, headers=th).json()["id"]
    r2 = cc.get(f"/api/plans/{pid2}/readiness", headers=th).json()
    assert r2["must_ok"] is False
