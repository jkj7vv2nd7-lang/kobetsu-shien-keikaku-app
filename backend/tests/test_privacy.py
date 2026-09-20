"""個人情報ガードのテスト（実行: python -m pytest backend/tests/test_privacy.py -q）"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))
sys.path.insert(0, str(BASE / "src"))


def test_pii_pattern_block_via_api():
    from fastapi.testclient import TestClient
    from app.main import app
    from app import auth as auth_mod
    auth_mod.ensure_user("q_user", "q_user123", "teacher", "")
    cc = TestClient(app)
    t = cc.post("/api/auth/login", json={"username": "q_user", "password": "q_user123"}).json()["token"]
    hh = {"Authorization": f"Bearer {t}"}
    r = cc.post("/api/ai/check", json={"facts": "025-000-0000 に連絡する。"}, headers=hh)
    assert r.json()["blocked"] is True, r.text
    r = cc.post("/api/ai/check", json={"facts": "新潟市中央区1-2-3に住む。"}, headers=hh)
    assert r.json()["blocked"] is True, r.text
    r2 = cc.post("/api/ai/check", json={"facts": "予定表を見て5分で支度する。"}, headers=hh)
    assert r2.json()["blocked"] is False, r2.text


def test_detect_patterns_unit():
    from core.anonymize import detect_pii_patterns, assert_safe_for_llm
    assert detect_pii_patterns("090-0000-0000") == ["電話番号"]
    assert detect_pii_patterns("t@example.com") == ["メールアドレス"]
    assert detect_pii_patterns("予定表を見る") == []
    # エラー文に頭文字を含めない
    assert assert_safe_for_llm("山田太郎が来た", ["山田太郎"]) == ["入力文中に個人を特定できる名前が残っています。除去してください"]


def test_demo_guard_empty_vs_used_db():
    env = dict(os.environ)
    d1 = Path(tempfile.mkdtemp())
    env["DB_PATH"] = str(d1 / "a.db")
    p1 = subprocess.run([sys.executable, "backend/seed_demo.py"], capture_output=True, text=True, env=env)
    assert p1.returncode == 0, p1.stderr[-500:]
    d2 = Path(tempfile.mkdtemp())
    env["DB_PATH"] = str(d2 / "b.db")
    import sqlite3
    con = sqlite3.connect(str(d2 / "b.db"))
    con.execute("CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, child_code TEXT, status TEXT, data_json TEXT, created_at REAL, updated_at REAL)")
    con.execute("INSERT INTO plans VALUES('x','REAL-1','draft','{}',1,1)")
    con.commit()
    con.close()
    p2 = subprocess.run([sys.executable, "backend/seed_demo.py"], capture_output=True, text=True, env=env)
    assert p2.returncode != 0 and "中止" in (p2.stdout + p2.stderr), (p2.stdout + p2.stderr)[-500:]
