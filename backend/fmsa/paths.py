"""Where the application lives and where it keeps its data.

- app_dir: folder of FMSaveAnalyst.exe (frozen) or the repository root (development).
  It holds `reference/` and, in portable mode, `data/`.
- bundle_dir: read-only resources bundled into the executable (the built frontend).
- data_dir: settings, logs and, by default, the career databases.
  Portable mode (a `portable.flag` file next to the exe) keeps it in `<app_dir>/data`,
  otherwise it is `%APPDATA%/FMSaveAnalyst`.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "FMSaveAnalyst"
PORTABLE_FLAG = "portable.flag"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def default_app_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def default_bundle_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", default_app_dir()))
    return default_app_dir() / "frontend"


@dataclass(frozen=True, slots=True)
class AppPaths:
    app_dir: Path
    bundle_dir: Path
    data_dir: Path
    portable: bool

    @property
    def settings_file(self) -> Path:
        return self.data_dir / "settings.json"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def default_careers_dir(self) -> Path:
        return self.data_dir / "careers"

    @property
    def default_reference_db(self) -> Path:
        return self.app_dir / "reference" / "fm_reference.sqlite"

    @property
    def frontend_dir(self) -> Path:
        return self.bundle_dir / "dist"

    def ensure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def resolve(cls, app_dir: Path | None = None, bundle_dir: Path | None = None) -> AppPaths:
        app = app_dir or default_app_dir()
        bundle = bundle_dir or default_bundle_dir()
        portable = (app / PORTABLE_FLAG).exists()
        if portable:
            data = app / "data"
        else:
            appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
            data = Path(appdata) / APP_NAME
        return cls(app_dir=app, bundle_dir=bundle, data_dir=data, portable=portable)


def default_fm_save_dirs() -> list[Path]:
    """Usual Football Manager save folders that exist on this PC (FM27 first)."""
    docs = Path.home() / "Documents" / "Sports Interactive"
    candidates = [docs / f"Football Manager {v}" / "games" for v in ("27", "26", "2027", "2026")]
    return [c for c in candidates if c.is_dir()]
