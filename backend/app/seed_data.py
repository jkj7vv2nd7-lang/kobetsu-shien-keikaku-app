"""初期データ登録（スクリプト・テスト共通）。"""
from __future__ import annotations
import json
import shutil
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "src"))

from app import config as _config  # noqa: E402
_config.load_dotenv()  # noqa: E402
from app import db, auth  # noqa: E402
from app.core import template_engine  # noqa: E402

TID = "niigata01"


def register_niigata(tid: str = TID) -> dict:
    db.init_db()
    auth.seed()
    src = REPO / "templates" / "niigata" / "kobetsu_niigata.xlsx"
    mapping = json.loads((REPO / "templates" / "niigata" / "mapping.json").read_text(encoding="utf-8"))["mapping"]
    d = BACKEND / "data" / "templates" / tid
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, d / "original.xlsx")
    slots = template_engine.extract_xlsx(str(d / "original.xlsx"))
    (d / "slots.json").write_text(json.dumps(slots, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    with db.conn() as c:
        c.execute("DELETE FROM templates WHERE id=?", (tid,))
        c.execute("INSERT INTO templates(id,filename,suffix,label,mapping_json,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                  (tid, "kobetsu_niigata.xlsx", ".xlsx", "新潟県様式（参考・個別の教育支援計画＋指導計画）",
                   json.dumps(mapping, ensure_ascii=False), "seed", time.time()))
    return {"template_id": tid, "slots": len(slots), "mapping": len(mapping)}
