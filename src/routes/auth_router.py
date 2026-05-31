from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from controllers.auth_controller import AuthController
from helpers.config import Settings, get_settings
from schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
    RegisterRequest,
    VerifyEmailResponse,
)


auth_router = APIRouter(prefix="/auth", tags=["Auth"])


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.db_client() as session:
        yield session


@auth_router.post("/register", response_model=MessageResponse)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return await AuthController.register(payload, db, settings)


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return await AuthController.login(payload, db, settings)


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return await AuthController.refresh(payload.refresh_token, db, settings)


@auth_router.post("/logout", response_model=MessageResponse)
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)):
    return await AuthController.logout(payload.refresh_token, db)


@auth_router.get("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return await AuthController.verify_email(token, db, settings)
