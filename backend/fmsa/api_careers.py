"""API routes: careers, save files, continuity checks and import jobs."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from fmsa.careers import (
    JobRunner,
    career_file_name,
    import_history,
    import_log,
    list_careers,
    list_saves,
    read_summary,
)
from fmsa.config import SettingsStore
from fmsa.ingest.continuity import check_continuity

MAX_RECENT = 10


class NewCareer(BaseModel):
    name: str
    save_path: str


class CareerSave(BaseModel):
    career_path: str
    save_path: str


class CareerPath(BaseModel):
    path: str


def _existing_file(path: str, what: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_file():
        raise HTTPException(404, f"{what} not found: {path}")
    return p


def create_router(store: SettingsStore, jobs: JobRunner) -> APIRouter:
    router = APIRouter(prefix="/api")

    def reference_db() -> Path | None:
        p = Path(store.get().reference_db)
        return p if p.is_file() else None

    def remember(path: Path) -> None:
        s = store.get()
        p = str(path)
        recent = [p, *(r for r in s.recent_careers if r.lower() != p.lower())][:MAX_RECENT]
        store.save(s.model_copy(update={"last_career": p, "recent_careers": recent}))

    @router.get("/saves")
    def saves(folder: str = "") -> dict[str, Any]:
        target = Path(folder or store.get().fm_save_dir)
        return {"folder": str(target), "saves": [asdict(s) for s in list_saves(target)]}

    @router.get("/careers")
    def careers() -> list[dict[str, Any]]:
        s = store.get()
        return [asdict(c) for c in list_careers(Path(s.careers_dir), s.recent_careers)]

    @router.get("/careers/detail")
    def career_detail(path: str) -> dict[str, Any]:
        p = _existing_file(path, "career")
        return {"summary": asdict(read_summary(p)), "imports": import_history(p)}

    @router.get("/careers/import-log")
    def career_import_log(path: str, import_id: int) -> dict[str, Any]:
        return import_log(_existing_file(path, "career"), import_id)

    @router.post("/careers")
    def create_career(body: NewCareer) -> dict[str, Any]:
        save = _existing_file(body.save_path, "save")
        try:
            file_name = career_file_name(body.name)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        target = Path(store.get().careers_dir) / file_name
        if target.exists():
            raise HTTPException(409, f"a career file named {file_name} already exists")
        try:
            job = jobs.start("create", target, save, reference_db(), career_name=body.name.strip())
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        remember(target)
        return job.to_dict()

    @router.post("/careers/open")
    def open_career(body: CareerPath) -> dict[str, Any]:
        p = _existing_file(body.path, "career")
        remember(p)
        return asdict(read_summary(p))

    @router.post("/careers/check")
    def check(body: CareerSave) -> dict[str, Any]:
        career = _existing_file(body.career_path, "career")
        save = _existing_file(body.save_path, "save")
        return check_continuity(career, save).to_dict()

    @router.post("/careers/import")
    def import_more(body: CareerSave) -> dict[str, Any]:
        career = _existing_file(body.career_path, "career")
        save = _existing_file(body.save_path, "save")
        try:
            job = jobs.start("update", career, save, reference_db())
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return job.to_dict()

    @router.get("/jobs/{job_id}")
    def job_status(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "unknown job")
        return job.to_dict()

    return router
