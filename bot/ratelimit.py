"""Rate limiter en memoria por usuario (ventana deslizante de 60s).

Suficiente para 1 réplica en modo polling. Para HA con varias réplicas,
sustituir por un backend compartido (valkey) en una fase posterior.
"""
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, per_min: int):
        self.per_min = max(1, per_min)
        self._hits: dict[int, deque] = defaultdict(deque)

    def allow(self, key: int) -> bool:
        now = time.monotonic()
        dq = self._hits[key]
        while dq and now - dq[0] > 60:
            dq.popleft()
        if len(dq) >= self.per_min:
            return False
        dq.append(now)
        return True
