"""
Server clock loop.

Calls auction.tick() about 10 times per second.

Important:
- When a transition happens, save state immediately.
- When a transition happens, broadcast immediately.
- Otherwise send heartbeat state about once per second.
"""

import asyncio
import logging
import time

from .sync import sync_all


logger = logging.getLogger("auction.tick")


def _transition_signature(auction):
    """
    Return a stable signature of important auction transitions.

    We intentionally do not include seconds_left here because that changes
    constantly and should not trigger persistence.
    """

    last_result = auction.last_result

    if isinstance(last_result, dict):
        last_result = tuple(sorted(last_result.items()))

    return (
        auction.phase,
        auction.round_no,
        auction.current,
        auction.done_reason,
        last_result,
    )


async def tick_loop(state) -> None:
    auction = state.auction

    last_signature = _transition_signature(auction)
    next_heartbeat = time.monotonic() + 1.0

    while True:
        auction.tick()

        now = time.monotonic()
        current_signature = _transition_signature(auction)

        if current_signature != last_signature:
            # A meaningful transition happened:
            # PREVIEW -> LIVE, LIVE -> RESULT, RESULT -> next player,
            # LIVE -> AWAITING_HAMMER, DONE, etc.
            try:
                state.store.save_state(auction.to_dict())
            except Exception:
                logger.exception("Failed to save auction state after tick transition")

            await sync_all(state)

            last_signature = current_signature
            next_heartbeat = now + 1.0

        elif now >= next_heartbeat:
            # Normal heartbeat: keeps timers synchronized on all screens.
            await sync_all(state)
            next_heartbeat = now + 1.0

        await asyncio.sleep(0.1)