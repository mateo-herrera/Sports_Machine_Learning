"""Live game status from MLB StatsAPI (public, no auth)."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
ET = ZoneInfo("America/New_York")


def get_game_statuses(date=None):
    """Return {gamePk: status_dict} for the given date (default: today ET).

    Raises on network failure or bad response — the caller decides how to
    degrade. See the try/except around this call in main.py.
    """
    day = (date or datetime.now(ET)).strftime("%m/%d/%Y")

    r = requests.get(
        SCHEDULE_URL,
        params={"sportId": 1, "date": day, "hydrate": "linescore"},
        timeout=5,
    )
    r.raise_for_status()

    statuses = {}
    for d in r.json().get("dates", []):
        for g in d.get("games", []):
            ls = g.get("linescore") or {}
            teams = ls.get("teams") or {}
            status = g.get("status") or {}

            statuses[g["gamePk"]] = {
                "state": status.get("abstractGameState"),   # Preview | Live | Final
                "detail": status.get("detailedState"),      # In Progress, Delayed, Postponed...
                "inning": ls.get("currentInningOrdinal"),   # "7th"
                "half": ls.get("inningHalf"),               # "Top" / "Bottom"
                "away_score": (teams.get("away") or {}).get("runs"),
                "home_score": (teams.get("home") or {}).get("runs"),
            }

    return statuses



