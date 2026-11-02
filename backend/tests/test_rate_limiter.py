import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from src.application.use_cases.catalog.upload_attachment import UploadAttachmentUseCase
from src.domain.exceptions import BusinessRuleViolationException
from src.infrastructure.api.v1.payments.router import _verify_mp_signature
from src.infrastructure.security.jwt import (
    UserRole,
    create_access_token,
    create_password_reset_token,
    decode_access_token,
    decode_password_reset_token,
)
from src.infrastructure.security.rate_limiter import SimpleRateLimiter


def test_rate_limiter_allows_under_limit() -> None:
    limiter = SimpleRateLimiter(max_requests=3, window_seconds=60)
    mock_request = MagicMock()
    mock_request.client.host = "192.168.1.10"
    mock_request.headers = {}

    # 3 allowed requests
    limiter.check(mock_request)
    limiter.check(mock_request)
    limiter.check(mock_request)


def test_rate_limiter_blocks_on_excess() -> None:
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


def test_rate_limiter_respects_forwarded_for() -> None:
    limiter = SimpleRateLimiter(max_requests=1, window_seconds=60)
    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"  # Nginx proxy IP
    mock_request.headers = {"x-forwarded-for": "203.0.113.195, 127.0.0.1"}

    limiter.check(mock_request)

    with pytest.raises(HTTPException) as exc_info:
        limiter.check(mock_request)

    assert exc_info.value.status_code == 429


def test_rate_limiter_blocks_spoofed_leftmost_x_forwarded_for() -> None:
    limiter = SimpleRateLimiter(max_requests=1, window_seconds=60)

    req1 = MagicMock()
    req1.client.host = "127.0.0.1"
    req1.headers = {"x-forwarded-for": "1.1.1.1, 198.51.100.42"}

    req2 = MagicMock()
    req2.client.host = "127.0.0.1"
    # Attacker rotates leftmost fake IP, but Nginx appends true peer IP 198.51.100.42
    req2.headers = {"x-forwarded-for": "2.2.2.2, 198.51.100.42"}

    limiter.check(req1)
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(req2)

    assert exc_info.value.status_code == 429


def test_rate_limiter_bounds_tracked_keys_memory() -> None:
    limiter = SimpleRateLimiter(max_requests=2, window_seconds=60, max_tracked_keys=5)
    for i in range(10):
        req = MagicMock()
        req.client.host = f"192.0.2.{i}"
        req.headers = {}
        limiter.check(req)

    assert len(limiter._history) <= 5


def test_password_reset_token_cannot_be_used_as_access_token() -> None:
    reset_token = create_password_reset_token(
        user_id=1,
        email="mariana@2rodriguez.uy",
        role=UserRole.ADMIN,
        password_hash="$2b$12$oldhashvalue",
    )
    assert decode_access_token(reset_token) is None

    access_token = create_access_token(
        user_id=1,
        email="mariana@2rodriguez.uy",
        role=UserRole.ADMIN,
    )
    assert decode_password_reset_token(access_token) is None
    decoded_access = decode_access_token(access_token)
    assert decoded_access is not None
    assert decoded_access.user_id == 1


def test_password_reset_token_is_single_use_when_password_changes() -> None:
    old_hash = "$2b$12$old_bcrypt_hash_value_111111"
    new_hash = "$2b$12$new_bcrypt_hash_value_222222"

    token = create_password_reset_token(
        user_id=7,
        email="cliente@empresa.uy",
        role=UserRole.CUSTOMER,
        password_hash=old_hash,
    )

    # Valid before password change
    assert decode_password_reset_token(token, current_password_hash=old_hash) is not None
    # Automatically invalidated after password change (replay blocked)
    assert decode_password_reset_token(token, current_password_hash=new_hash) is None


@pytest.mark.asyncio
async def test_upload_attachment_rejects_extension_spoofing() -> None:
    mock_session = AsyncMock()
    use_case = UploadAttachmentUseCase(mock_session)

    spoofed_file = MagicMock(spec=UploadFile)
    spoofed_file.filename = "malicious.png"
    spoofed_file.read = AsyncMock(return_value=b"<html><script>alert(1)</script></html>")

    with pytest.raises(BusinessRuleViolationException, match="contenido binario"):
        await use_case.execute(spoofed_file)


def test_mp_webhook_hmac_signature_verification() -> None:
    mock_req = MagicMock()
    data_id = "999888"
    req_id = "req-abc-123"
    ts = "1700000000"
    secret = "super_secret_mp_webhook_key"

    manifest = f"id:{data_id};request-id:{req_id};ts:{ts};"
    valid_v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()

    with patch("src.infrastructure.api.v1.payments.router.settings.MP_WEBHOOK_SECRET", secret):
        mock_req.headers = {
            "x-signature": f"ts={ts},v1={valid_v1}",
            "x-request-id": req_id,
        }
        assert _verify_mp_signature(mock_req, data_id) is True

        mock_req.headers = {
            "x-signature": f"ts={ts},v1=deadbeef0000",
            "x-request-id": req_id,
        }
        assert _verify_mp_signature(mock_req, data_id) is False


def test_arch_and_secrets_guard_detects_violations() -> None:
    import ast
    import importlib.util
    from pathlib import Path

    guard_path = (
        Path(__file__).resolve().parent.parent.parent / "scripts" / "arch_and_secrets_guard.py"
    )
    spec = importlib.util.spec_from_file_location("arch_and_secrets_guard", guard_path)
    assert spec is not None and spec.loader is not None
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)

    # 1. Hexagonal violation in domain
    bad_domain_tree = ast.parse("from sqlalchemy import select\nimport src.infrastructure.db")
    hex_errs = guard.check_domain_hexagonal_purity(Path("domain/entities.py"), bad_domain_tree)
    assert len(hex_errs) == 2
    assert all("HEXAGONAL-VIOLATION" in e for e in hex_errs)

    # 2. Hardcoded secret & high-entropy token in Python
    bad_secret_tree = ast.parse(
        'MARCO_POSTAL_TOKEN: str = "LRJ4DwsDY21qwf3PSqsbTBMzAkAlWRCVVtcY2CYw28XGpyApGxNrEE4tU1NQ"\n'
        'SOME_RANDOM_VAR = "LRJ4DwsDY21qwf3PSqsbTBMzAkAlWRCVVtcY2CYw28XGpyApGxNrEE4tU1NQ"'
    )
    sec_errs = guard.check_python_hardcoded_secrets(Path("config.py"), bad_secret_tree)
    assert len(sec_errs) == 2
    assert any("HARDCODED-SECRET" in e for e in sec_errs)
    assert any("HIGH-ENTROPY-TOKEN" in e for e in sec_errs)

    # 3. Clean repository passes
    repo_root = Path(__file__).resolve().parent.parent.parent
    assert guard.scan_repository(repo_root) == []
