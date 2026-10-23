"""Voice upload endpoint wiring checks using an isolated server data root."""

import asyncio
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from starlette.datastructures import UploadFile


class TestServerVoiceEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_root = tempfile.mkdtemp(prefix="cyberassist-voice-api-")

        import modules.database as database
        import modules.pattern_engine as pattern_engine
        original_db_path = database.DB_PATH
        original_sync = pattern_engine.sync_all_case_files
        database.DB_PATH = os.path.join(cls.test_root, "complaints.db")
        pattern_engine.sync_all_case_files = lambda _path: original_sync(
            os.path.join(cls.test_root, "case_files"),
            db_path=os.path.join(cls.test_root, "case_index.db"),
        )
        try:
            import server
        finally:
            database.DB_PATH = original_db_path
            pattern_engine.sync_all_case_files = original_sync
        server.CASE_DIR = os.path.join(cls.test_root, "case_files")
        server.UPLOAD_DIR = os.path.join(cls.test_root, "uploads")
        cls.server = server

    def test_transcribe_endpoint_forwards_upload_and_language(self):
        audio_bytes = b"fictional audio bytes"
        upload = UploadFile(filename="recording.webm", file=io.BytesIO(audio_bytes))
        mocked_result = {
            "ok": True,
            "text": "My bank account was debited.",
            "language": "mr",
            "latency_seconds": 0.1,
        }

        with patch.object(
            self.server,
            "transcribe_audio_bytes",
            return_value=mocked_result,
        ) as transcribe:
            response = asyncio.run(
                self.server.transcribe_endpoint(file=upload, language="mr")
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.body)["text"], mocked_result["text"])
        transcribe.assert_called_once_with(
            audio_bytes,
            filename="recording.webm",
            language="mr",
            model_name="tiny",
        )


if __name__ == "__main__":
    unittest.main()
