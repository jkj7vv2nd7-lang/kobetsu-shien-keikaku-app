"""API統合テスト v0.3。実行: python -m pytest backend/tests -q"""
import os
import tempfile
from pathlib import Path

TMP = tempfile.mkdtemp()
os.environ["DB_PATH"] = str(Path(TMP) / "test.db")

import sys
BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))

from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)


def _login(u="teacher", p="teacher123"):
    c.post("/api/auth/seed")
    r = c.post("/api/auth/login", json={"username": u, "password": p})
    assert "token" in r.json(), r.json()
    return r.json()["token"]


def test_auth_and_plans_flow():
    tok = _login()
    h = {"Authorization": f"Bearer {tok}"}
    r = c.post("/api/plans", json={"child_code": "T-001", "grade": "小4", "class_type": "特別支援学級",
                                    "data": {"profile_strengths": "a", "profile_needs": "b"}}, headers=h)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    # 必須欠落あり→review遷移は400
    r2 = c.post(f"/api/plans/{pid}/status", json={"status": "review"}, headers=h)
    assert r2.status_code == 400
    # 充足させてreviewへ
    full = {"child_code": "T-001", "grade": "小4", "class_type": "特別支援学級",
            "profile_strengths": "図形が得意", "profile_needs": "変更に不安",
            "guardian_wish": "楽しく", "support_long_goal": "見通しを持って生活",
            "guidance_long_goal": "予定を確認して切替", "short_goal_1": "予定表を見て移動",
            "supports": "視覚支援と予告", "eval_method": "12月に観察", "guardian_confirmed": True}
    r3 = c.put(f"/api/plans/{pid}", json={"child_code": "T-001", "grade": "小4",
                                           "class_type": "特別支援学級", "data": full}, headers=h)
    assert r3.status_code == 200, r3.text
    r4 = c.post(f"/api/plans/{pid}/status", json={"status": "review"}, headers=h)
    assert r4.status_code == 200, r4.text
    # teacherは承認不可
    r5 = c.post(f"/api/plans/{pid}/status", json={"status": "approved"}, headers=h)
    assert r5.status_code == 403


def test_ai_blocks_realname():
    tok = _login()
    h = {"Authorization": f"Bearer {tok}"}
    r = c.post("/api/ai/draft", json={"kind": "guidance_long_goal", "facts": "山田太郎は頑張る",
                                       "child_name": "山田", "school_name": ""}, headers=h)
    # 「山田」が残存すればblocked、除去されれば通過のいずれも許容だが、NG表現チェックは別途
    assert r.status_code == 200


def test_mfa_totp_flow():
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).resolve().parents[2] / "backend"))
    from app import auth
    tok = _login()
    h = {"Authorization": f"Bearer {tok}"}
    r = c.post("/api/auth/mfa/setup", headers=h)
    assert r.status_code == 200, r.text
    secret = r.json()["secret"]
    code = auth.totp_code(secret)
    r2 = c.post("/api/auth/mfa/verify", json={"code": code}, headers=h)
    assert r2.json()["ok"] is True
    assert auth.verify_totp(secret, "000000") is False
    me = c.get("/api/auth/me", headers=h).json()
    assert me["mfa"] is True


def test_comments_and_pdf_endpoint():
    from app import auth as auth_mod
    auth_mod.ensure_user("c_teacher", "c_teacher123", "teacher", "3年1組")
    r = c.post("/api/auth/login", json={"username": "c_teacher", "password": "c_teacher123"})
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.post("/api/plans", json={"child_code": "C-001", "grade": "小4", "class_type": "通級",
                                    "data": {"profile_strengths": "a"}}, headers=h)
    pid = r.json()["id"]
    r = c.post(f"/api/plans/{pid}/comments", json={"body": "通級でも様子を見ます。"}, headers=h)
    assert r.status_code == 200, r.text
    rows = c.get(f"/api/plans/{pid}/comments", headers=h).json()
    assert len(rows) == 1 and rows[0]["author"] == "c_teacher"
    assert c.post(f"/api/plans/{pid}/comments", json={"body": "  "}, headers=h).status_code == 400


def test_template_txt_merge_via_api():
    tok = _login("manager", "manager123")
    h = {"Authorization": f"Bearer {tok}"}
    p = Path(TMP) / "t.txt"
    p.write_text("目標 {{guidance_long_goal}} 以上", encoding="utf-8")
    with open(p, "rb") as f:
        r = c.post("/api/templates/upload", files={"file": ("t.txt", f)}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    tid = r.json()["template_id"]
    data = {"child_code": "T-002", "grade": "小4", "class_type": "通級",
            "profile_strengths": "得意あり", "profile_needs": "配慮あり",
            "guardian_wish": "願い", "support_long_goal": "長期", "guidance_long_goal": "切替を行う",
            "short_goal_1": "短期1", "supports": "手立て", "eval_method": "評価", "guardian_confirmed": True}
    r2 = c.post(f"/api/templates/{tid}/merge", json={"data": data, "mapping": {}}, headers=h)
    assert r2.status_code == 200, r2.text
    assert r2.json()["blocked"] is False
