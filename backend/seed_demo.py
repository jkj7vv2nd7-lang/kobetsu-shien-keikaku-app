"""体験用デモデータ投入 v0.10。実行: python backend/seed_demo.py

架空の児童2件（DEMO-001/002）を作成。氏名欄も架空名と明示。
冪等性あり（再実行で重複作成しない）。実データ投入前に削除すること。
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config as _config  # noqa: E402
_config.load_dotenv()  # noqa: E402
from app import db, auth  # noqa: E402
from app.routers.plans import validate_plan  # noqa: E402

BASE_DATA = {
    "profile_strengths": "電車の絵を細かい部分まで丁寧に仕上げる。乗り物図鑑が好き。",
    "profile_needs": "大きな集団や騒がしい場所が苦手。見通しがあると安心する。",
    "child_wish": "先生や友達にあいさつをがんばりたい。",
    "guardian_wish": "友達と仲よくしながら、落ち着いて学校生活を送ってほしい。",
    "support_history": "2年：視覚支援カード導入。3年：朝の会の役割付与。",
    "related_agencies": "放課後デイサービス、通級指導教室",
    "support_long_goal": "友達との関わりを増やしながら、自分の気持ちを言葉で伝えられる。",
    "guidance_long_goal": "1日の流れを自分で確認し、切り替えを自分で行う。",
    "short_goal_1": "朝の会までに予定表を見て5分で支度する。",
    "short_goal_2": "休み時間の約束を1つ守って遊ぶ。",
    "supports": "予定表の視覚化、切替3分前予告、成功時の即時称賛。",
    "eval_method": "学期末に行動観察と面談でふりかえる。",
    "conference_memo": "4月支援会議：担任・通級担当・保護者で目標合意。",
    "guardian_confirmed": True,
    "written_date": "令和8年4月10日",
    "writer": "担任（デモ）",
    "child_name": "デモ 花子（架空）",
    "child_furigana": "でも はなこ",
    "gender": "女",
    "history": "保育園から通級を利用（架空事例）。",
    "life": "朝の支度を手順表で自分で行う。",
    "wish": "友達と仲よく過ごしたい。",
    "school_support": "遊びや学習で関わる機会を作り、教師が仲立ちする。",
    "eval_handover": "学期末にふりかえる。",
    "family_support": "家庭でも予定表を使う。",
    "community_support": "水泳教室に週1回参加。",
    "welfare_support": "発達支援センターと連携。",
    "medical_support": "定期受診で支援方針を確認。",
    "consent_date": "令和8年5月20日",
    "guardian_name_confirm": "デモ 太郎（架空）",
    "strengths": "電車の絵、工作が丁寧。",
    "weaknesses": "急な予定変更が苦手。クールダウンの声かけで対応。",
    "fact_1": "予定が変わると不安になり、その場を離れることがある。",
    "goal_1": "予定表を見て次の活動に自分から移ることができる。",
    "method_1": "事前に予告し、手順表で見通しを示す。できたら称賛する。",
    "eval_1": "行動観察と連絡帳で確認する。",
    "handover_to": "4年1組担任",
    "handover_consent": True,
    "handover_consent_date": "令和8年3月20日",
    "start_ease": "4月最初は得意な絵の時間から始める。",
    "effective_supports": "手順表と予告があると切り替えができる。",
}

DEMOS = [
    ("DEMO-001", "小3", "特別支援学級", dict(BASE_DATA)),
    ("DEMO-002", "小4", "通級", dict(BASE_DATA, child_code="DEMO-002", grade="小4",
                                     child_name="デモ 次郎（架空）", grade_year="4年")),
]


def create_demo_plans() -> list:
    db.init_db()
    auth.seed()
    ids = []
    with db.conn() as c:
        for code, grade, ctype, data in DEMOS:
            data = dict(data, child_code=code, grade=grade, class_type=ctype)
            row = c.execute("SELECT id FROM plans WHERE child_code=?", (code,)).fetchone()
            if row:
                ids.append(dict(row)["id"])
                continue
            import uuid
            pid = "demo_" + code.lower().replace("-", "")
            now = time.time()
            c.execute("""INSERT INTO plans(id,child_code,school,grade,class_type,status,data_json,
                         created_by,updated_by,guardian_confirmed,guardian_date,created_at,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (pid, code, "デモ学校", grade, ctype, "draft",
                       json.dumps(data, ensure_ascii=False), "teacher", "teacher",
                       1, "令和8年5月20日", now, now))
            ids.append(pid)
    # 検証結果つきで返す
    out = []
    with db.conn() as c:
        for pid in ids:
            r = c.execute("SELECT data_json FROM plans WHERE id=?", (pid,)).fetchone()
            v = validate_plan(json.loads(dict(r)["data_json"]))
            out.append({"id": pid, "blocked": v["blocked"], "issues": len(v["issues"])})
    return out


if __name__ == "__main__":
    for r in create_demo_plans():
        print(r["id"], "blocked:" + str(r["blocked"]), f"issues:{r['issues']}")
