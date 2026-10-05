"""
Loaders for CSV files.

load_candidates() reads rated.csv.
load_teams() reads teams.csv.
"""

import csv
from typing import Any, Dict, List


REQUIRED_CANDIDATE_COLUMNS = {
    "id",
    "name",
    "rating",
    "tier",
    "base_price",
}

CORE_CANDIDATE_COLUMNS = {
    "id",
    "name",
    "rating",
    "tier",
    "base_price",
    "aptitude",
    "gd",
    "profile",
}

VALID_TIERS = {1, 2, 3, 4}

REQUIRED_TEAM_COLUMNS = {
    "id",
    "name",
    "login_code",
}


def load_candidates(path: str) -> List[Dict[str, Any]]:
    """
    Load and validate rated candidates.

    Returns list of dicts:

        {
            "id": int,
            "name": str,
            "rating": int,
            "tier": int,
            "base_price": int,
            "profile": dict,
        }
    """

    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return []

    fields = set(rows[0].keys())
    missing = REQUIRED_CANDIDATE_COLUMNS - fields

    if missing:
        raise ValueError(
            f"Rated CSV is missing required columns: {', '.join(sorted(missing))}"
        )

    candidates: List[Dict[str, Any]] = []
    seen_ids = set()

    for line_no, row in enumerate(rows, start=2):
        try:
            candidate_id = int(str(row["id"]).strip())
            name = str(row["name"]).strip()
            rating = int(float(str(row["rating"]).strip()))
            tier = int(str(row["tier"]).strip())
            base_price = int(str(row["base_price"]).strip())

        except Exception as exc:
            raise ValueError(
                f"Line {line_no}: invalid candidate row: {exc}"
            ) from exc

        if not name:
            raise ValueError(f"Line {line_no}: candidate name is empty")

        if candidate_id in seen_ids:
            raise ValueError(
                f"Line {line_no}: duplicate candidate id {candidate_id}"
            )

        if tier not in VALID_TIERS:
            raise ValueError(
                f"Line {line_no}: tier must be one of {sorted(VALID_TIERS)}, got {tier}"
            )

        if base_price <= 0:
            raise ValueError(
                f"Line {line_no}: base_price must be positive, got {base_price}"
            )

        if rating <= 0:
            raise ValueError(
                f"Line {line_no}: rating must be positive, got {rating}"
            )

        seen_ids.add(candidate_id)

        profile = {
            k: v
            for k, v in row.items()
            if k not in REQUIRED_CANDIDATE_COLUMNS and v not in ("", None)
        }
        if "aptitude" in row and row["aptitude"] not in ("", None):
            try:
                profile["aptitude"] = int(float(str(row["aptitude"]).strip()))
            except Exception:
                profile["aptitude"] = row["aptitude"]
        if "gd" in row and row["gd"] not in ("", None):
            try:
                profile["gd"] = int(float(str(row["gd"]).strip()))
            except Exception:
                profile["gd"] = row["gd"]

        candidates.append(
            {
                "id": candidate_id,
                "name": name,
                "rating": rating,
                "tier": tier,
                "base_price": base_price,
                "profile": profile,
            }
        )

    return candidates


def load_teams(path: str) -> List[Dict[str, Any]]:
    """
    Load teams.

    Required columns:

        id,name,login_code

    Optional column:

        purse
    """

    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return []

    fields = set(rows[0].keys())
    missing = REQUIRED_TEAM_COLUMNS - fields

    if missing:
        raise ValueError(
            f"Teams CSV is missing required columns: {', '.join(sorted(missing))}"
        )

    teams: List[Dict[str, Any]] = []
    seen_ids = set()

    for line_no, row in enumerate(rows, start=2):
        try:
            team_id = int(str(row["id"]).strip())
            name = str(row["name"]).strip()
            login_code = str(row["login_code"]).strip()

        except Exception as exc:
            raise ValueError(
                f"Line {line_no}: invalid team row: {exc}"
            ) from exc

        if not name:
            raise ValueError(f"Line {line_no}: team name is empty")

        if not login_code:
            raise ValueError(f"Line {line_no}: team login_code is empty")

        if team_id in seen_ids:
            raise ValueError(f"Line {line_no}: duplicate team id {team_id}")

        seen_ids.add(team_id)

        team: Dict[str, Any] = {
            "id": team_id,
            "name": name,
            "login_code": login_code,
        }

        purse_raw = str(row.get("purse", "")).strip()

        if purse_raw:
            try:
                purse = int(purse_raw)
            except Exception as exc:
                raise ValueError(
                    f"Line {line_no}: purse must be an integer, got {purse_raw!r}"
                ) from exc

            if purse < 0:
                raise ValueError(
                    f"Line {line_no}: purse cannot be negative, got {purse}"
                )

            team["purse"] = purse

        teams.append(team)

    return teams