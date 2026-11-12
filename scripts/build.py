"""Build the portable Windows release.

    python scripts/build.py              frontend + exe + zip
    python scripts/build.py --skip-frontend

Output:
    dist/FMSaveAnalyst/                       the portable folder (FMSaveAnalyst.exe, reference/)
    dist/FMSaveAnalyst-<version>-win64.zip    what gets attached to the GitHub release
    dist/FMSaveAnalyst-<version>-win64.zip.sha256
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
APP = DIST / "FMSaveAnalyst"


def version() -> str:
    text = (ROOT / "backend" / "fmsa" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("version not found in backend/fmsa/__init__.py")
    return match.group(1)


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == "win32")


def build_frontend() -> None:
    frontend = ROOT / "frontend"
    run(["npm", "ci"], frontend)
    run(["npm", "run", "build"], frontend)


def build_exe() -> None:
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        raise SystemExit("frontend/dist is missing: build the frontend first")
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST),
            "--workpath",
            str(ROOT / "build"),
            str(ROOT / "packaging" / "fmsa.spec"),
        ],
        ROOT,
    )


def build_reference_db() -> None:
    run([sys.executable, str(ROOT / "reference" / "build_reference.py")], ROOT)


def add_portable_files() -> None:
    ref_src = ROOT / "reference"
    ref_dst = APP / "reference"
    ref_dst.mkdir(exist_ok=True)
    for f in ref_src.glob("*"):
        if f.is_file() and f.suffix in {".sqlite", ".md"}:
            shutil.copy2(f, ref_dst / f.name)
    shutil.copy2(ROOT / "packaging" / "LEGGIMI.txt", APP / "LEGGIMI.txt")


def make_zip(ver: str) -> Path:
    archive = DIST / f"FMSaveAnalyst-{ver}-win64.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(APP.rglob("*")):
            if f.is_file():
                z.write(f, Path("FMSaveAnalyst") / f.relative_to(APP))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + ".sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-frontend", action="store_true")
    args = parser.parse_args()
    ver = version()
    if not args.skip_frontend:
        build_frontend()
    build_reference_db()
    build_exe()
    add_portable_files()
    archive = make_zip(ver)
    size = archive.stat().st_size / 2**20
    print(f"Built {archive.relative_to(ROOT)} ({size:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
