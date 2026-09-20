"""無双化テスト群 v0.9（追記専用。実行: python -m pytest backend/tests -q）"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))
sys.path.insert(0, str(BASE / "src"))


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("m_teacher", "m_teacher123", "teacher", "")
    auth_mod.ensure_user("m_manager", "m_manager123", "manager", "")
    # 他テストの影響を受けないよう確定パスワードに揃える
    with auth_mod.db.conn() as _c:
        _t = _c.execute("SELECT id FROM users WHERE username='m_teacher'").fetchone()
        _m = _c.execute("SELECT id FROM users WHERE username='m_manager'").fetchone()
    auth_mod.set_password(dict(_t)["id"], "m_teacher123")
    auth_mod.set_password(dict(_m)["id"], "m_manager123")
    cc = TestClient(app)
    t = cc.post("/api/auth/login", json={"username": "m_teacher", "password": "m_teacher123"}).json()
    m = cc.post("/api/auth/login", json={"username": "m_manager", "password": "m_manager123"}).json()
    return cc, {"Authorization": f"Bearer {t['token']}"}, {"Authorization": f"Bearer {m['token']}"}


def test_propose_plain_no_double_suffix():
    sys.path.insert(0, str(BASE / "src"))
    from core.plain import propose_plain
    r = propose_plain("通級指導教室と連携し、通級でも様子を見る。")
    assert "指導教室指導教室" not in r["rewritten"]
    assert "通級指導教室と連携" in r["rewritten"]


def test_must_change_pw_flow():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("m_fresh", "m_fresh123", "teacher", "")
    cc = TestClient(app)
    t = cc.post("/api/auth/login", json={"username": "m_fresh", "password": "m_fresh123"}).json()
    assert t.get("must_change_pw") is True
    th = {"Authorization": f"Bearer {t['token']}"}
    me = cc.get("/api/auth/me", headers=th).json()
    assert me["must_change_pw"] is True
    r = cc.post("/api/auth/password", json={"old_password": "m_fresh123", "new_password": "m_fresh456"}, headers=th)
    assert r.json() == {"ok": True}
    me2 = cc.get("/api/auth/me", headers=th).json()
    assert me2["must_change_pw"] is False


def test_duplicate_resets_consent():
    cc, th, _ = _client()
    data = {"child_code": "D-1", "grade": "小4", "class_type": "通級",
            "profile_strengths": "a", "profile_needs": "b", "guardian_wish": "c",
            "support_long_goal": "d", "guidance_long_goal": "e", "short_goal_1": "f",
            "supports": "g", "eval_method": "h", "guardian_confirmed": True, "handover_consent": True}
    pid = cc.post("/api/plans", json={"child_code": "D-1", "grade": "小4", "class_type": "通級", "data": data}, headers=th).json()["id"]
    cc.post(f"/api/plans/{pid}/comments", json={"body": "申送り"}, headers=th)
    nid = cc.post(f"/api/plans/{pid}/duplicate", headers=th).json()["id"]
    got = cc.get(f"/api/plans/{nid}", headers=th).json()
    assert got["status"] == "draft"
    assert got["data"]["guardian_confirmed"] is False and got["data"]["handover_consent"] is False
    assert got["data"]["prev_plan_id"] == pid
    assert len(cc.get(f"/api/plans/{nid}/comments", headers=th).json()) == 1


def test_health_and_audit_export():
    cc, _, mh = _client()
    h = cc.get("/api/health").json()
    assert h["ok"] is True and h["pdf_font"] is True and h["db"] in ("sqlite", "postgres")
    r = cc.get("/api/audit/export", headers=mh)
    assert r.status_code == 200
    assert "操作" in r.content.decode("utf-8-sig")


def test_docx_append_and_table_leftover():
    from docx import Document
    from app.core import template_engine
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    src = tmp / "t.docx"
    doc = Document()
    doc.add_paragraph("性別")
    t = doc.add_table(rows=1, cols=1)
    t.cell(0, 0).text = "{{missing_field}}"
    doc.save(src)
    out = tmp / "o.docx"
    # append モード
    template_engine.merge_docx(str(src), str(out),
                               {"gender": "女", "missing_field": "x"},
                               {"docx_p0": {"field": "gender", "mode": "append"}})
    assert Document(str(out)).paragraphs[0].text == "性別　女"
    # 表セル leftover 検査の確認：未解決があれば例外
    try:
        template_engine.merge_docx(str(src), str(tmp / "o2.docx"), {}, {})
        raise SystemExit("leftover未検出は異常")
    except ValueError as e:
        assert "missing_field" in str(e)


def test_backup_roundtrip():
    import shutil
    import tempfile
    import zipfile
    sys.path.insert(0, str(BASE / "backend"))
    import backup as backup_mod
    d = Path(tempfile.mkdtemp())
    z = backup_mod.backup(str(d))
    assert z.exists() and zipfile.is_zipfile(z)
    names = zipfile.ZipFile(z).namelist()
    assert any("app.db" in n for n in names)
    shutil.rmtree(d, ignore_errors=True)
