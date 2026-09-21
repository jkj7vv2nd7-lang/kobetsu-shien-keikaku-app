"""自己登録・権限緩和のテスト"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))


def test_signup_and_relaxed_gates():
    from fastapi.testclient import TestClient
    from app.main import app
    cc = TestClient(app)
    r = cc.post("/api/auth/signup", json={"username": "j_self", "password": "j_self123456"}).json()
    assert "token" in r and r["role"] == "teacher", r
    th = {"Authorization": f"Bearer {r['token']}"}
    assert cc.post("/api/auth/signup", json={"username": "j_self", "password": "j_self123456"}).status_code == 400
    assert cc.post("/api/auth/signup", json={"username": "あ", "password": "short"}).status_code == 400
    # 担任でも名簿取込・キー発行（自分）・定型文削除が可能
    rows = [{"child_code": "J-1", "grade": "小1", "class_type": "通級", "school": ""}]
    assert len(cc.post("/api/admin/roster", json={"rows": rows}, headers=th).json()["created"]) == 1
    k = cc.post("/api/auth/keys", json={"username": "j_self", "label": "t"}, headers=th).json()
    assert k["api_key"].startswith("sk-")
    assert cc.post("/api/auth/keys", json={"username": "other", "label": "t"}, headers=th).status_code in (403, 404)
    # 監査・アーカイブは管理職のみのまま
    assert cc.get("/api/audit", headers=th).status_code == 403
    assert cc.get("/api/admin/archive", headers=th).status_code == 403
    # 最終起案（承認）は管理職のみ
    pid = cc.post("/api/plans", json={"child_code": "J-2", "grade": "小4", "class_type": "通級",
                                       "data": {"profile_strengths": "a"}}, headers=th).json()["id"]
    assert cc.post(f"/api/plans/{pid}/status", json={"status": "approved"}, headers=th).status_code == 403
