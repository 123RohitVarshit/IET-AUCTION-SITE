"""
Shared test helpers.

This file is not a test file. It is imported by the test modules.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI

from backend.api.rate_limit import RateLimiter
from backend.api.routers import (
    admin,
    captain,
    exports,
    health,
    setup,
    stage,
)
from backend.core.auction import Auction
from backend.core.config import Config
from backend.persistence.store import Store
from backend.realtime.handlers import router as websocket_router
from backend.realtime.hub import WebSocketHub
from backend.state import AppState


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def make_cfg(**overrides) -> Config:
    defaults = dict(
        roster_size=1,
        purse=10_000,
        preview_seconds=0,
        bid_seconds=30,
        result_seconds=8,
        anti_snipe_seconds=8,
        undo_extend_seconds=10,
        auto_advance=True,
        max_rounds=5,
    )

    defaults.update(overrides)

    return Config(**defaults)


def make_teams(count: int, purse: int = 10_000):
    return [
        {
            "id": i,
            "name": f"Team {i}",
            "purse": purse,
        }
        for i in range(1, count + 1)
    ]


def make_candidates(count: int, base_price: int = 1000, tier: int = 1):
    return [
        {
            "id": i,
            "name": f"Player {i}",
            "rating": 1500,
            "tier": tier,
            "base_price": base_price,
        }
        for i in range(1, count + 1)
    ]


def make_started_auction(
    clock=None,
    team_count: int = 2,
    candidate_count: int = 2,
    base_price: int = 1000,
    tier: int = 1,
    **cfg_overrides,
):
    """
    Create an auction that has already passed setup_report() and start().
    """

    if clock is None:
        clock = FakeClock()

    cfg = make_cfg(**cfg_overrides)

    teams = make_teams(team_count)
    candidates = make_candidates(
        candidate_count,
        base_price=base_price,
        tier=tier,
    )

    auction = Auction(
        cfg,
        teams,
        candidates,
        clock=clock,
    )

    auction.start()

    return auction, clock


def make_test_app(
    team_count: int = 2,
    candidate_count: int = 2,
    roster_size: int = 1,
    admin_pin: str = "test-admin",
    team_logins=None,
    **cfg_overrides,
):
    """
    Build a FastAPI app suitable for TestClient tests.

    This does not use backend.main.app because that app uses bootstrap/lifespan
    and reads CSV files from disk. For tests we want controlled in-memory data.
    """

    tmp = TemporaryDirectory()
    db_path = Path(tmp.name) / "test.db"

    store = Store(db_path)

    cfg = make_cfg(
        roster_size=roster_size,
        **cfg_overrides,
    )

    teams = make_teams(team_count)

    # Use cheap tier-4 players by default so API and WebSocket tests
    # do not need large bid amounts.
    candidates = make_candidates(
        candidate_count,
        base_price=200,
        tier=4,
    )

    auction = Auction(cfg, teams, candidates)

    hub = WebSocketHub()

    # High limit so tests do not accidentally trigger rate limiting.
    rate_limiter = RateLimiter(
        limit=1000,
        window_seconds=1.0,
    )

    if team_logins is None:
        team_logins = {
            i: f"code{i}"
            for i in range(1, team_count + 1)
        }

    state = AppState(
        cfg=cfg,
        auction=auction,
        store=store,
        hub=hub,
        rate_limiter=rate_limiter,
        admin_pin=admin_pin,
        team_tokens={},
        team_logins=team_logins,
    )

    app = FastAPI()
    app.state.app_state = state

    app.include_router(health.router)
    app.include_router(setup.router)
    app.include_router(captain.router)
    app.include_router(admin.router)
    app.include_router(stage.router)
    app.include_router(exports.router)
    app.include_router(websocket_router)

    return app, state, tmp