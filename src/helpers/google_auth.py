from dataclasses import dataclass

from fastapi import HTTPException, status
from google.auth.transport import requests
from google.oauth2 import id_token

from helpers.config import Settings


@dataclass(frozen=True)
class GoogleUserInfo:
    google_id: str
    email: str
    name: str | None


def verify_google_id_token(token: str, *, settings: Settings) -> GoogleUserInfo:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google login is not configured",
        )

    try:
        payload = id_token.verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        ) from exc

    if not payload.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google email is not verified",
        )

    email = payload.get("email")
    google_id_value = payload.get("sub")
    if not email or not google_id_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    return GoogleUserInfo(
        google_id=google_id_value,
        email=email,
        name=payload.get("name"),
    )
