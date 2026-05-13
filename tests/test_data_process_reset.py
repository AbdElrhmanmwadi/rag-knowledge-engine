import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from helpers.process_reset import reset_project_processing_state


class ProcessResetTests(unittest.IsolatedAsyncioTestCase):
    async def test_reset_deletes_collection_before_chunks(self):
        events = []

        async def delete_collection(*, collection_name):
            events.append(("collection", collection_name))
            return True

        async def delete_chunks_by_project_id(*, project_id):
            events.append(("chunks", project_id))
            return 3

        vectordb_client = AsyncMock()
        vectordb_client.delete_collection.side_effect = delete_collection

        chunk_model = AsyncMock()
        chunk_model.delete_chunks_by_project_id.side_effect = delete_chunks_by_project_id

        await reset_project_processing_state(
            chunk_model=chunk_model,
            vectordb_client=vectordb_client,
            collection_name="collection_384_10",
            project_id="10",
        )

        self.assertEqual(
            events,
            [("collection", "collection_384_10"), ("chunks", "10")],
        )


if __name__ == "__main__":
    unittest.main()
