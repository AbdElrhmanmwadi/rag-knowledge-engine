from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import uuid4

import jwt
from fastapi import HTTPException, status

from helpers.config import Settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_token(
    *,
    subject: str,
    settings: Settings,
    expires_delta: timedelta,
    token_type: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = _utc_now()
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(*, user_id: int, settings: Settings) -> str:
    return create_token(
        subject=str(user_id),
        settings=settings,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )


def create_email_verification_token(*, user_id: int, email: str, settings: Settings) -> str:
    return create_token(
        subject=str(user_id),
        settings=settings,
        expires_delta=timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
        token_type="email_verification",
        extra_claims={"email": email},
    )


def password_hash_fingerprint(hashed_password: str | None) -> str:
    """Short digest of the current password hash, embedded in reset tokens.

    The fingerprint changes as soon as the password does, so an issued reset
    token can only be redeemed once — without storing any state server-side.
    """
    return sha256((hashed_password or "").encode()).hexdigest()[:16]


def create_password_reset_token(
    *, user_id: int, email: str, hashed_password: str | None, settings: Settings
) -> str:
    return create_token(
        subject=str(user_id),
        settings=settings,
        expires_delta=timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        token_type="password_reset",
        extra_claims={"email": email, "pwd": password_hash_fingerprint(hashed_password)},
    )


def decode_token(token: str, *, settings: Settings, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    return payload
