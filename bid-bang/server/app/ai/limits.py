"""Protection des coûts et des abus pour la génération IA (en mémoire, par processus)."""
import asyncio
import time
from collections import defaultdict, deque

MAX_GENERATIONS_PER_ROOM = 5   # appels au fournisseur par salon (échecs compris)
MIN_INTERVAL_SECONDS = 5.0     # délai minimal entre deux générations d'un salon
MAX_CONCURRENT_GENERATIONS = 3  # générations simultanées sur tout le serveur
MAX_FAILURES_PER_MINUTE = 10   # requêtes refusées (jeton, droits) par adresse client

_semaphore: asyncio.Semaphore | None = None


def global_slot() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
    return _semaphore


def reset() -> None:
    """Pour les tests."""
    global _semaphore
    _semaphore = None
    failures.clear()


class FailureLimiter:
    """Fenêtre glissante d'échecs d'authentification par adresse."""

    def __init__(self, limit: int = MAX_FAILURES_PER_MINUTE, window: float = 60.0):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, who: str, now: float) -> deque[float]:
        q = self._hits[who]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def blocked(self, who: str) -> bool:
        return len(self._prune(who, time.monotonic())) >= self.limit

    def record(self, who: str) -> None:
        now = time.monotonic()
        self._prune(who, now).append(now)

    def clear(self) -> None:
        self._hits.clear()


failures = FailureLimiter()
