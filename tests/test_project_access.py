import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from models.db_schemes.minirag.scheme import Project
from services.project_access import (
    check_project_access,
    get_project_for_user,
    user_has_project_access,
)


class ProjectAccessTests(unittest.TestCase):
    def test_user_has_project_access_owner_only(self):
        project = Project(project_id=1, owner_id=10)
        self.assertTrue(user_has_project_access(project, 10))
        self.assertFalse(user_has_project_access(project, 11))

    def test_check_project_access_raises_forbidden(self):
        project = Project(project_id=1, owner_id=10)
        with self.assertRaises(HTTPException) as ctx:
            check_project_access(project, 99)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_get_project_for_user_not_found(self):
        async def run():
            db = AsyncMock()
            db.scalar = AsyncMock(return_value=None)
            with self.assertRaises(HTTPException) as ctx:
                await get_project_for_user(db, project_id=5, user_id=1, create_if_missing=False)
            self.assertEqual(ctx.exception.status_code, 404)

        import asyncio

        asyncio.run(run())

    def test_get_project_for_user_forbidden(self):
        async def run():
            db = AsyncMock()
            db.scalar = AsyncMock(return_value=Project(project_id=5, owner_id=2))
            with self.assertRaises(HTTPException) as ctx:
                await get_project_for_user(db, project_id=5, user_id=1, create_if_missing=False)
            self.assertEqual(ctx.exception.status_code, 403)

        import asyncio

        asyncio.run(run())

    def test_get_project_for_user_creates_when_missing(self):
        async def run():
            db = AsyncMock()
            db.scalar = AsyncMock(return_value=None)
            db.add = MagicMock()
            db.commit = AsyncMock()
            db.refresh = AsyncMock()

            project = await get_project_for_user(
                db, project_id=7, user_id=3, create_if_missing=True
            )
            self.assertEqual(project.project_id, 7)
            self.assertEqual(project.owner_id, 3)
            db.add.assert_called_once()
            db.commit.assert_awaited_once()

        import asyncio

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
