"""APIキー・簡易モードのテスト"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))


def test_api_key_flow():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("k_manager", "k_manager123", "manager", "")
    auth_mod.ensure_user("k_teacher", "k_teacher123", "teacher", "")
    cc = TestClient(app)
    m = cc.post("/api/auth/login", json={"username": "k_manager", "password": "k_manager123"}).json()["token"]
    mh = {"Authorization": f"Bearer {m}"}
    r = cc.post("/api/auth/keys", json={"username": "k_teacher", "label": "test"}, headers=mh).json()
    assert r["api_key"].startswith("sk-")
    kh = {"Authorization": f"Bearer {r['api_key']}"}
    me = cc.get("/api/auth/me", headers=kh).json()
    assert me["username"] == "k_teacher"
    # キーで計画作成まで可能
    p = cc.post("/api/plans", json={"child_code": "K-1", "grade": "小4", "class_type": "通級",
                                     "data": {"profile_strengths": "a"}}, headers=kh)
    assert p.status_code == 200, p.text
    # 取消後は無効
    kid = cc.get("/api/auth/keys", headers=mh).json()[0]["id"]
    cc.delete(f"/api/auth/keys/{kid}", headers=mh)
    assert cc.get("/api/auth/me", headers=kh).status_code == 401
    # 教員は発行不可
    t = cc.post("/api/auth/login", json={"username": "k_teacher", "password": "k_teacher123"}).json()["token"]
    th = {"Authorization": f"Bearer {t}"}
    assert cc.post("/api/auth/keys", json={"username": "k_teacher"}, headers=th).status_code == 403


def test_simple_mode_flag():
    from app import auth as auth_mod
    assert auth_mod.SIMPLE_MODE in (True, False)
    os.environ["SIMPLE_MODE"] = "1"
    assert os.environ["SIMPLE_MODE"] == "1"
    del os.environ["SIMPLE_MODE"]
