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


SNIPPETS = [
    ("見通し", "予定表の提示", "1日の流れを予定表で見せ、次が見通せるようにします。切り替えの3分前に予告します。"),
    ("見通し", "手順表の活用", "やることを手順表にして1つずつ確かめます。できたらその場で称賛します。"),
    ("関わり", "仲立ちの工夫", "教師が仲立ちして関わるきっかけを作ります。難しいときは気持ちを代弁します。"),
    ("関わり", "クールダウン", "気持ちが高ぶったら、本人の合図でクールダウンスペースを使えるようにします。"),
    ("評価", "ふりかえりの言葉", "できたこと・兆しを具体的に伝え、次のめあてを本人と確認します。"),
]


def seed_snippets() -> int:
    import uuid
    db.init_db()
    n = 0
    with db.conn() as c:
        for cat, title, body in SNIPPETS:
            if c.execute("SELECT id FROM snippets WHERE category=? AND title=?", (cat, title)).fetchone():
                continue
            c.execute("INSERT INTO snippets(id,category,title,body,created_by,created_at) VALUES(?,?,?,?,?,?)",
                      (uuid.uuid4().hex[:12], cat, title, body, "seed", time.time()))
            n += 1
    return n
