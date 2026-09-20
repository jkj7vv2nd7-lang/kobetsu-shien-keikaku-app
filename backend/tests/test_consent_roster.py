"""合意記録・OneRosterのテスト"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("w_teacher", "w_teacher123", "teacher", "")
    auth_mod.ensure_user("w_manager", "w_manager123", "manager", "")
    cc = TestClient(app)
    t = cc.post("/api/auth/login", json={"username": "w_teacher", "password": "w_teacher123"}).json()["token"]
    m = cc.post("/api/auth/login", json={"username": "w_manager", "password": "w_manager123"}).json()["token"]
    return cc, {"Authorization": f"Bearer {t}"}, {"Authorization": f"Bearer {m}"}


def _full(code):
    return {"child_code": code, "grade": "小4", "class_type": "通級",
            "profile_strengths": "a", "profile_needs": "b", "guardian_wish": "c",
            "support_long_goal": "d", "guidance_long_goal": "e", "short_goal_1": "f",
            "supports": "g", "eval_method": "h", "guardian_confirmed": False}


def test_consent_flow():
    cc, th, _ = _client()
    pid = cc.post("/api/plans", json={"child_code": "W-1", "grade": "小4", "class_type": "通級",
                                       "data": _full("W-1")}, headers=th).json()["id"]
    assert cc.post(f"/api/plans/{pid}/consents", json={"consenter": "", "method": "対面"}, headers=th).status_code == 400
    assert cc.post(f"/api/plans/{pid}/consents", json={"consenter": "保護者", "method": "電話"}, headers=th).status_code == 400
    r = cc.post(f"/api/plans/{pid}/consents", json={"consenter": "保護者", "method": "対面"}, headers=th).json()
    assert len(r["plan_hash"]) == 32
    rows = cc.get(f"/api/plans/{pid}/consents", headers=th).json()
    assert len(rows) == 1 and rows[0]["method"] == "対面"
    got = cc.get(f"/api/plans/{pid}", headers=th).json()
    assert got["data"]["guardian_confirmed"] is True


def test_oneroster_import():
    cc, th, mh = _client()
    csv_text = ("sourcedId,enabledUser,givenName,familyName,role,grades,orgSourcedIds\n"
                "t001,TRUE,太郎,山田,teacher,,SCH1\n"
                "s001,TRUE,花子,田中,student,小3,SCH1\n"
                "x001,TRUE,,無効,badrole,,SCH1\n"
                "s002,FALSE,次郎,鈴木,student,小4,SCH1\n")
    r = cc.post("/api/admin/oneroster", json={"csv": csv_text}, headers=mh).json()
    assert r["teachers"] == ["t001"]
    assert len(r["students"]) == 1 and r["students"][0]["child_code"] == "s001"
    assert len(r["skipped"]) == 2
    # 氏名は保存しない
    got = cc.get(f"/api/plans/{r['students'][0]['id']}", headers=mh).json()
    assert "familyName" not in str(got["data"]) and "田中" not in str(got["data"])
    # 権限・上限
    assert cc.post("/api/admin/oneroster", json={"csv": csv_text}, headers=th).status_code == 403
    assert cc.post("/api/admin/oneroster", json={"csv": "x" * (2 * 1024 * 1024 + 1)}, headers=mh).status_code == 400
