import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from controllers.auth_controller import AuthController
from helpers.config import Settings
from helpers.google_auth import GoogleUserInfo, verify_google_id_token
from models.user_model import User


class GoogleAuthHelperTests(unittest.TestCase):
    def test_verify_google_id_token_success(self):
        settings = Settings(
            APP_NAME="test",
            APP_DESCRIPTION="test",
            APP_VERSION="1.0.0",
            FILE_MAX_SIZE=1,
            FILE_DEFAULT_CHUNK_SIZE=1,
            POSTGRES_USERNAME="u",
            POSTGRES_PASSWORD="p",
            POSTGRES_HOST="h",
            POSTGRES_PORT=5432,
            POSTGRES_DB="d",
            GENERATION_BACKEND="COHERE",
            EMBEDDING_BACKEND="COHERE",
            TRANSLATION_ENGINE="LIBRETRANSLATE",
            VECTOR_DB_BACKEND="PGVECTOR",
            VECTOR_DB_PATH="qdrant_db",
            VECTOR_DB_DISTANCE_METHOD="cosine",
            PRIMARY_LANG="en",
            DEFAULT_LANG="en",
            GOOGLE_CLIENT_ID="test-client-id.apps.googleusercontent.com",
        )

        payload = {
            "sub": "google-sub-123",
            "email": "user@example.com",
            "email_verified": True,
            "name": "Test User",
            "aud": settings.GOOGLE_CLIENT_ID,
        }

        with patch("helpers.google_auth.id_token.verify_oauth2_token", return_value=payload):
            result = verify_google_id_token("fake-token", settings=settings)

        self.assertEqual(result.google_id, "google-sub-123")
        self.assertEqual(result.email, "user@example.com")
        self.assertEqual(result.name, "Test User")

    def test_verify_google_id_token_rejects_unverified_email(self):
        settings = Settings(
            APP_NAME="test",
            APP_DESCRIPTION="test",
            APP_VERSION="1.0.0",
            FILE_MAX_SIZE=1,
            FILE_DEFAULT_CHUNK_SIZE=1,
            POSTGRES_USERNAME="u",
            POSTGRES_PASSWORD="p",
            POSTGRES_HOST="h",
            POSTGRES_PORT=5432,
            POSTGRES_DB="d",
            GENERATION_BACKEND="COHERE",
            EMBEDDING_BACKEND="COHERE",
            TRANSLATION_ENGINE="LIBRETRANSLATE",
            VECTOR_DB_BACKEND="PGVECTOR",
            VECTOR_DB_PATH="qdrant_db",
            VECTOR_DB_DISTANCE_METHOD="cosine",
            PRIMARY_LANG="en",
            DEFAULT_LANG="en",
            GOOGLE_CLIENT_ID="test-client-id.apps.googleusercontent.com",
        )

        payload = {
            "sub": "google-sub-123",
            "email": "user@example.com",
            "email_verified": False,
        }

        with patch("helpers.google_auth.id_token.verify_oauth2_token", return_value=payload):
            with self.assertRaises(HTTPException) as ctx:
                verify_google_id_token("fake-token", settings=settings)

        self.assertEqual(ctx.exception.status_code, 403)


class AuthControllerGoogleTests(unittest.TestCase):
    def _async_test(self, coro):
        return asyncio.run(coro)

    def _settings(self) -> Settings:
        return Settings(
            APP_NAME="test",
            APP_DESCRIPTION="test",
            APP_VERSION="1.0.0",
            FILE_MAX_SIZE=1,
            FILE_DEFAULT_CHUNK_SIZE=1,
            POSTGRES_USERNAME="u",
            POSTGRES_PASSWORD="p",
            POSTGRES_HOST="h",
            POSTGRES_PORT=5432,
            POSTGRES_DB="d",
            GENERATION_BACKEND="COHERE",
            EMBEDDING_BACKEND="COHERE",
            TRANSLATION_ENGINE="LIBRETRANSLATE",
            VECTOR_DB_BACKEND="PGVECTOR",
            VECTOR_DB_PATH="qdrant_db",
            VECTOR_DB_DISTANCE_METHOD="cosine",
            PRIMARY_LANG="en",
            DEFAULT_LANG="en",
            JWT_SECRET_KEY="test-secret-key",
            GOOGLE_CLIENT_ID="test-client-id.apps.googleusercontent.com",
        )

    def test_google_login_creates_new_user(self):
        db = AsyncMock()
        db.scalar = AsyncMock(return_value=None)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        google_user = GoogleUserInfo(
            google_id="google-sub-123",
            email="newuser@example.com",
            name="New User",
        )

        with patch("controllers.auth_controller.verify_google_id_token", return_value=google_user):
            with patch("controllers.auth_controller.create_access_token", return_value="access"):
                result = self._async_test(AuthController.google_login("token", db, self._settings()))

        self.assertEqual(result["access_token"], "access")
        self.assertEqual(result["token_type"], "bearer")
        db.add.assert_called()
        added_user = db.add.call_args_list[0].args[0]
        self.assertEqual(added_user.email, "newuser@example.com")
        self.assertEqual(added_user.google_id, "google-sub-123")
        self.assertTrue(added_user.is_verified)
        self.assertIsNone(added_user.hashed_password)

    def test_google_login_links_existing_email_account(self):
        existing_user = User(
            id=1,
            email="user@example.com",
            username="existing",
            hashed_password="bcrypt_sha256$hash",
            auth_provider="local",
            is_verified=False,
        )

        db = AsyncMock()
        db.scalar = AsyncMock(side_effect=[None, existing_user])
        db.commit = AsyncMock()

        google_user = GoogleUserInfo(
            google_id="google-sub-123",
            email="user@example.com",
            name="Existing User",
        )

        with patch("controllers.auth_controller.verify_google_id_token", return_value=google_user):
            with patch("controllers.auth_controller.create_access_token", return_value="access"):
                result = self._async_test(AuthController.google_login("token", db, self._settings()))

        self.assertEqual(result["access_token"], "access")
        self.assertEqual(existing_user.google_id, "google-sub-123")
        self.assertEqual(existing_user.auth_provider, "both")
        self.assertTrue(existing_user.is_verified)

    def test_login_rejects_google_only_account(self):
        google_user = User(
            id=2,
            email="google@example.com",
            username="google_user",
            hashed_password=None,
            google_id="google-sub-999",
            auth_provider="google",
            is_verified=True,
        )

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=google_user)

        from schemas.auth import LoginRequest

        with self.assertRaises(HTTPException) as ctx:
            self._async_test(
                AuthController.login(
                    LoginRequest(email="google@example.com", password="password123"),
                    db,
                    self._settings(),
                )
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "This account uses Google sign-in")


if __name__ == "__main__":
    unittest.main()
