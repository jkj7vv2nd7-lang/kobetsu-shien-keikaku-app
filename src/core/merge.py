"""差し込みモジュール v0.1：{{field_id}} を値で置換。残存があれば例外。"""
import re

PAT = re.compile(r"\{\{(\w+)\}\}")


def merge(template_text: str, data: dict) -> str:
    missing = []

    def repl(m):
        key = m.group(1)
        if key not in data or data[key] in (None, ""):
            missing.append(key)
            return m.group(0)
        v = data[key]
        if isinstance(v, bool):
            return "確認済" if v else "未確認"
        return str(v)

    out = PAT.sub(repl, template_text)
    if missing:
        raise ValueError(f"未入力フィールド: {', '.join(sorted(set(missing)))}")
    leftover = PAT.findall(out)
    if leftover:
        raise ValueError(f"未解決プレースホルダ残存: {leftover}")
    return out
