"""動作確認用デモ（標準ライブラリのみ）。実名は扱わずサンプル値で実行。"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from core.anonymize import anonymize, assert_safe_for_llm
from core.checks import check_expression, check_consistency, check_required
from core.merge import merge

sample = {
    "child_code": "S-2026-001",
    "grade": "小4",
    "class_type": "特別支援学級",
    "profile_strengths": "図形パズルが得意。見通しが分かると集中できる。",
    "profile_needs": "急な予定変更で不安が高まる。見通しの提示が必要。",
    "guardian_wish": "友達と楽しく過ごしてほしい。",
    "child_wish": "休み時間にみんなと遊びたい。",
    "support_history": "3年：視覚支援カード導入。4年：朝の会の役割付与。",
    "related_agencies": "放課後等デイサービス、通級指導教室",
    "support_long_goal": "見通しを持って学校生活を送り、友達と関わる力を伸ばす（3年）。",
    "guidance_long_goal": "1日の流れを自分で確認し、切り替えを自分で行う。",
    "short_goal_1": "朝の会までに1日の予定を絵カードで確認できる。",
    "short_goal_2": "休み時間の約束を1つ守って遊ぶ。",
    "supports": "①予定表の視覚化 ②切替3分前予告 ③成功時の即時称賛。具体的に記録。",
    "eval_method": "12月・3月に行動観察＋担任・保護者面談で評価。",
    "conference_memo": "9月支援会議：担任・通級担当・保護者で目標合意。",
    "guardian_confirmed": True,
}

if __name__ == "__main__":
    memo = "山田太郎さんは○○小学校で頑張る様子が見られます。"
    a = anonymize(memo, child_name="山田太郎", school_name="○○小学校")
    print("匿名化:", a.text, "| 警告:", a.warnings or "なし")
    print("LLM送信前検査:", assert_safe_for_llm(a.text, ["山田太郎", "○○小学校"]) or "問題なし")

    text_all = " ".join(str(v) for v in sample.values())
    print("\n表現チェック:", check_expression(text_all) or "問題なし")
    print("整合性チェック:", check_consistency(sample) or "問題なし")
    print("必須チェック:", check_required(sample) or "問題なし")

    for name in ("support_plan.txt", "guidance_plan.txt"):
        tpl = (BASE / "templates" / "mext" / name).read_text(encoding="utf-8")
        out = merge(tpl, sample)
        dest = BASE / "templates" / "mext" / f"out_{name}"
        dest.write_text(out, encoding="utf-8")
        print(f"出力: {dest.name} OK")
