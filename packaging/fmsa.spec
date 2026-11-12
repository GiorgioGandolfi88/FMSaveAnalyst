# PyInstaller spec: portable one-folder build of FMSaveAnalyst.
# Run through scripts/build.py (it builds the frontend first and zips the result).
# ruff: noqa
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent
VERSION_FILE = ROOT / "build" / "version_info.txt"  # written by scripts/build.py

datas = [
    (str(ROOT / "frontend" / "dist"), "dist"),
    (str(ROOT / "backend" / "fmsa" / "dashboards" / "defs"), "fmsa/dashboards/defs"),
]
binaries = []
hiddenimports = collect_submodules("uvicorn") + collect_submodules("fmsa")

# fmsave loads its per-build layouts dynamically; backports.zstd is a native extension.
# keyring discovers its backends through package metadata (Windows Credential Manager).
datas += copy_metadata("keyring")
hiddenimports += collect_submodules("keyring.backends") + ["win32ctypes.core"]

for package in ("fmsave", "backports.zstd", "webview"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pandas", "polars", "numpy", "matplotlib", "pytest", "psutil"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FMSaveAnalyst",
    console=False,
    upx=False,
    version=str(VERSION_FILE) if VERSION_FILE.is_file() else None,
    disable_windowed_traceback=False,
)

coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="FMSaveAnalyst")
