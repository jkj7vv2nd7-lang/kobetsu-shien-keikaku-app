"""DBアダプタの単体テスト（サーバ不要）。Postgres実機は backend/check_postgres.py で。"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))

from app import db


def test_placeholder_conversion():
    assert db.q("SELECT * FROM users WHERE id=?") == "SELECT * FROM users WHERE id=?"


def test_cur_dict_mapping():
    class FakeCur:
        description = (("id",), ("status",))
        def fetchone(self):
            return ("a1", "draft")
        def fetchall(self):
            return [("a1", "draft"), ("b2", "review")]
    assert db._Cur(FakeCur()).fetchone() == {"id": "a1", "status": "draft"}
    assert db._Cur(FakeCur()).fetchall() == [{"id": "a1", "status": "draft"}, {"id": "b2", "status": "review"}]


def test_pdf_smoke(tmp_path):
    sys.path.insert(0, str(BASE / "src"))
    from app.pdfgen import build_niigata_pdf
    blob = build_niigata_pdf({"child_name": "田中 花子", "support_long_goal": "見通しをもって生活します。",
                              "fact_1": "予定変更に不安。", "goal_1": "予定表を見て動く。"})
    assert blob[:5] == b"%PDF-"
    assert len(blob) > 20000
    (tmp_path / "t.pdf").write_bytes(blob)


def test_security_guards():
    import io as _io
    sys.path.insert(0, str(BASE / "backend"))
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod, config as cfg_mod
    auth_mod.ensure_user("sec_teacher", "sec_teacher123", "teacher", "")
    cc = TestClient(app)
    t = cc.post("/api/auth/login", json={"username": "sec_teacher", "password": "sec_teacher123"}).json()["token"]
    h = {"Authorization": f"Bearer {t}", "X": "y"}
    hh = {"Authorization": f"Bearer {t}"}
    # 経路 traversal は400/404で実ファイルに到達しない
    assert cc.get("/api/templates/niigata01/file/%2E%2E%2Fapp%2Fdb.py", headers=hh).status_code in (400, 404)
    assert cc.get("/api/templates/../app/file/x", headers=hh).status_code in (400, 404)
    # 10MB超アップロードは拒否
    big = _io.BytesIO(b"x" * (10 * 1024 * 1024 + 1))
    r = cc.post("/api/templates/upload", files={"file": ("big.xlsx", big)}, headers=hh)
    assert r.status_code == 400, r.status_code
    # .env読込：既存 env 優先・コメント/引用符対応
    import tempfile as _tf
    p = Path(_tf.mkdtemp()) / ".env"
    p.write_text("# comment\nFOO_TEST_X=hello\nQUOTED='a b'\n", encoding="utf-8")
    cfg_mod.load_dotenv(str(p))
    import os as _os
    assert _os.environ["FOO_TEST_X"] == "hello" and _os.environ["QUOTED"] == "a b"
    _os.environ["FOO_TEST_X"] = "keep"
    cfg_mod.load_dotenv(str(p))
    assert _os.environ["FOO_TEST_X"] == "keep"


def test_propose_plain():
    sys.path.insert(0, str(BASE / "src"))
    from core.plain import propose_plain
    r = propose_plain("アセスメントにより改善を促す。")
    assert "アセスメント" not in r["rewritten"] and len(r["applied"]) >= 2


def test_handover_consent_block_and_export():
    import os as _os
    import tempfile as _tf
    _os.environ["DB_PATH"] = str(Path(_tf.mkdtemp()) / "h.db")
    sys.path.insert(0, str(BASE / "backend"))
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("h_teacher", "h_teacher123", "teacher", "")
    cc = TestClient(app)
    cc.post("/api/auth/seed")
    t = cc.post("/api/auth/login", json={"username": "h_teacher", "password": "h_teacher123"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    data = {"child_code": "H-1", "grade": "小4", "class_type": "通級",
            "profile_strengths": "a", "profile_needs": "b", "guardian_wish": "c",
            "support_long_goal": "d", "guidance_long_goal": "e", "short_goal_1": "f",
            "supports": "g", "eval_method": "h", "history": "保育園から通級。",
            "handover_consent": False}
    pid = cc.post("/api/plans", json={"child_code": "H-1", "grade": "小4", "class_type": "通級", "data": data}, headers=h).json()["id"]
    assert cc.get(f"/api/plans/{pid}/handover?format=csv", headers=h).status_code == 400
    data["handover_consent"] = True
    cc.put(f"/api/plans/{pid}", json={"child_code": "H-1", "grade": "小4", "class_type": "通級", "data": data}, headers=h)
    r = cc.get(f"/api/plans/{pid}/handover?format=csv", headers=h)
    assert r.status_code == 200
    text = r.content.decode("utf-8-sig")
    assert "生育歴" in text and "保育園から通級" in text
    rj = cc.get(f"/api/plans/{pid}/handover?format=json", headers=h)
    assert rj.status_code == 200 and rj.json()["data"]["history"] == "保育園から通級。"


def test_norishiro_and_sso():
    import os as _os
    sys.path.insert(0, str(BASE / "src"))
    from core.norishiro import propose_norishiro
    ps = propose_norishiro({"strengths": "電車の絵", "supports": "手順表", "short_goal_1": "支度する"})
    assert len(ps) == 3 and "電車の絵" in ps[0]["body"]
    assert propose_norishiro({})[0]["title"] == "見通しを示して安心させる"
    _os.environ["SSO_TRUSTED_HEADER"] = "X-Remote-User"
    _os.environ["SSO_TRUSTED_NETWORKS"] = "*"
    _os.environ["SSO_DEFAULT_ROLE"] = "teacher"
    sys.path.insert(0, str(BASE / "backend"))
    from fastapi.testclient import TestClient
    from app.main import app
    cc = TestClient(app)
    r = cc.get("/api/auth/sso/me", headers={"X-Remote-User": "sso_taro"})
    assert r.status_code == 200 and r.json()["username"] == "sso_taro", r.text
    r2 = cc.get("/api/auth/sso/me")
    assert r2.status_code == 401
    del _os.environ["SSO_TRUSTED_HEADER"]
