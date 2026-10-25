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


def create_access_token(
    user_id: int,
    email: str,
    role: UserRole,
    commercial_list_id: int | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Generates a signed JWT with user role and commercial list claims."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role.value,
        "commercial_list_id": commercial_list_id,
        "exp": expire,
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> TokenData | None:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
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
    expires_minutes: int = 60,
) -> str:
    """Generates a signed JWT specific for password reset with 1 hour expiration."""
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    to_encode = {
        "sub": str(user_id),
        "email": email,
        "role": role.value,
        "type": "password_reset",
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_password_reset_token(token: str) -> TokenData | None:
    """Decodes and validates a password reset JWT."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
        sub = payload.get("sub")
        email = payload.get("email")
        role_str = payload.get("role")
        if not sub or not email or not role_str:
            return None
        return TokenData(
            user_id=int(sub),
            email=str(email),
            role=UserRole(role_str),
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
