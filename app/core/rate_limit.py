"""A small in-memory, per-user sliding-window rate limiter.

Why in-memory: the API runs as ONE process (one container replica, one uvicorn worker), so a dict is
the whole truth and needs no extra service. The tradeoff: counts reset on restart and would not be
shared if we ever ran several replicas; at that point the counter belongs in Redis or an API gateway.

Why no lock: `hit` never awaits, so on the single asyncio event loop no other request can run between
the check and the append. The check-then-record is therefore atomic without one.
"""
import math
import time
from collections import deque
from collections.abc import Callable, Hashable


class SlidingWindowLimiter:
    def __init__(self, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.window_seconds = window_seconds
        self.clock = clock
        self._hits: dict[Hashable, deque[float]] = {}

    def hit(self, key: Hashable, limit: int) -> int | None:
        """Record one request for `key`. Returns None if allowed, else whole seconds until a slot frees up."""
        now = self.clock()
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()  # forget requests that have left the window
        if len(hits) >= limit:
            return max(1, math.ceil(hits[0] + self.window_seconds - now))
        hits.append(now)
        return None

    def reset(self) -> None:
        self._hits.clear()
