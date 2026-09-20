"""共有リンク・名簿取込のテスト"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("g_teacher", "g_teacher123", "teacher", "")
    auth_mod.ensure_user("g_manager", "g_manager123", "manager", "")
    cc = TestClient(app)
    t = cc.post("/api/auth/login", json={"username": "g_teacher", "password": "g_teacher123"}).json()["token"]
    m = cc.post("/api/auth/login", json={"username": "g_manager", "password": "g_manager123"}).json()["token"]
    return cc, {"Authorization": f"Bearer {t}"}, {"Authorization": f"Bearer {m}"}


def _full(code):
    return {"child_code": code, "grade": "小4", "class_type": "通級",
            "profile_strengths": "a", "profile_needs": "b", "guardian_wish": "c",
            "support_long_goal": "d", "guidance_long_goal": "e", "short_goal_1": "f",
            "supports": "g", "eval_method": "h", "guardian_confirmed": True}


def test_share_lifecycle():
    cc, th, mh = _client()
    pid = cc.post("/api/plans", json={"child_code": "G-1", "grade": "小4", "class_type": "通級",
                                       "data": _full("G-1")}, headers=th).json()["id"]
    # draftでは発行不可
    assert cc.post(f"/api/plans/{pid}/shares", json={"days": 7}, headers=th).status_code == 400
    cc.post(f"/api/plans/{pid}/status", json={"status": "review"}, headers=th)
    s = cc.post(f"/api/plans/{pid}/shares", json={"days": 7}, headers=th).json()
    assert "token" in s
    # 公開閲覧（認証なし）
    pub = cc.get(f"/api/share/{s['token']}")
    assert pub.status_code == 200 and pub.json()["data"]["short_goal_1"] == "f"
    # 取消後は410
    sid = cc.get(f"/api/plans/{pid}/shares", headers=th).json()[0]["id"]
    cc.delete(f"/api/plans/{pid}/shares/{sid}", headers=th)
    assert cc.get(f"/api/share/{s['token']}").status_code == 410
    assert cc.get("/api/share/invalid!!token").status_code == 404


def test_roster_import():
    cc, th, mh = _client()
    rows = [{"child_code": "N-1", "grade": "小1", "class_type": "通級", "school": "全校"},
            {"child_code": "N-2", "grade": "小2", "class_type": "通級", "school": "全校"},
            {"child_code": "", "grade": "小3"}]
    r = cc.post("/api/admin/roster", json={"rows": rows}, headers=mh).json()
    assert len(r["created"]) == 2 and len(r["skipped"]) == 1
    # 重複はスキップ、教員は権限なし
    r2 = cc.post("/api/admin/roster", json={"rows": rows[:1]}, headers=mh).json()
    assert len(r2["created"]) == 0 and len(r2["skipped"]) == 1
    assert cc.post("/api/admin/roster", json={"rows": rows[:1]}, headers=th).status_code == 403
    assert cc.post("/api/admin/roster", json={"rows": list(range(201))}, headers=mh).status_code == 400
