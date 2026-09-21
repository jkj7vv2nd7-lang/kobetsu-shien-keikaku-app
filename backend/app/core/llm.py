"""LLMプロバイダ抽象化 v0.4。既定mock。実接続はOpenAI互換HTTP（urllibのみ）。"""
from __future__ import annotations
import json
import os
import time
import urllib.request

PROVIDER = os.getenv("LLM_PROVIDER", "mock")

SYSTEM_PROMPT = (
    "あなたは日本の特別支援教育の計画作成補助です。守ること："
    "(1) 個人情報の復元・推測は禁止。渡された匿名情報を特定しようとしない。"
    "(2) 保護者に読まれる文書として、専門用語を避け、やさしい日本語・ですます調・短い文で書く。"
    "手順は番号で区切り、誰が・いつ・何をするかを具体的に書く。"
    "(3) 医療的断定（診断名の断定、治る、投薬の指示）はしない。"
    "(4) 差別的・否定的な断定表現を使わない。具体的事実＋成長の見通しで書く。"
)

ENDPOINTS = {
    "gemini": (os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
               os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
    "groq": (os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
             os.getenv("GROQ_API_KEY", ""), os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")),
    "ollama": (os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
               os.getenv("OLLAMA_API_KEY", "ollama"), os.getenv("OLLAMA_MODEL", "llama3.1:8b")),
}


def _post_openai_compatible(base: str, key: str, model: str, prompt: str, timeout: int = 40) -> str:
    url = base.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": model, "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}], "temperature": 0.4}).encode("utf-8")
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                j = json.loads(r.read().decode("utf-8"))
                return j["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - 429/5xx時は待って再試行
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM接続失敗: {last}")


def mock_draft(kind: str, facts: str) -> str:
    if kind == "guidance_long_goal":
        return ("（試作下書き・やさしい日本語で整えてください）\n"
                f"1年間のめあて：1日の流れを自分でたしかめて、切りかえを自分で行います。\n"
                f"今の様子：{facts[:60]}")
    if kind == "short_goal":
        return ("（試作下書き・やさしい日本語で整えてください）\n"
                "3か月のめあて：予定表を見て、次の活動に自分から移ります。\n"
                f"今の様子：{facts[:60]}")
    if kind == "wish":
        return ("（試作下書き・やさしい日本語で整えてください）\n"
                "願い：友達と仲よく過ごしたいです。できることを増やしたいです。\n"
                "本人の言葉・保護者の言葉で1〜2文に整えてください。")
    if kind == "support":
        return ("（試作下書き・やさしい日本語で整えてください）\n"
                "工夫：1. 予定表を見せる 2. 切り替え前に予告する 3. できたらすぐにほめる。\n"
                "誰が・いつ・何をするか具体的に整えてください。")
    if kind == "eval":
        return ("（試作下書き・やさしい日本語で整えてください）\n"
                "ふりかえり：行動の様子を見て確かめます。よくなった点・兆しを書きます。\n"
                "時期・方法を具体的に整えてください。")
    if kind == "summary":
        return ("（試作下書き・引継ぎメモ）\n1. 今の様子（強み・得意を含む）：…\n"
                "2. よくなったこと・成長の兆し：…\n3. 有効だった工夫と条件：…\n"
                "4. 入学・進級直後の予想と支援：…\n5. 糊しろ（4月のおさらい課題）：…\n"
                "6. 願いと今後の目標：…\n短い文・ですます調で整えてください。")
    return (f"（試作下書き）「{facts[:80]}」を、短い文・ですます調・具体的な行動で整えた文案にします。"
            "教員が必ず修正・承認してください。")


def generate(kind: str, anonymized_prompt: str, provider: str | None = None) -> dict:
    prov = (provider or PROVIDER).lower()
    if prov == "mock":
        return {"provider": "mock", "text": mock_draft(kind, anonymized_prompt), "sent_to_external": False}
    if prov not in ENDPOINTS:
        raise ValueError(f"unknown provider: {prov}")
    base, key, model = ENDPOINTS[prov]
    if not key:
        raise RuntimeError(f"{prov} のAPIキーが未設定（.env参照）。LLM_PROVIDER=mock で試作継続可。")
    text = _post_openai_compatible(base, key, model, anonymized_prompt)
    return {"provider": prov, "model": model, "text": text, "sent_to_external": True}
