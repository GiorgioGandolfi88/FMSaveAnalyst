"""Local HTTP API + static frontend, bound to 127.0.0.1 only.

Every /api request must carry the per-run session token in the X-FMSA-Token header, so other
programs or web pages on the PC cannot query the local server. The Host header is restricted to
loopback names to block DNS-rebinding.
"""

from __future__ import annotations

import hmac
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from fmsa import __version__, api_ai, api_dashboards, api_query
from fmsa.api_careers import create_router
from fmsa.careers import JobRunner
from fmsa.config import Settings, SettingsStore
from fmsa.paths import AppPaths
from fmsa.updates import UpdateChecker

TOKEN_HEADER = "X-FMSA-Token"

_MISSING_FRONTEND = """<!doctype html><html><body style="font-family:sans-serif">
<h1>FMSaveAnalyst</h1><p>Frontend non compilato. Esegui <code>npm run build</code> in
<code>frontend/</code> oppure avvia il dev server Vite.</p></body></html>"""


def create_app(paths: AppPaths, store: SettingsStore, token: str) -> FastAPI:
    app = FastAPI(title="FMSaveAnalyst", version=__version__, docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def require_token(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path.startswith("/api/"):
            given = request.headers.get(TOKEN_HEADER, "")
            if not hmac.compare_digest(given.encode(), token.encode()):
                return JSONResponse({"detail": "invalid session token"}, status_code=401)
        return await call_next(request)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/app-info")
    def app_info() -> dict[str, object]:
        return {
            "version": __version__,
            "portable": paths.portable,
            "app_dir": str(paths.app_dir),
            "data_dir": str(paths.data_dir),
            "settings_file": str(store.path),
        }

    updates = UpdateChecker()

    @app.get("/api/updates")
    def get_updates(force: bool = False) -> dict[str, object]:
        """Latest release on GitHub. Automatic checks honour the settings switch."""
        if not force and not store.get().check_updates:
            return {"current": __version__, "disabled": True, "update_available": False}
        return updates.get(force=force).to_dict()

    @app.get("/api/settings")
    def get_settings() -> Settings:
        return store.get()

    @app.put("/api/settings")
    def put_settings(settings: Settings) -> Settings:
        return store.save(settings)

    app.include_router(create_router(store, JobRunner()))
    app.include_router(api_query.create_router(store, paths.data_dir))
    app.include_router(api_dashboards.create_router(store, paths.data_dir))
    app.include_router(api_ai.create_router(store))
    _mount_frontend(app, paths.frontend_dir)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> Response:
        if path.startswith("api/"):
            return JSONResponse({"detail": "not found"}, status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index, headers={"Cache-Control": "no-store"})
        return HTMLResponse(_MISSING_FRONTEND)
