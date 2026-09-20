"""履歴・定型文・検索・アーカイブのテスト"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("z_teacher", "z_teacher123", "teacher", "")
    auth_mod.ensure_user("z_manager", "z_manager123", "manager", "")
    cc = TestClient(app)
    t = cc.post("/api/auth/login", json={"username": "z_teacher", "password": "z_teacher123"}).json()["token"]
    m = cc.post("/api/auth/login", json={"username": "z_manager", "password": "z_manager123"}).json()["token"]
    return cc, {"Authorization": f"Bearer {t}"}, {"Authorization": f"Bearer {m}"}


def _full(code):
    return {"child_code": code, "grade": "小4", "class_type": "通級",
            "profile_strengths": "a", "profile_needs": "b", "guardian_wish": "c",
            "support_long_goal": "d", "guidance_long_goal": "e", "short_goal_1": "f",
            "supports": "g", "eval_method": "h", "guardian_confirmed": True}


def test_versions_and_restore():
    cc, th, _ = _client()
    pid = cc.post("/api/plans", json={"child_code": "Z-1", "grade": "小4", "class_type": "通級",
                                       "data": _full("Z-1")}, headers=th).json()["id"]
    d2 = _full("Z-1")
    d2["short_goal_1"] = "予定表を見て動く"
    cc.put(f"/api/plans/{pid}", json={"child_code": "Z-1", "grade": "小4", "class_type": "通級", "data": d2}, headers=th)
    vs = cc.get(f"/api/plans/{pid}/versions", headers=th).json()
    assert len(vs) == 1 and vs[0]["created_by"] == "z_teacher"
    r = cc.post(f"/api/plans/{pid}/restore/1", headers=th).json()
    assert r["id"] == pid
    got = cc.get(f"/api/plans/{pid}", headers=th).json()
    assert got["data"]["short_goal_1"] == "f"
    assert cc.post(f"/api/plans/{pid}/restore/99", headers=th).status_code == 404


def test_snippets_and_search_and_archive():
    cc, th, mh = _client()
    s = cc.get("/api/plans/snippets/all", headers=th).json()
    assert len(s) >= 5
    r = cc.post("/api/plans/snippets/all", json={"category": "T", "title": "t1", "body": "b1"}, headers=th).json()
    assert "id" in r
    assert cc.post("/api/plans/snippets/all", json={"category": "T", "title": "", "body": "b"}, headers=th).status_code == 400
    cc.post("/api/plans", json={"child_code": "Z-SEARCH-1", "grade": "小6", "class_type": "通級",
                                 "data": _full("Z-SEARCH-1")}, headers=th)
    found = cc.get("/api/plans?q=Z-SEARCH", headers=th).json()
    assert any(p["child_code"] == "Z-SEARCH-1" for p in found)
    found6 = cc.get("/api/plans?q=小6", headers=th).json()
    assert any(p["child_code"] == "Z-SEARCH-1" for p in found6)
    z = cc.get("/api/admin/archive", headers=mh)
    assert z.status_code == 200 and z.content[:2] == b"PK"
    assert cc.get("/api/admin/archive", headers=th).status_code == 403
