"""やさしい日本語チェック v0.4（標準ライブラリのみ）

保護者に読んでいただく文書用。専門用語の言い換え提案＋長文検出。
文面の自動書き換えはしない（教員の判断を残す）。
"""
import re

# 専門用語 → 言い換え案（見つかった語のまま使わず、具体例に置き換える指針）
JARGON = {
    "アセスメント": "お子さんの様子をくわしく見ること",
    "実態把握": "ふだんの様子",
    "療育": "発達のサポート・練習",
    "自立活動": "自分でできることをふやす学習",
    "通級": "通級指導教室（ことばや気持ちの教室）",
    "SST": "友だちとの関わりの練習",
    "合理的配慮": "学びやすくするための工夫",
    "実行機能": "段取りをする力",
    "ワーキングメモリ": "覚えたことを使って考える力",
    "感覚過敏": "音や光などが気になりやすいこと",
    "こだわり": "いつもと同じやり方だと安心できること",
    "パニック": "気持ちが高ぶって落ち着けなくなること",
    "問題行動": "こまっている行動・様子",
    "逸脱": "きまりとちがう行動",
    "改善": "よくなる・よくする",
    "促す": "声をかけて手伝う",
    "変容": "変化・成長",
    "所見": "様子",
    "課題": "がんばるポイント",
    "手立て": "工夫・やり方",
    "評価": "ふりかえり",
    "引継ぎ": "次の先生への申送り",
    "関係機関": "関わる場所（病院・福祉など）",
    "医療機関": "病院",
    "放課後等デイサービス": "放課後の教室（デイサービス）",
    "就学": "入学",
    "交流及び共同学習": "いっしょに学ぶ時間",
    "特別支援": "一人ひとりに合わせた応援",
    "障害": "困りごと・特性（文脈に応じて具体的に）",
    "診断": "お医者さんの見立て",
    "投薬": "お薬",
    "集団適応": "みんなの中での過ごし方",
    "規範意識": "きまりを守ろうとする気持ち",
    "自己肯定感": "自分は大丈夫と思える気持ち",
}

LONG_SENTENCE = 60


def check_plain(text: str) -> list:
    """やさしい日本語の観点で issues を返す。"""
    issues = []
    for term, alt in JARGON.items():
        if term in (text or ""):
            # 「障害」は「障害のある」等の定型・法令文脈ではinfo止まり
            level = "info" if term == "障害" else "warn"
            issues.append({"level": level, "rule": "やさしい日本語", "hit": term,
                           "msg": f"「{term}」は保護者に伝わりにくい場合があります。例：「{alt}」など具体的な言い方を検討してください。"})
    for s in re.split(r"[。\n]", text or ""):
        s = s.strip()
        if len(s) > LONG_SENTENCE:
            issues.append({"level": "warn", "rule": "やさしい日本語", "hit": s[:20] + "…",
                           "msg": f"1文が{len(s)}字と長めです。2文以上に分け、短く区切ってください。（目安{LONG_SENTENCE}字）"})
            break  # 長文は最初の1件だけ指摘（ noisy 防止）
    return issues


def propose_plain(text: str) -> dict:
    """専門用語を言い換え案に置換した修正案を作る（意味保証なし・教員確認用）。

    戻り値：{"rewritten": str, "applied": [{"from","to"}]}。
    長文の自動分割はしない（意味が変わる恐れがあるため指摘のみ）。
    """
    out = text or ""
    applied = []
    # 長い定型句を先に保護（部分置換の重複を防ぐ）
    protected = {"通級指導教室": "\ue000"}
    for phrase, mask in protected.items():
        out = out.replace(phrase, mask)
    for term, alt in JARGON.items():
        if term == "障害":
            continue  # 法令・定型文脈が多いため自動置換しない
        if term in out:
            # 例示的な語（通級等）は初出のみ注記付きで置換
            out = out.replace(term, alt)
            applied.append({"from": term, "to": alt})
    for phrase, mask in protected.items():
        out = out.replace(mask, phrase)
    return {"rewritten": out, "applied": applied}


PLAIN_GUIDE = (
    "保護者向けの文章は、専門用語を避け、短い文・ですます調で書く。"
    "手順は番号で区切り、誰が・いつ・何をするかを具体的に書く。"
)
