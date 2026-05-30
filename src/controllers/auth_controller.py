from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.config import Settings
from helpers.email import send_verification_email
from helpers.jwt import create_access_token, create_email_verification_token, decode_token
from helpers.security import hash_password, verify_password
from models.token_model import RefreshToken
from models.user_model import User
from schemas.auth import LoginRequest, RegisterRequest


class AuthController:
    @staticmethod
    async def register(payload: RegisterRequest, db: AsyncSession, settings: Settings) -> dict[str, str]:
        existing_user = await db.scalar(
            select(User).where((User.email == payload.email) | (User.username == payload.username))
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email or username already registered",
            )

        user = User(
            email=payload.email,
            username=payload.username,
            hashed_password=hash_password(payload.password),
            is_verified=False,
        )
        db.add(user)
        await db.flush()

        verification_token = create_email_verification_token(
            user_id=user.id,
            email=user.email,
            settings=settings,
        )
        await send_verification_email(user.email, verification_token, settings)

        await db.commit()
        return {"message": "Check your email"}

    @staticmethod
    async def login(payload: LoginRequest, db: AsyncSession, settings: Settings) -> dict[str, str]:
        user = await db.scalar(select(User).where(User.email == payload.email))
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if not user.is_verified:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not verified")

        access_token = create_access_token(user_id=user.id, settings=settings)
        refresh_token, expires_at = AuthController._new_refresh_token(settings)

        db.add(RefreshToken(token=refresh_token, user_id=user.id, expires_at=expires_at))
        await db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    @staticmethod
    async def refresh(refresh_token: str, db: AsyncSession, settings: Settings) -> dict[str, str]:
        token_record = await db.scalar(select(RefreshToken).where(RefreshToken.token == refresh_token))
        if not token_record:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        if token_record.expires_at <= datetime.now(timezone.utc):
            await db.delete(token_record)
            await db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired")

        return {
            "access_token": create_access_token(user_id=token_record.user_id, settings=settings),
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    @staticmethod
    async def logout(refresh_token: str, db: AsyncSession) -> dict[str, str]:
        await db.execute(delete(RefreshToken).where(RefreshToken.token == refresh_token))
        await db.commit()
        return {"message": "Logged out"}

    @staticmethod
    async def verify_email(token: str, db: AsyncSession, settings: Settings) -> dict[str, str]:
        payload = decode_token(token, settings=settings, expected_type="email_verification")
        user_id = int(payload["sub"])
        email = payload.get("email")

        user = await db.scalar(select(User).where(User.id == user_id))
        if not user or user.email != email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification token")

        if not user.is_verified:
            user.is_verified = True
            await db.commit()

        return {"message": "Email verified successfully"}

    @staticmethod
    def _new_refresh_token(settings: Settings) -> tuple[str, datetime]:
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        return token_urlsafe(64), expires_at
