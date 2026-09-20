"""E2E：seed→login→plan作成→review→manager承認→新潟差し込み→DL→監査。"""
import json
import os
import tempfile
from pathlib import Path

TMP = tempfile.mkdtemp()
os.environ["DB_PATH"] = str(Path(TMP) / "e2e.db")

import sys
BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))

from fastapi.testclient import TestClient
from app.main import app
from app import auth as auth_mod
from app.seed_data import register_niigata

c = TestClient(app)
register_niigata()

# 他テストと干渉しない専用ユーザ（同一プロセスでDB共有のため）
auth_mod.ensure_user("e2e_teacher", "e2e_teacher123", "teacher", "3年1組")
auth_mod.ensure_user("e2e_manager", "e2e_manager123", "manager", "全校")
FULL = {
    "child_code": "E2E-001", "grade": "小3", "class_type": "特別支援学級",
    "profile_strengths": "電車の絵を丁寧に仕上げる。", "profile_needs": "騒がしい場所が苦手。",
    "guardian_wish": "友達と仲よく過ごしてほしい。", "support_long_goal": "自分の気持ちを言葉で伝えられる。",
    "guidance_long_goal": "予定を見て自分で動く。", "short_goal_1": "予定表を見て5分で支度する。",
    "supports": "手順表とシールで称賛する。", "eval_method": "学期末に行動を見て確かめる。",
    "guardian_confirmed": True,
}


def _login(u, p):
    c.post("/api/auth/seed")
    r = c.post("/api/auth/login", json={"username": u, "password": p})
    return r.json()


def test_e2e_full_flow():
    t = _login("e2e_teacher", "e2e_teacher123")["token"]
    th = {"Authorization": f"Bearer {t}"}
    # 1. 計画作成
    r = c.post("/api/plans", json={"child_code": "E2E-001", "grade": "小3",
                                    "class_type": "特別支援学級", "data": FULL}, headers=th)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    assert r.json()["blocked"] is False
    # 2. AIチェック（修正案つき）
    r = c.post("/api/ai/check", json={"plan_id": pid}, headers=th)
    assert r.status_code == 200 and "proposal" in r.json(), r.text
    # 3. 提出→teacher承認不可→manager承認
    assert c.post(f"/api/plans/{pid}/status", json={"status": "review"}, headers=th).status_code == 200
    assert c.post(f"/api/plans/{pid}/status", json={"status": "approved"}, headers=th).status_code == 403
    m = _login("e2e_manager", "e2e_manager123")["token"]
    mh = {"Authorization": f"Bearer {m}"}
    assert c.post(f"/api/plans/{pid}/status", json={"status": "approved"}, headers=mh).status_code == 200
    # 4. 新潟様式プレビュー→差し込み→DL
    niigata = dict(FULL, **{"written_date": "令和8年4月", "child_name": "山田 花子",
                             "consent_date": "令和8年5月", "strengths": "電車の絵が得意。"})
    r = c.post("/api/templates/niigata01/preview", json={"plan_id": pid, "data": niigata}, headers=mh)
    assert r.status_code == 200, r.text
    assert any(s["slot_id"].endswith("_B7") for s in r.json()["slots"])
    r = c.post("/api/templates/niigata01/merge", json={"plan_id": pid, "data": niigata}, headers=mh)
    assert r.status_code == 200, r.text
    dl = r.json()["download"]
    r = c.get(dl, headers=mh)
    assert r.status_code == 200 and len(r.content) > 10000
    # 4b. PDF直接生成
    r = c.post("/api/templates/niigata01/pdf", json={"plan_id": pid, "data": niigata}, headers=mh)
    assert r.status_code == 200, r.text
    assert r.content[:5] == b"%PDF-" and len(r.content) > 20000
    # 5. ダッシュボード・監査
    s = c.get("/api/stats/summary", headers=mh).json()
    assert s["total"] >= 1 and s["by_status"].get("approved", 0) >= 1
    a = c.get("/api/audit", headers=mh).json()
    assert any(x["action"] == "template.merge" for x in a)
    # 6. PW変更
    r = c.post("/api/auth/password", json={"old_password": "e2e_manager123", "new_password": "e2e_manager456"}, headers=mh)
    assert r.json() == {"ok": True}
    assert "token" in c.post("/api/auth/login", json={"username": "e2e_manager", "password": "e2e_manager456"}).json()
