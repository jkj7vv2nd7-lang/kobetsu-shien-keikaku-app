"""匿名化モジュール v0.4（標準ライブラリのみ）

実名・学校名などをLLM送信前に仮名化する。対応表は送信しない。
PII項目の値は sanitize_for_llm で一括除去できる。
"""
import re
from dataclasses import dataclass

# field_master.json で pii:true の項目ID（LLM送信対象外）
PII_FIELDS = frozenset({
    "child_name", "child_furigana", "birth_date", "address", "address2",
    "guardian_furigana", "guardian_name", "tel", "emergency",
    "guardian_name_confirm",
})


@dataclass
class AnonymizeResult:
    text: str
    mapping: dict
    warnings: list


def anonymize(text: str, child_name: str = "", school_name: str = "") -> AnonymizeResult:
    mapping: dict = {}
    warnings: list = []
    out = text or ""
    if child_name:
        mapping[child_name] = "【児童A】"
        out = out.replace(child_name, "【児童A】")
    if school_name:
        mapping[school_name] = "【学校X】"
        out = out.replace(school_name, "【学校X】")
    # 日付の年を残しつつ簡易検出（例：2026年9月20日は保持、個人文脈では問題なし）
    # 電話・住所らしきものを警告
    if re.search(r"\d{2,4}-\d{2,4}-\d{3,4}", out):
        warnings.append("電話番号らしき文字列が含まれています。削除してください。")
    if re.search(r"(住所|自宅|携帯)", out):
        warnings.append("住所・連絡先らしき語句があります。入力欄分離を推奨。")
    # 残存チェック：mapping外の人名らしき敬称
    return AnonymizeResult(text=out, mapping=mapping, warnings=warnings)


def assert_safe_for_llm(text: str, real_names: list) -> list:
    """LLM送信直前チェック。実名残存があれば警告リストを返す。"""
    issues = []
    for n in real_names:
        if n and n in text:
            issues.append(f"実名残存: {n[:1]}*** を除去してください")
    if "{{" in text and "}}" in text:
        pass  # テンプレ変数は許容
    return issues


def sanitize_for_llm(data: dict) -> tuple:
    """計画データからPII値を除去したAI用dictと除去項目リストを返す。

    値が本文中に埋め込まれている場合も置換できるよう、除去値リストを返す。
    """
    clean: dict = {}
    removed: list = []
    for k, v in (data or {}).items():
        if k in PII_FIELDS:
            if isinstance(v, str) and v.strip():
                removed.append(v.strip())
            continue
        clean[k] = v
    return clean, removed


def scrub_text(text: str, secrets: list) -> str:
    """本文中のPII値を【非表示】に置換する。"""
    out = text or ""
    for s in sorted(set(secrets), key=len, reverse=True):
        if s and len(s) >= 2:
            out = out.replace(s, "【非表示】")
    return out
