"""
Simple in-memory sliding-window rate limiter.

Used to prevent captains from spamming bids.
"""

import time
from collections import defaultdict, deque
from typing import Deque, Dict


class RateLimiter:
    def __init__(self, limit: int = 3, window_seconds: float = 1.0):
        self.limit = limit
        self.window_seconds = window_seconds

        # Fixed syntax: Dict[int, Deque[float]]
        self.events: Dict[int, Deque[float]] = defaultdict(deque)

    def allow(self, key: int) -> bool:
        now = time.monotonic()
        dq = self.events[key]

        while dq and now - dq[0] > self.window_seconds:
            dq.popleft()

        if len(dq) >= self.limit:
            return False

        dq.append(now)
        return True