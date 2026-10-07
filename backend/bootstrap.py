"""
Startup construction.

Creates:
- Config,
- Store,
- Auction,
- WebSocketHub,
- RateLimiter,
- AppState.

If a saved state exists in SQLite, restore it.
Otherwise create a fresh auction from CSV files.
"""

import os
from pathlib import Path
from typing import Any, Dict, List

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from .api.rate_limit import RateLimiter
from .core.auction import Auction
from .core.config import Config
from .core.loader import load_candidates, load_teams
from .persistence.store import Store
from .realtime.hub import WebSocketHub
from .state import AppState


def _load_if_exists(path: Path, loader) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    return loader(path)


def create_state(base_dir: Path) -> AppState:
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    rated_csv = data_dir / "rated.csv"
    teams_csv = data_dir / "teams.csv"
    db_path = data_dir / "auction.db"

    # Always start fresh: delete old database so the auction resets on
    # every server restart instead of resuming from saved state.
    if db_path.exists():
        db_path.unlink()
    # Also remove WAL and SHM files left by SQLite.
    for suffix in (".db-wal", ".db-shm"):
        wal_path = db_path.with_suffix(suffix)
        if wal_path.exists():
            wal_path.unlink()

    store = Store(db_path)

    # Teams/login codes are always read from teams.csv if available.
    teams = _load_if_exists(teams_csv, load_teams)

    team_logins = {
        team["id"]: team["login_code"]
        for team in teams
    }

    # Always create a fresh auction from CSV data.
    cfg = Config()
    candidates = _load_if_exists(rated_csv, load_candidates)

    auction = Auction(
        cfg=cfg,
        teams=teams,
        candidates=candidates,
    )

    hub = WebSocketHub()

    rate_limiter = RateLimiter(
        limit=3,
        window_seconds=1.0,
    )

    admin_pin = os.getenv("ADMIN_PIN", "change-me")

    return AppState(
        cfg=cfg,
        auction=auction,
        store=store,
        hub=hub,
        rate_limiter=rate_limiter,
        admin_pin=admin_pin,
        team_tokens={},
        team_logins=team_logins,
    )