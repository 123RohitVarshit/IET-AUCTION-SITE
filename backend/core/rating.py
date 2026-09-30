"""
OFFLINE script. Run once after the final candidate list is locked.

Elo used in reverse:

    If a candidate would beat a share p of the pool:

        rating = 1500 + 400 * log10(p / (1 - p))

Usage from project root:

    python -m backend.core.rating raw.csv rated.csv

raw.csv needs columns:

    id,name,aptitude,gd,profile

Extra columns are passed through and will appear on candidate cards.
"""

import csv
import math
import sys
from typing import Dict, List


try:
    from .config import Config
except ImportError:
    # Fallback allows running from inside backend/core/ as a plain script,
    # but the recommended way is:
    #   python -m backend.core.rating raw.csv rated.csv
    from config import Config


WEIGHTS = {
    "aptitude": 0.40,
    "gd": 0.25,
    "profile": 0.35,
}

# Top 10% = tier 1
# Next 20% = tier 2
# Next 30% = tier 3
# Rest = tier 4
TIER_CUTS = (0.10, 0.30, 0.60)

TIER_BASE = dict(Config().tier_base)

REQUIRED_COLUMNS = {
    "id",
    "name",
    "aptitude",
    "gd",
    "profile",
}

SCORE_COLUMNS = (
    "aptitude",
    "gd",
    "profile",
)


def percentile_scores(values: List[float]) -> List[float]:
    """
    Share of the other candidates each one beats.

    Ties count half.
    """
    n = len(values)

    if n == 1:
        return [0.5]

    out = []

    for i, v in enumerate(values):
        below = sum(1 for j, x in enumerate(values) if j != i and x < v)
        tied = sum(1 for j, x in enumerate(values) if j != i and x == v)
        out.append((below + 0.5 * tied) / (n - 1))

    return out


def elo_rating(p: float, lo: float = 0.02, hi: float = 0.98) -> int:
    """
    Convert percentile p into an Elo-style rating.
    """
    p = min(max(p, lo), hi)
    return round(1500 + 400 * math.log10(p / (1.0 - p)))


def tier_for(higher: int, n: int) -> int:
    """
    Assign tier by rank.

    Tied candidates share a tier because they have the same number of
    players above them.
    """
    if n <= 0:
        raise ValueError("Cannot assign tier for empty candidate pool")

    frac = higher / n

    for tier, cut in enumerate(TIER_CUTS, start=1):
        if frac < cut:
            return tier

    return 4


def _validate_rows(rows: List[Dict]) -> None:
    """
    Fail early with clear errors instead of crashing mid-calculation.
    """

    if not rows:
        raise ValueError("Candidate CSV is empty")

    fields = set(rows[0].keys())
    missing = REQUIRED_COLUMNS - fields

    if missing:
        raise ValueError(
            f"raw.csv is missing required columns: {', '.join(sorted(missing))}"
        )

    seen_ids = set()

    for line_no, row in enumerate(rows, start=2):
        candidate_id = str(row.get("id", "")).strip()

        if not candidate_id:
            raise ValueError(f"Line {line_no}: candidate id is empty")

        if candidate_id in seen_ids:
            raise ValueError(f"Line {line_no}: duplicate candidate id {candidate_id}")

        seen_ids.add(candidate_id)

        name = str(row.get("name", "")).strip()
        if not name:
            raise ValueError(f"Line {line_no}: candidate name is empty")

        for col in SCORE_COLUMNS:
            raw_value = row.get(col, "")
            try:
                float(raw_value)
            except Exception as exc:
                raise ValueError(
                    f"Line {line_no}: column '{col}' must be numeric, got {raw_value!r}"
                ) from exc


def build(rows: List[Dict]) -> List[Dict]:
    """
    Calculate rating, tier, and base_price for each candidate row.
    """

    if not rows:
        return []

    _validate_rows(rows)

    cols = {
        k: percentile_scores([float(r[k]) for r in rows])
        for k in WEIGHTS
    }

    for i, r in enumerate(rows):
        p = sum(WEIGHTS[k] * cols[k][i] for k in WEIGHTS)
        r["rating"] = elo_rating(p)

    n = len(rows)

    for r in rows:
        higher = sum(1 for o in rows if o["rating"] > r["rating"])
        r["tier"] = tier_for(higher, n)
        r["base_price"] = TIER_BASE[r["tier"]]

    return rows


def main(argv: List[str]) -> int:
    if len(argv) != 3:
        print("Usage: python -m backend.core.rating raw.csv rated.csv")
        return 2

    src, dst = argv[1], argv[2]

    try:
        # utf-8-sig handles CSV files saved from Excel with BOM.
        with open(src, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        rows = build(rows)

        if not rows:
            print("No candidates found.")
            return 0

        rows.sort(key=lambda r: -r["rating"])

        with open(dst, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

        print(f"Wrote {len(rows)} candidates to {dst}")
        return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))