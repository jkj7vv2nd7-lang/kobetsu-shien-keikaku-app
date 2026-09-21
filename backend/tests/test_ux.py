"""同意・一括PDF・滞留・backupのテスト"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("u_teacher", "u_teacher123", "teacher", "")
    cc = TestClient(app)
    t = cc.post("/api/auth/login", json={"username": "u_teacher", "password": "u_teacher123"}).json()["token"]
    return cc, {"Authorization": f"Bearer {t}"}


def _full(code, **kw):
    d = {"child_code": code, "grade": "小4", "class_type": "通級",
         "profile_strengths": "a", "profile_needs": "b", "guardian_wish": "c",
         "support_long_goal": "d", "guidance_long_goal": "e", "short_goal_1": "f",
         "supports": "g", "eval_method": "h", "guardian_confirmed": True,
         "written_date": "令和8年4月", "consent_date": "令和8年5月"}
    d.update(kw)
    return d


def test_ai_consent_gate():
    import os as _os
    cc, th = _client()
    # mock既定では同意不要
    r = cc.post("/api/ai/check", json={"facts": "予定表を見る。"}, headers=th)
    assert r.status_code == 200, r.text
    # 同意の記録・撤回
    assert cc.post("/api/auth/ai-consent", json={"agree": True}, headers=th).json() == {"ok": True, "ai_consent": True}
    assert cc.get("/api/auth/me", headers=th).json()["ai_consent"] is True
    assert cc.post("/api/auth/ai-consent", json={"agree": False}, headers=th).json()["ai_consent"] is False


def test_bulk_pdf_and_stuck():
    import datetime
    cc, th = _client()
    p1 = cc.post("/api/plans", json={"child_code": "U-1", "grade": "小4", "class_type": "通級",
                                      "data": _full("U-1")}, headers=th).json()["id"]
    p2 = cc.post("/api/plans", json={"child_code": "U-2", "grade": "小4", "class_type": "通級",
                                      "data": _full("U-2")}, headers=th).json()["id"]
    r = cc.post("/api/templates/bulk-pdf", json={"plan_ids": [p1, p2]}, headers=th)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-", r.text[:200]
    from pypdf import PdfReader
    import io
    assert len(PdfReader(io.BytesIO(r.content)).pages) == 4
    assert cc.post("/api/templates/bulk-pdf", json={"plan_ids": []}, headers=th).status_code == 400
    # 滞留：reviewのまま更新が古い計画
    cc.post(f"/api/plans/{p1}/status", json={"status": "review"}, headers=th)
    from app import db as _db
    with _db.conn() as _c:
        _c.execute("UPDATE plans SET updated_at=? WHERE id=?", (1.0, p1))
    s = cc.get("/api/stats/summary", headers=th).json()
    assert "review_stuck" in s


def test_backup_restore_tmp():
    import tempfile
    sys.path.insert(0, str(BASE / "backend"))
    import backup as backup_mod
    d = Path(tempfile.mkdtemp())
    src = d / "data"
    src.mkdir()
    (src / "app.db").write_bytes(b"fake-db")
    (src / "templates").mkdir()
    z = backup_mod.backup(str(d / "out"), data_dir=src)
    assert z.exists()
    restored = backup_mod.restore(str(z), force=True, data_dir=d / "restored")
    assert (restored / "app.db").read_bytes() == b"fake-db"
    try:
        backup_mod.restore(str(z), force=False)
        raise SystemExit("forceなし復元は不可のはず")
    except RuntimeError:
        pass


def test_draft_kinds_and_archive_bundle():
    sys.path.insert(0, str(BASE / 'backend'))
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user('k2_mgr', 'k2_mgr123', 'manager', '')
    cc = TestClient(app)
    t = cc.post('/api/auth/login', json={'username': 'k2_mgr', 'password': 'k2_mgr123'}).json()['token']
    mh = {'Authorization': f'Bearer {t}'}
    for kind in ('wish', 'support', 'eval'):
        r = cc.post('/api/ai/draft', json={'kind': kind, 'facts': '実態'}, headers=mh).json()
        assert '試作下書き' in r.get('text', ''), kind
    import io, zipfile
    z = cc.get('/api/admin/archive', headers=mh)
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert any(n.endswith('.json') for n in names)


def test_health_split_and_share_cap():
    import sys as _s
    _s.path.insert(0, str(BASE / 'backend'))
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user('h_t', 'h_t12345678', 'teacher', '')
    auth_mod.ensure_user('h_m', 'h_m12345678', 'manager', '')
    cc = TestClient(app)
    pub = cc.get('/api/health').json()
    assert pub['ok'] is True and 'users' not in pub and 'disk_free_mb' not in pub
    t = cc.post('/api/auth/login', json={'username': 'h_t', 'password': 'h_t12345678'}).json()['token']
    m = cc.post('/api/auth/login', json={'username': 'h_m', 'password': 'h_m12345678'}).json()['token']
    th = {'Authorization': f'Bearer {t}'}
    mh = {'Authorization': f'Bearer {m}'}
    assert cc.get('/api/health/detail', headers=th).status_code == 403
    assert cc.get('/api/health/detail', headers=mh).json()['ok'] is True
