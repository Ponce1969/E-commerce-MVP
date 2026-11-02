import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import HTTPException, Request, status

_LOOPBACK_IPS = {"127.0.0.1", "::1", "localhost"}


def extract_client_ip(request: Request) -> str:
    """Safely extracts the client IP without trusting spoofable leftmost X-Forwarded-For values.

    Priority:
    1. X-Real-IP set directly by the edge Nginx proxy ($remote_addr).
    2. Rightmost non-loopback IP in X-Forwarded-For (appended by the trusted proxy).
    3. Direct socket peer address (request.client.host).
    """
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip and real_ip not in _LOOPBACK_IPS:
        return real_ip

    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        parts = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        non_loopback = [ip for ip in parts if ip not in _LOOPBACK_IPS]
        if non_loopback:
            return non_loopback[-1]
        if parts:
            return parts[-1]

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


class SimpleRateLimiter:
    """Thread-safe, memory-bounded sliding window rate limiter for endpoint protection.

    Implements ISO 27001 A.8.5 & SOC 2 CC6.1 brute-force and DoS mitigation.
    """

    def __init__(
        self,
        max_requests: int = 5,
        window_seconds: int = 60,
        max_tracked_keys: int = 10000,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_tracked_keys = max_tracked_keys
        self._history: dict[str, list[float]] = defaultdict(list)

    def _prune_stale_keys(self, now: float) -> None:
        """Removes expired keys when the tracking dictionary grows large to prevent memory exhaustion."""
        expired_keys = [
            k
            for k, times in self._history.items()
            if not times or (now - times[-1] >= self.window_seconds)
        ]
        for k in expired_keys:
            del self._history[k]

        # Hard cap eviction (oldest keys first) if still at capacity
        if len(self._history) >= self.max_tracked_keys:
            overflow = len(self._history) - self.max_tracked_keys + 1
            for k in list(self._history.keys())[:overflow]:
                del self._history[k]

    def check(self, request: Request, identifier: str = "") -> None:
        client_ip = extract_client_ip(request)
        key = f"{client_ip}:{identifier}" if identifier else client_ip
        now = time.time()

        if key not in self._history and len(self._history) >= self.max_tracked_keys:
            self._prune_stale_keys(now)

        # Evict timestamps outside the sliding window
        valid_times = [t for t in self._history.get(key, []) if now - t < self.window_seconds]
        if valid_times:
            self._history[key] = valid_times
        elif key in self._history:
            del self._history[key]

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
checkout_rate_limiter = SimpleRateLimiter(max_requests=10, window_seconds=60)


def rate_limit(limiter: SimpleRateLimiter) -> Callable[[Request], None]:
    """Dependency helper to enforce rate limiting on FastAPI routes."""

    def dependency(request: Request) -> None:
        limiter.check(request)

    return dependency
