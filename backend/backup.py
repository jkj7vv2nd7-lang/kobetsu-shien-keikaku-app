"""バックアップ/リストア v0.9（標準ライブラリのみ）。

対象：backend/data 全体（DB＋様式原本＋映射＋出力物）。
実行：python backend/backup.py backup [--out DIR]
      python backend/backup.py restore <zip> --force
"""
import shutil
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
from app import config as _config  # noqa: E402
_config.load_dotenv()  # noqa: E402
from app import db  # noqa: E402

DATA = BACKEND / "data"
BACKUP_DIR = BACKEND / "backups"


def backup(out_dir: str | None = None) -> Path:
    db.init_db()
    dest = Path(out_dir) if out_dir else BACKUP_DIR
    dest.mkdir(parents=True, exist_ok=True)
    name = f"backup_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    # DBのWAL等を避けるため一時コピーして固める
    tmp = dest / f".tmp_{name}"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(DATA, tmp, ignore=shutil.ignore_patterns("*.wal", "*.shm", "*.journal"))
    zpath = dest / name
    shutil.make_archive(str(zpath.with_suffix("")), "zip", root_dir=tmp.parent, base_dir=tmp.name)
    shutil.rmtree(tmp)
    print(f"backup: {zpath} ({zpath.stat().st_size // 1024} KB)")
    return zpath


def restore(zpath: str, force: bool = False) -> Path:
    import zipfile
    z = Path(zpath)
    if not z.exists():
        raise FileNotFoundError(z)
    if not force:
        raise RuntimeError("上書き復元には --force が必要です")
    if not zipfile.is_zipfile(z):
        raise RuntimeError("zipではありません")
    tmp = BACKUP_DIR / ".restore_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
        if any(n.startswith("/") or ".." in n for n in names):
            raise RuntimeError("不正なzip内容")
        zf.extractall(tmp)
    inner = list(tmp.iterdir())
    src = inner[0] if len(inner) == 1 and inner[0].is_dir() else tmp
    if not (src / "app.db").exists() and not (src / "templates").exists():
        raise RuntimeError("バックアップ内容が不正（app.db/templatesなし）")
    bak = BACKEND / f"data.prev_{time.strftime('%Y%m%d_%H%M%S')}"
    if DATA.exists():
        DATA.rename(bak)
        print(f"現行dataを退避: {bak}")
    shutil.move(str(src), str(DATA))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"restore: {z} -> {DATA}")
    return DATA


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("backup", "restore"):
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "backup":
        out = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--out" else None
        backup(out)
    else:
        if len(sys.argv) < 3:
            print("usage: backup.py restore <zip> --force")
            sys.exit(1)
        restore(sys.argv[2], force="--force" in sys.argv)
