"""新潟県様式の実ファイル差し込みテスト。実行: python -m pytest backend/tests -q"""
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend"))
sys.path.insert(0, str(BASE / "src"))

from app.core import template_engine

SRC = BASE / "templates" / "niigata" / "kobetsu_niigata.xlsx"
MAP = json.loads((BASE / "templates" / "niigata" / "mapping.json").read_text(encoding="utf-8"))["mapping"]

DATA = {
    "written_date": "令和8年4月10日", "writer": "担任 山田", "child_furigana": "たなか はなこ",
    "gender": "女", "birth_date": "平成28年5月1日", "child_name": "田中 花子",
    "address": "新潟市中央区1-2-3", "guardian_name": "田中 太郎",
    "tel": "025-000-0000", "emergency": "090-0000-0000", "grade_year": "4年",
    "history": "保育園から通級を利用しました。", "life": "朝の支度を自分でしています。",
    "wish": "友だちと仲よく過ごしてほしいです。", "support_long_goal": "見通しをもって学校生活を送ります。",
    "school_support": "予定表を見せて声をかけます。", "eval_handover": "12月にふりかえりをします。",
    "family_support": "家庭でも予定表を使います。", "community_support": "地域の教室に参加します。",
    "welfare_support": "デイサービスと連絡します。", "medical_support": "病院の先生と相談します。",
    "consent_date": "令和8年4月15日", "guardian_name_confirm": "田中 太郎",
    "strengths": "絵をかくことが好きです。", "weaknesses": "急な予定の変更が苦手です。",
    "fact_1": "予定が変わると不安になります。", "goal_1": "予定表を見て動けます。",
    "method_1": "前に予告をします。", "eval_1": "行動を見て確かめます。",
}


def _val(path, sheet, cell):
    from openpyxl import load_workbook
    wb = load_workbook(path)
    return wb[sheet][cell].value


def test_niigata_merge_all_key_cells(tmp_path):
    out = tmp_path / "filled.xlsx"
    template_engine.merge_xlsx(str(SRC), str(out), DATA, MAP)
    S1, S2 = "個別の教育支援計画", "個別の指導計画"
    assert _val(out, S1, "K3") == "令和8年4月10日"          # 定型「年月日」セル
    assert _val(out, S1, "B7") == "田中 花子"
    assert _val(out, S1, "C8") == "新潟市中央区1-2-3"
    assert _val(out, S1, "E6") == "性別　女"                # ラベル一体型(append)
    assert _val(out, S1, "J6") == "平成28年5月1日"
    assert _val(out, S1, "B11") == "保育園から通級を利用しました。"
    assert _val(out, S1, "B14") == "見通しをもって学校生活を送ります。"
    assert "予定表を見せて声をかけます" in _val(out, S1, "A15")
    assert _val(out, S1, "A20") == "家庭でも予定表を使います。"
    assert _val(out, S1, "C22") == "令和8年4月15日"
    assert "田中 太郎" in _val(out, S1, "H22")
    assert _val(out, S2, "B6") == "4年"
    assert _val(out, S2, "G6") == "女"
    assert _val(out, S2, "A9") == "絵をかくことが好きです。"
    assert _val(out, S2, "F9") == "急な予定の変更が苦手です。"
    assert _val(out, S2, "B11") == "予定が変わると不安になります。"
    assert _val(out, S2, "I11") == "行動を見て確かめます。"
    assert "田中 太郎" in _val(out, S2, "F21")


def test_guide_goal_quality():
    from core.guide import check_goal_quality, HANDOVER_ITEMS, SCHEDULE
    r = check_goal_quality("最後まで席を離れず学習活動に取り組む。")
    assert any(i["rule"] == "目標の具体性" for i in r)
    r2 = check_goal_quality("予定表を見て5分間集中して取り組むことができる。")
    assert not any(i["rule"] == "目標の具体性" for i in r2)
    r3 = check_goal_quality("できないことを減らす。")
    assert any(i["rule"] == "肯定的表現" for i in r3)
    assert len(HANDOVER_ITEMS) == 7 and len(SCHEDULE) == 7


def test_plain_and_sanitize():
    from core.plain import check_plain
    from core.anonymize import sanitize_for_llm, scrub_text
    hits = [i["hit"] for i in check_plain("アセスメントの結果、手立てを講じて改善を促す。")]
    assert "アセスメント" in hits and "改善" in hits
    long_issue = check_plain("あ" * 61 + "。")
    assert any(i["rule"] == "やさしい日本語" for i in long_issue)
    clean, removed = sanitize_for_llm({"child_name": "田中 花子", "wish": "仲よく過ごす"})
    assert "child_name" not in clean and "田中 花子" in removed
    assert scrub_text("田中 花子は元気", ["田中 花子"]) == "【非表示】は元気"
