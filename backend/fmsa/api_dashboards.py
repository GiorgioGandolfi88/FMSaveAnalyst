"""API routes: pre-built dashboards."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from fmsa.config import SettingsStore
from fmsa.dashboards import (
    DashboardError,
    delete_dashboard,
    export_dashboard,
    hidden_builtins,
    load_dashboards,
    param_options,
    restore_dashboard,
    run_dashboard,
    save_dashboard,
    validate_dashboard,
)
from fmsa.query.export import ExportFormat
from fmsa.query.session import QueryError, open_career


class DashboardRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class DashboardSave(BaseModel):
    dashboard: dict[str, Any]
    old_id: str | None = None


class DashboardPreview(DashboardRequest):
    dashboard: dict[str, Any]


class DashboardExport(DashboardRequest):
    format: ExportFormat = "csv_excel"
    path: str | None = None


def create_router(store: SettingsStore, data_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api/dashboards")
    user_dir = data_dir / "dashboards"

    def career() -> Path:
        path = store.get().last_career
        if not path or not Path(path).is_file():
            raise HTTPException(409, "no career is open")
        return Path(path)

    def dashboard(dashboard_id: str) -> dict[str, Any]:
        d = load_dashboards(user_dir).get(dashboard_id)
        if d is None:
            raise HTTPException(404, f"unknown dashboard {dashboard_id}")
        return d

    def today(session: Any) -> str | None:
        try:
            rows = session.query("SELECT max(game_date) FROM _imports WHERE status = 'ok'").rows
            return rows[0][0] if rows else None
        except QueryError:
            return None

    @router.get("")
    def list_dashboards() -> list[dict[str, Any]]:
        return [
            {
                k: d.get(k)
                for k in ("id", "title", "description", "params", "source", "order", "builtin")
            }
            | {"widgets": len(d["widgets"])}
            for d in load_dashboards(user_dir).values()
        ]

    @router.get("/params")
    def params() -> dict[str, Any]:
        with open_career(career(), store.get().masking) as session:
            return param_options(session)

    @router.get("/hidden")
    def hidden() -> list[dict[str, Any]]:
        """Built-in dashboards the user deleted (they can be restored)."""
        builtin = load_dashboards(None)
        return [
            {"id": k, "title": builtin[k]["title"]}
            for k in sorted(hidden_builtins(user_dir))
            if k in builtin and k not in load_dashboards(user_dir)
        ]

    @router.post("/preview")
    def preview(body: DashboardPreview) -> dict[str, Any]:
        try:
            d = validate_dashboard(body.dashboard)
        except DashboardError as exc:
            raise HTTPException(422, str(exc)) from exc
        with open_career(career(), store.get().masking) as session:
            return {"widgets": run_dashboard(session, d, body.params, today(session))}

    @router.put("/{dashboard_id}")
    def save(dashboard_id: str, body: DashboardSave) -> dict[str, Any]:
        if body.dashboard.get("id") != dashboard_id:
            raise HTTPException(422, "the dashboard id does not match the URL")
        try:
            return save_dashboard(user_dir, body.dashboard, body.old_id)
        except DashboardError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.delete("/{dashboard_id}")
    def delete(dashboard_id: str) -> dict[str, Any]:
        dashboard(dashboard_id)
        delete_dashboard(user_dir, dashboard_id)
        return {"deleted": dashboard_id}

    @router.post("/{dashboard_id}/restore")
    def restore(dashboard_id: str) -> dict[str, Any]:
        try:
            restore_dashboard(user_dir, dashboard_id)
        except DashboardError as exc:
            raise HTTPException(404, str(exc)) from exc
        return dashboard(dashboard_id)

    @router.get("/{dashboard_id}")
    def get_dashboard(dashboard_id: str) -> dict[str, Any]:
        return dashboard(dashboard_id)

    @router.post("/{dashboard_id}/data")
    def data(dashboard_id: str, body: DashboardRequest) -> dict[str, Any]:
        d = dashboard(dashboard_id)
        with open_career(career(), store.get().masking) as session:
            return {"widgets": run_dashboard(session, d, body.params, today(session))}

    @router.post("/{dashboard_id}/export", response_model=None)
    def export(dashboard_id: str, body: DashboardExport) -> dict[str, Any] | Response:
        d = dashboard(dashboard_id)
        with open_career(career(), store.get().masking) as session:
            payload = export_dashboard(session, d, body.params, today(session), body.format)
        if body.path:
            target = Path(body.path)
            target.write_bytes(payload)
            return {"path": str(target), "bytes": len(payload)}
        return Response(
            payload,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{dashboard_id}.zip"'},
        )

    return router
