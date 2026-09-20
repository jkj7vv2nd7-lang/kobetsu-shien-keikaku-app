"""糊しろ提案 v0.7（規則ベース・外部送信なし）

ハンドブックp9：新年度は前年度のおさらい・得意なことから始め、
信頼関係を築く「糊しろ」をつくる。計画データから4月最初の課題案を3件まで作る。
"""
from __future__ import annotations


def propose_norishiro(data: dict) -> list:
    d = data or {}
    out = []
    strengths = (d.get("strengths") or d.get("profile_strengths") or "").strip()
    if strengths:
        out.append({"title": "得意なことからスタート",
                    "body": f"4月の最初は、得意な「{strengths[:40]}」から取り組みます。",
                    "reason": "得意なことは興味を引き出し、称賛のきっかけになります（ハンドブックp9）。"})
    eff = (d.get("effective_supports") or d.get("supports") or "").strip()
    if eff:
        out.append({"title": "うまくいった工夫を続ける",
                    "body": f"4月も続ける工夫：{eff[:60]}",
                    "reason": "環境が変わっても、できる条件をそろえると安心できます。"})
    short = (d.get("short_goal_1") or d.get("goal_1") or "").strip()
    if short:
        out.append({"title": "最初の1週間は小さく始める",
                    "body": f"最初の1週間は「{short[:40]}」のうち、できそうな部分だけにします。",
                    "reason": "目標の細分化で成功体験を積み、無理なく進めます（ハンドブックp7）。"})
    if len(out) < 2:
        out.append({"title": "見通しを示して安心させる",
                    "body": "1日の流れを予定表で見せ、新しい先生・教室の見通しをもてるようにします。",
                    "reason": "見通しがもてると不安が軽くなり、信頼関係の土台になります。"})
    return out[:3]
