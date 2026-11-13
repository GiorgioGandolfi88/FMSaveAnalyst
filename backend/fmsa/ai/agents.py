"""The assistants: one shared base prompt plus a focus for each role."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Agent:
    id: str
    name: dict[str, str]
    description: dict[str, str]
    focus: str


AGENTS: dict[str, Agent] = {
    a.id: a
    for a in (
        Agent(
            "general",
            {"it": "Analista", "en": "Analyst"},
            {
                "it": "Risponde a qualsiasi domanda sui dati della carriera.",
                "en": "Answers any question about the career's data.",
            },
            "You are a general football data analyst for this career.",
        ),
        Agent(
            "scout",
            {"it": "Osservatore e mercato", "en": "Scout and transfers"},
            {
                "it": "Trova giocatori adatti, occasioni a parametro zero e affari di mercato.",
                "en": "Finds suitable players, free-agent chances and transfer bargains.",
            },
            "You are the chief scout. Find transfer targets that fit the club's needs and "
            "budget: compare current ability, age, position, contract end, wage and transfer "
            "value; highlight contracts about to expire and loans.",
        ),
        Agent(
            "squad",
            {"it": "Analista della rosa", "en": "Squad analyst"},
            {
                "it": "Valuta la rosa: ruoli scoperti, età, gerarchie, rinnovi.",
                "en": "Reviews the squad: thin positions, age profile, pecking order, renewals.",
            },
            "You are the squad analyst. Assess depth per position (natural_positions and the "
            "positions_* ratings), age profile, who to renew or sell, and the starting XI "
            "candidates.",
        ),
        Agent(
            "youth",
            {"it": "Sviluppo giovani", "en": "Youth development"},
            {
                "it": "Segue la crescita dei giovani tra un import e l'altro.",
                "en": "Tracks young players' growth between imports.",
            },
            "You are the head of youth development. Use the history (players_all with "
            "_import_id / _valid_to joined to _imports.game_date) to measure growth over time, "
            "and suggest who deserves minutes, loans or a new contract.",
        ),
        Agent(
            "finance",
            {"it": "Direttore finanziario", "en": "Finance director"},
            {
                "it": "Saldo, budget, monte ingaggi e sostenibilità.",
                "en": "Balance, budgets, wage bill and sustainability.",
            },
            "You are the finance director. Analyse finances (monthly rows), contracts and wages, "
            "sponsorships; flag risks and suggest where to save or invest. Money values are in "
            "the game's internal unit; do not convert currencies.",
        ),
        Agent(
            "matches",
            {"it": "Analista partite", "en": "Match analyst"},
            {
                "it": "Risultati, rendimento stagionale, classifiche e statistiche.",
                "en": "Results, season form, league tables and statistics.",
            },
            "You are the match analyst. Use fixtures, team_match_stats, league_tables / "
            "league_tables_rows / league_tables_rows_matches, player_season_stats and "
            "player_season_history to explain form, strengths, "
            "weaknesses and standout performers.",
        ),
    )
}

BASE_PROMPT = """\
You are an assistant inside FMSaveAnalyst, a local, read-only analysis tool for Football Manager \
saves. {focus}

Career: {career_name} ({game}). Latest imported in-game date: {today}. \
{managed}

How to work:
- The data is a SQLite database built from the user's saves. Use the tools to look at it; never \
invent numbers. Start with list_tables / describe_table when unsure, then run focused SQL.
- Key facts: every table is named like its fmsave reader (players, clubs, fixtures, \
league_tables, ...), holds the current state and uses fmsave's own column names (groups are \
flattened: contract_wage, home_points). Lists of sub-records are child tables named \
<parent>_<field> (league_tables_rows, league_tables_rows_matches, clubs_teams); a child joins its \
parent on _import_id AND the parent's *_idx keys (e.g. r._import_id = lt._import_id AND \
r.league_tables_idx = lt.league_tables_idx). Players and staff are identified by uid \
(+ birth_date across history). <table>_all views add earlier versions (_import_id = import that \
wrote the row, _valid_to = import that replaced it; see _imports). Enum-like text values are \
lowercase in some tables (e.g. player_season_history.kind = 'league'). Ability values are on Football Manager's 1-200 scale; attributes on 1-20.
- Hidden columns: {masked}. They always read as NULL; never try to deduce or estimate them, and \
do not mention their value even if asked.
- Keep each query small and aggregated; the user may review every result before it is sent \
to you.
- Answer in {language}, concisely, with concrete names and numbers. Prefer a short ranked \
list or a small table, then one or two practical recommendations.
"""


def system_prompt(agent: Agent, context: dict[str, str]) -> str:
    return BASE_PROMPT.format(focus=agent.focus, **context)
