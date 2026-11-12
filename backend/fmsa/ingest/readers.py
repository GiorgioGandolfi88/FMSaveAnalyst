"""How each fmsave reader is stored in a career database.

Storage kinds (see docs/fmsave-schema.md for the evidence behind each choice):

- ENTITY: one current version per key, older versions kept (`_valid_from` / `_valid_to`
  import ids). A new version is written only when something changed, so attribute and ability
  progression is available without storing identical copies.
- EVENT: things that happened (matches, injuries, season history). Accumulated across imports
  and deduplicated by key, because a save only keeps a time window of them. A record whose
  values change (a fixture that gets played) is updated in place.
- SNAPSHOT: tables without a stable key, or meaningful only "as of" a date; stored whole for
  every import.
- LATEST: only the most recent import is kept (replaced every time). Used for the running
  season's statistics: completed seasons are already kept, per season, by
  player_season_history, so earlier copies would only duplicate them.

Readers are read in groups: fmsave keeps every table it has read in memory until the save is
closed, so the save is reopened for every group to keep memory bounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Kind(StrEnum):
    ENTITY = "entity"
    EVENT = "event"
    SNAPSHOT = "snapshot"
    LATEST = "latest"


@dataclass(frozen=True, slots=True)
class ReaderSpec:
    name: str
    kind: Kind
    key: tuple[str, ...] = ()  # empty for EVENT: the whole row is the key
    exclude: frozenset[str] = frozenset()


E, V, S, L = Kind.ENTITY, Kind.EVENT, Kind.SNAPSHOT, Kind.LATEST

READER_GROUPS: tuple[tuple[ReaderSpec, ...], ...] = (
    (
        # contract and suspensions are also readers of their own
        ReaderSpec("players", E, ("uid", "birth_date"), frozenset({"contract", "suspensions"})),
        ReaderSpec("contracts", E, ("player_uid",)),
        ReaderSpec("suspensions", V, ("player_uid", "issued_date", "scope_code", "competition_id")),
    ),
    (
        ReaderSpec("staff", E, ("uid", "birth_date")),
        ReaderSpec("staff_lists", S),
    ),
    (
        ReaderSpec("clubs", E, ("uid",)),
        ReaderSpec("managed_clubs", S),
        ReaderSpec("finances", V, ("club_uid", "month")),
        ReaderSpec("sponsorships", S),
        ReaderSpec("facilities", E, ("club_uid",)),
        ReaderSpec("stadiums", E, ("uid",)),
        ReaderSpec("affiliates", S),
        ReaderSpec("job_vacancies", S),
    ),
    (
        ReaderSpec("nations", E, ("nation_id",)),
        ReaderSpec("competitions", E, ("id",)),
        ReaderSpec("stages", E, ("id",)),
        ReaderSpec("fixtures", V, ("date", "home_team_id", "away_team_id")),
        ReaderSpec("officials", E, ("referee_id",)),
        ReaderSpec("league_tables", S),
        ReaderSpec("competition_rules", S),
        ReaderSpec("transfer_windows", S),
    ),
    (
        ReaderSpec(
            "player_match_stats", V, ("player_uid", "date", "competition_id", "opponent_team_id")
        ),
        ReaderSpec("team_match_stats", V, ("date", "home_team_id", "away_team_id", "team_id")),
    ),
    (ReaderSpec("player_season_stats", L),),
    (
        ReaderSpec(
            "player_season_history",
            V,
            ("player_uid", "season_year", "club_uid", "kind", "competition_reference"),
        ),
    ),
    (
        ReaderSpec("injury_types", E, ("id",)),
        ReaderSpec("injuries", V, ("player_uid", "date", "type_id")),
    ),
    (
        ReaderSpec("training", S),
        ReaderSpec("mentoring", S),
        ReaderSpec("tactics", S),
        ReaderSpec("set_pieces", S),
        ReaderSpec("selections", S),
        ReaderSpec("squad_planner", S),
    ),
)

ALL_READERS: tuple[ReaderSpec, ...] = tuple(r for g in READER_GROUPS for r in g)
