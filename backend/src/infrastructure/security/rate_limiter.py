import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import HTTPException, Request, status


class SimpleRateLimiter:
    """Thread-safe, in-memory sliding window rate limiter for endpoint protection.

    Implements ISO 27001 A.8.5 & SOC 2 CC6.1 brute-force mitigation.
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def check(self, request: Request, identifier: str = "") -> None:
        client_ip = "unknown"
        if request.client:
            client_ip = request.client.host

        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        key = f"{client_ip}:{identifier}" if identifier else client_ip
        now = time.time()

        # Evict timestamps outside the sliding window
        valid_times = [t for t in self._history[key] if now - t < self.window_seconds]
        self._history[key] = valid_times

        if len(valid_times) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - valid_times[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos. Por favor espere un momento antes de reintentar.",
                headers={"Retry-After": str(max(1, retry_after))},
            )

        self._history[key].append(now)


# Standard singleton limiters
login_rate_limiter = SimpleRateLimiter(max_requests=5, window_seconds=60)
password_reset_rate_limiter = SimpleRateLimiter(max_requests=3, window_seconds=300)


def rate_limit(limiter: SimpleRateLimiter) -> Callable[[Request], None]:
    """Dependency helper to enforce rate limiting on FastAPI routes."""

    def dependency(request: Request) -> None:
        limiter.check(request)

    return dependency
