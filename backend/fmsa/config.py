"""User settings, stored as JSON in the data folder.

API keys are never stored here: they go to the Windows Credential Manager (Step 8).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from fmsa.paths import AppPaths, default_fm_save_dirs

log = logging.getLogger(__name__)

Language = Literal["it", "en"]
AiProvider = Literal["none", "anthropic", "openai", "gemini"]


class MaskingSettings(BaseModel):
    """Which spoiler data are hidden everywhere (grids, SQL, dashboards, AI)."""

    potential_ability: bool = True
    current_ability: bool = False
    hidden_attributes: bool = False
    personality: bool = False
    extra_columns: list[str] = Field(default_factory=list)


class AiSettings(BaseModel):
    provider: AiProvider = "none"
    model: str = ""
    confirm_before_send: bool = True


class Settings(BaseModel):
    schema_version: int = 1
    language: Language = "it"
    fm_save_dir: str = ""
    careers_dir: str = ""
    reference_db: str = ""
    last_career: str = ""
    recent_careers: list[str] = Field(default_factory=list)
    check_updates: bool = True
    masking: MaskingSettings = Field(default_factory=MaskingSettings)
    ai: AiSettings = Field(default_factory=AiSettings)

    def with_defaults(self, paths: AppPaths) -> Settings:
        """Fill empty path settings with the defaults for this installation."""
        update: dict[str, str] = {}
        if not self.careers_dir:
            update["careers_dir"] = str(paths.default_careers_dir)
        if not self.reference_db:
            update["reference_db"] = str(paths.default_reference_db)
        if not self.fm_save_dir:
            found = default_fm_save_dirs()
            if found:
                update["fm_save_dir"] = str(found[0])
        return self.model_copy(update=update) if update else self


class SettingsStore:
    """Thread-safe load/save of the settings file (atomic writes)."""

    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths
        self._lock = threading.Lock()
        self._settings = self._load()

    @property
    def path(self) -> Path:
        return self._paths.settings_file

    def _load(self) -> Settings:
        file = self.path
        if file.exists():
            try:
                raw = json.loads(file.read_text(encoding="utf-8"))
                return Settings.model_validate(raw).with_defaults(self._paths)
            except (OSError, ValueError, ValidationError):
                backup = file.with_suffix(".invalid.json")
                log.exception("Invalid settings file, keeping a copy in %s", backup)
                with contextlib.suppress(OSError):
                    os.replace(file, backup)
        return Settings().with_defaults(self._paths)

    def get(self) -> Settings:
        with self._lock:
            return self._settings

    def save(self, settings: Settings) -> Settings:
        with self._lock:
            settings = settings.with_defaults(self._paths)
            file = self.path
            file.parent.mkdir(parents=True, exist_ok=True)
            tmp = file.with_suffix(".tmp")
            tmp.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
            os.replace(tmp, file)
            self._settings = settings
            return settings
