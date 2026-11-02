import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from pydantic import BaseModel

from src.config import settings


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    CUSTOMER = "CUSTOMER"


class TokenData(BaseModel):
    user_id: int
    email: str
    role: UserRole
    commercial_list_id: int | None = None
    pwd_fp: str | None = None


def _compute_password_fingerprint(password_hash: str) -> str:
    """Computes a truncated HMAC-SHA256 fingerprint of the current password hash.

    Binding the reset token to the current password hash ensures the token is
    automatically invalidated as soon as the password is changed once (single-use).
    """
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        password_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]


def create_access_token(
    user_id: int,
    email: str,
    role: UserRole,
    commercial_list_id: int | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Generates a signed JWT with user role, commercial list, and explicit 'access' type."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role.value,
        "commercial_list_id": commercial_list_id,
        "type": "access",
        "exp": expire,
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> TokenData | None:
    """Decodes and validates an access JWT token. Rejects password_reset tokens."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            return None

        sub = payload.get("sub")
        email = payload.get("email")
        role_str = payload.get("role")
        comm_list_id = payload.get("commercial_list_id")

        if not sub or not email or not role_str:
            return None

        return TokenData(
            user_id=int(sub),
            email=str(email),
            role=UserRole(role_str),
            commercial_list_id=int(comm_list_id) if comm_list_id is not None else None,
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def create_password_reset_token(
    user_id: int,
    email: str,
    role: UserRole,
    password_hash: str = "",
    expires_minutes: int = 60,
) -> str:
    """Generates a signed single-use JWT specific for password reset with 1 hour expiration."""
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    to_encode: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role.value,
        "type": "password_reset",
        "pwd_fp": _compute_password_fingerprint(password_hash),
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_password_reset_token(
    token: str,
    current_password_hash: str | None = None,
) -> TokenData | None:
    """Decodes and validates a password reset JWT and optionally verifies single-use fingerprint."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
        sub = payload.get("sub")
        email = payload.get("email")
        role_str = payload.get("role")
        pwd_fp = payload.get("pwd_fp")
        if not sub or not email or not role_str:
            return None

        if current_password_hash is not None:
            expected_fp = _compute_password_fingerprint(current_password_hash)
            if not pwd_fp or not hmac.compare_digest(str(pwd_fp), expected_fp):
                return None

        return TokenData(
            user_id=int(sub),
            email=str(email),
            role=UserRole(role_str),
            pwd_fp=str(pwd_fp) if pwd_fp else None,
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
