"""API routes: player list, player card and shortlist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from fmsa.config import SettingsStore
from fmsa.players import (
    GROUPS,
    STAT_KINDS,
    PlayerError,
    list_players,
    player_card,
    player_stats,
    read_shortlist,
    write_shortlist,
)
from fmsa.query.session import QueryError, open_career


class PlayerKey(BaseModel):
    uid: int
    birth_date: str


class ListBody(BaseModel):
    search: str = ""
    group: str = ""
    shortlist_only: bool = False
    kind: str = "league"
    sort: str = "pa"
    desc: bool = True
    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=500)


def create_router(store: SettingsStore, data_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api/players")

    def career() -> Path:
        path = store.get().last_career
        if not path or not Path(path).is_file():
            raise HTTPException(409, "no career is open")
        return Path(path)

    @router.get("/meta")
    def meta() -> dict[str, Any]:
        return {
            "groups": {k: {"positions": list(v[0]), "label": v[1]} for k, v in GROUPS.items()},
            "stat_kinds": list(STAT_KINDS),
        }

    @router.post("/list")
    def players(body: ListBody) -> dict[str, Any]:
        path = career()
        only = None
        if body.shortlist_only:
            only = [(i["uid"], i["birth_date"]) for i in read_shortlist(data_dir, path)]
        try:
            with open_career(path, store.get().masking) as session:
                return list_players(
                    session, search=body.search, group=body.group, only=only, kind=body.kind,
                    sort=body.sort, desc=body.desc, offset=body.offset, limit=body.limit,
                )  # fmt: skip
        except (PlayerError, QueryError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/card")
    def card(uid: int, birth_date: str, kind: str = "") -> dict[str, Any]:
        try:
            with open_career(career(), store.get().masking) as session:
                return player_card(session, uid, birth_date, kind)
        except PlayerError as exc:
            raise HTTPException(404, str(exc)) from exc
        except QueryError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/stats")
    def stats(uid: int, birth_date: str, kind: str) -> dict[str, Any]:
        try:
            with open_career(career(), store.get().masking) as session:
                return player_stats(session, uid, birth_date, kind)
        except (PlayerError, QueryError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/shortlist")
    def get_shortlist() -> list[dict[str, Any]]:
        return read_shortlist(data_dir, career())

    @router.put("/shortlist")
    def put_shortlist(items: list[PlayerKey]) -> list[dict[str, Any]]:
        path = career()
        write_shortlist(data_dir, path, [i.model_dump() for i in items])
        return read_shortlist(data_dir, path)

    return router
