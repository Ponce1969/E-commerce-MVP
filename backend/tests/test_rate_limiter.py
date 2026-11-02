from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.infrastructure.security.rate_limiter import SimpleRateLimiter


def test_rate_limiter_allows_under_limit():
    limiter = SimpleRateLimiter(max_requests=3, window_seconds=60)
    mock_request = MagicMock()
    mock_request.client.host = "192.168.1.10"
    mock_request.headers = {}

    # 3 allowed requests
    limiter.check(mock_request)
    limiter.check(mock_request)
    limiter.check(mock_request)


def test_rate_limiter_blocks_on_excess():
    limiter = SimpleRateLimiter(max_requests=2, window_seconds=60)
    mock_request = MagicMock()
    mock_request.client.host = "10.0.0.5"
    mock_request.headers = {}

    limiter.check(mock_request)
    limiter.check(mock_request)

    # 3rd request must trigger HTTP 429
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(mock_request)

    assert exc_info.value.status_code == 429
    assert "Demasiados intentos" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers


def test_rate_limiter_respects_forwarded_for():
    limiter = SimpleRateLimiter(max_requests=1, window_seconds=60)
    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"  # Nginx proxy IP
    mock_request.headers = {"x-forwarded-for": "203.0.113.195, 127.0.0.1"}

    limiter.check(mock_request)

    with pytest.raises(HTTPException) as exc_info:
        limiter.check(mock_request)

    assert exc_info.value.status_code == 429
