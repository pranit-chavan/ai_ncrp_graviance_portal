import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from modules.gemini_client import gemini_generate_content


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        result = {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps({"reply": "OK"})}]}}
            ]
        }
        return json.dumps(result).encode("utf-8")


class TestGeminiClient(unittest.TestCase):
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    @patch("modules.gemini_client.time.sleep")
    @patch("modules.gemini_client.urlopen")
    def test_retries_transient_server_error(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [
            HTTPError("https://example.test", 503, "Unavailable", {}, io.BytesIO(b"busy")),
            _Response(),
        ]

        result = gemini_generate_content("prompt", "instructions")

        self.assertEqual(json.loads(result), {"reply": "OK"})
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    @patch("modules.gemini_client.time.sleep")
    @patch("modules.gemini_client.urlopen")
    def test_does_not_retry_client_error(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = HTTPError(
            "https://example.test", 400, "Bad Request", {}, io.BytesIO(b"invalid request")
        )

        with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
            gemini_generate_content("prompt", "instructions")

        self.assertEqual(mock_urlopen.call_count, 1)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
