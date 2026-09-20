"""厳密チェックモジュール v0.1（標準ライブラリのみ）"""
import json
from pathlib import Path

NG_PATTERNS = [
    "劣っている", "異常", "普通じゃない", "問題児", "治らない",
    "無理", "できない子", "ダメ",
]
VAGUE_PATTERNS = [
    "頑張る", "見守る", "適宜", "なんとなく", "しっかり",
]
MEDICAL_ASSERT = ["診断", "障害である", "治る", "投薬すべき"]


def check_expression(text: str) -> list:
    issues = []
    for p in NG_PATTERNS:
        if p in text:
            issues.append({"level": "error", "rule": "NG表現", "hit": p,
                           "msg": f"断定的・否定的表現「{p}」を見直してください（具体的事実＋配慮表現へ）。"})
    for p in VAGUE_PATTERNS:
        if p in text:
            issues.append({"level": "warn", "rule": "曖昧表現", "hit": p,
                           "msg": f"「{p}」は誰が・いつ・何を・どの程度かを具体化してください。"})
    for p in MEDICAL_ASSERT:
        if p in text:
            issues.append({"level": "warn", "rule": "医療断定注意", "hit": p,
                           "msg": f"医療的断定「{p}」は医師・専門機関の所見引用か確認し、断定を避けてください。"})
    return issues


def check_consistency(data: dict) -> list:
    """長期目標と短期目標・手立て・評価の対応を簡易検査。"""
    issues = []
    long_goal = (data.get("guidance_long_goal") or "") + (data.get("support_long_goal") or "")
    shorts = [data.get("short_goal_1", ""), data.get("short_goal_2", "")]
    supports = data.get("supports", "")
    eval_method = data.get("eval_method", "")
    if not long_goal.strip():
        issues.append({"level": "error", "rule": "必須", "msg": "長期目標が未入力です。"})
    if not any(s.strip() for s in shorts):
        issues.append({"level": "error", "rule": "必須", "msg": "短期目標が未入力です。"})
    if supports.strip() == "":
        issues.append({"level": "error", "rule": "必須", "msg": "具体的支援・手立てが未入力です。"})
    if eval_method.strip() == "":
        issues.append({"level": "error", "rule": "必須", "msg": "評価方法・時期が未入力です。"})
    # 簡易：短期目標と長期・手立てで内容語の重なりを見る（助詞・記号のみ一致は無視）
    if long_goal and shorts[0]:
        import re as _re
        def _toks(s):
            return {t for t in _re.findall(r"[一-龯々〆ヵヶぁ-んァ-ヶーa-zA-Z0-9]{2,}", s)}
        st, lt = _toks(shorts[0]), _toks(long_goal) | _toks(supports)
        # 「できる」「行う」等の汎用語だけの一致は弱いので除外
        generic = {"できる", "行う", "行い", "する", "なる", "具体", "的", "記録"}
        if not ((st - generic) & (lt - generic)):
            issues.append({"level": "info", "rule": "整合性ヒント",
                           "msg": "短期目標と長期目標・手立てで共通キーワードが見当たりません。対応関係を一文添えると審査・引継ぎが容易です。（例：長期○○のため短期××）"})
    if not data.get("guardian_confirmed"):
        issues.append({"level": "error", "rule": "承認", "msg": "保護者確認フラグが未設定です。印刷前に確認してください。"})
    return issues


def check_required(data: dict, schema_path: str = "src/schema/field_master.json") -> list:
    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        # 実行ディレクトリ依存のフォールバック
        base = Path(__file__).resolve().parents[2]
        schema = json.loads((base / schema_path).read_text(encoding="utf-8"))
    issues = []
    for f in schema["fields"]:
        if f.get("required"):
            v = data.get(f["id"])
            if v is None or (isinstance(v, str) and not v.strip()) or v is False and f["id"] != "guardian_confirmed":
                issues.append({"level": "error", "rule": "必須", "msg": f"{f['label']}（{f['id']}）が未入力です。"})
    return issues
