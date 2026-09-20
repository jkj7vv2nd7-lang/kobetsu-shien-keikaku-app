"""設定読込 v0.8：backend/.env を環境変数に反映（既存の環境変数は優先）。

標準ライブラリのみ。`KEY=VALUE` 形式・`#` コメント・引用符に対応。
"""
from __future__ import annotations
import os
from pathlib import Path


def load_dotenv(path: str | None = None) -> None:
    p = Path(path) if path else Path(__file__).resolve().parents[1] / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("'\"")
        if k and k not in os.environ:
            os.environ[k] = v
