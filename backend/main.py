"""
FastAPI entry point.

Run from project root:

    uvicorn backend.main:app --reload
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routers import (
    admin,
    captain,
    exports,
    health,
    setup,
    stage,
)
from .bootstrap import create_state
from .realtime.handlers import router as websocket_router
from .realtime.tick import tick_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    base_dir = Path(__file__).resolve().parents[1]

    state = create_state(base_dir)
    app.state.app_state = state

    tick_task = asyncio.create_task(tick_loop(state))

    try:
        yield
    finally:
        tick_task.cancel()

        try:
            await tick_task
        except asyncio.CancelledError:
            pass

        state.store.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="IET Auction Backend",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(setup.router)
    app.include_router(captain.router)
    app.include_router(admin.router)
    app.include_router(stage.router)
    app.include_router(exports.router)
    app.include_router(websocket_router)

    static_dir = Path(__file__).resolve().parents[1] / "static"

    if static_dir.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(static_dir), html=True),
            name="static",
        )

    return app


app = create_app()
