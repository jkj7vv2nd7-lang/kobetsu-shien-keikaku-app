"""新潟県様式の登録。実行: python backend/seed_niigata.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.seed_data import register_niigata

if __name__ == "__main__":
    r = register_niigata()
    print(f"registered {r['template_id']}: slots={r['slots']} mapping={r['mapping']}")
