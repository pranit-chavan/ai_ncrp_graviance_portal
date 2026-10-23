"""
Tests for Module G — Speech-to-Text (Whisper)

Tests the module's API surface, validation logic, language support, and error
handling WITHOUT requiring Whisper or actual audio files to be present.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.speech_to_text import (
    _validate_audio_file,
    _error_result,
    get_supported_languages,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_LANGUAGES,
    MAX_DURATION_SECONDS,
)


class TestSupportedLanguages(unittest.TestCase):
    """Verify that all major Indian languages are declared."""

    def test_hindi_supported(self):
        langs = get_supported_languages()
        self.assertIn("hi", langs)
        self.assertEqual(langs["hi"], "Hindi")

    def test_tamil_supported(self):
        self.assertIn("ta", SUPPORTED_LANGUAGES)

    def test_telugu_supported(self):
        self.assertIn("te", SUPPORTED_LANGUAGES)

    def test_bengali_supported(self):
        self.assertIn("bn", SUPPORTED_LANGUAGES)

    def test_marathi_supported(self):
        self.assertIn("mr", SUPPORTED_LANGUAGES)

    def test_gujarati_supported(self):
        self.assertIn("gu", SUPPORTED_LANGUAGES)

    def test_kannada_supported(self):
        self.assertIn("kn", SUPPORTED_LANGUAGES)

    def test_malayalam_supported(self):
        self.assertIn("ml", SUPPORTED_LANGUAGES)

    def test_punjabi_supported(self):
        self.assertIn("pa", SUPPORTED_LANGUAGES)

    def test_urdu_supported(self):
        self.assertIn("ur", SUPPORTED_LANGUAGES)

    def test_english_supported(self):
        self.assertIn("en", SUPPORTED_LANGUAGES)

    def test_at_least_11_languages(self):
        self.assertGreaterEqual(len(SUPPORTED_LANGUAGES), 11)

    def test_get_supported_languages_returns_copy(self):
        """Ensure the public function returns a copy, not a reference."""
        langs = get_supported_languages()
        langs["xx"] = "Test"
        self.assertNotIn("xx", SUPPORTED_LANGUAGES)


class TestSupportedExtensions(unittest.TestCase):
    """Verify audio format coverage."""

    def test_wav_supported(self):
        self.assertIn(".wav", SUPPORTED_EXTENSIONS)

    def test_mp3_supported(self):
        self.assertIn(".mp3", SUPPORTED_EXTENSIONS)

    def test_m4a_supported(self):
        self.assertIn(".m4a", SUPPORTED_EXTENSIONS)

    def test_ogg_supported(self):
        self.assertIn(".ogg", SUPPORTED_EXTENSIONS)

    def test_flac_supported(self):
        self.assertIn(".flac", SUPPORTED_EXTENSIONS)

    def test_webm_supported(self):
        self.assertIn(".webm", SUPPORTED_EXTENSIONS)


class TestAudioFileValidation(unittest.TestCase):
    """Test the file validation guard."""

    def test_nonexistent_file_rejected(self):
        valid, msg = _validate_audio_file("/nonexistent/path/audio.wav")
        self.assertFalse(valid)
        self.assertIn("not found", msg.lower())

    def test_unsupported_extension_rejected(self):
        # Create a temp file with wrong extension
        fd, path = tempfile.mkstemp(suffix=".txt")
        try:
            os.close(fd)
            valid, msg = _validate_audio_file(path)
            self.assertFalse(valid)
            self.assertIn("unsupported", msg.lower())
        finally:
            os.unlink(path)

    def test_valid_wav_file_accepted(self):
        fd, path = tempfile.mkstemp(suffix=".wav")
        try:
            os.write(fd, b"RIFF" + b"\x00" * 100)
            os.close(fd)
            valid, msg = _validate_audio_file(path)
            self.assertTrue(valid)
            self.assertEqual(msg, "")
        finally:
            os.unlink(path)

    def test_valid_mp3_file_accepted(self):
        fd, path = tempfile.mkstemp(suffix=".mp3")
        try:
            os.write(fd, b"\xff\xfb" + b"\x00" * 100)
            os.close(fd)
            valid, msg = _validate_audio_file(path)
            self.assertTrue(valid)
        finally:
            os.unlink(path)


class TestErrorResult(unittest.TestCase):
    """Test the standardised error result builder."""

    def test_error_result_structure(self):
        import time
        result = _error_result("test error", time.time())
        self.assertFalse(result["ok"])
        self.assertEqual(result["text"], "")
        self.assertEqual(result["error"], "test error")
        self.assertEqual(result["language"], "unknown")
        self.assertIsInstance(result["segments"], list)
        self.assertIsInstance(result["latency_seconds"], float)

    def test_error_result_has_all_keys(self):
        import time
        result = _error_result("msg", time.time())
        expected_keys = {"ok", "text", "language", "language_name", "language_prob",
                         "segments", "duration_seconds", "model_used", "latency_seconds", "error"}
        self.assertEqual(set(result.keys()), expected_keys)


class TestTranscribeAudioMocked(unittest.TestCase):
    """Test transcribe_audio with a mocked Whisper model."""

    @patch("modules.speech_to_text._load_model")
    def test_successful_transcription(self, mock_load):
        from modules.speech_to_text import transcribe_audio

        # Create a dummy audio file
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.write(fd, b"RIFF" + b"\x00" * 100)
        os.close(fd)

        try:
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {
                "text": "mera paisa gaya hai please help",
                "language": "hi",
                "language_prob": 0.92,
                "segments": [
                    {"start": 0.0, "end": 3.5, "text": "mera paisa gaya hai"},
                    {"start": 3.5, "end": 5.0, "text": "please help"},
                ],
            }
            mock_load.return_value = mock_model

            result = transcribe_audio(path, model_name="base")

            self.assertTrue(result["ok"])
            self.assertIn("paisa", result["text"])
            self.assertEqual(result["language"], "hi")
            self.assertEqual(result["language_name"], "Hindi")
            self.assertAlmostEqual(result["language_prob"], 0.92, places=2)
            self.assertEqual(len(result["segments"]), 2)
            self.assertGreater(result["duration_seconds"], 0)
            self.assertIsNone(result["error"])
        finally:
            os.unlink(path)

    @patch("modules.speech_to_text._load_model")
    def test_language_hint_forwarded(self, mock_load):
        from modules.speech_to_text import transcribe_audio

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.write(fd, b"RIFF" + b"\x00" * 100)
        os.close(fd)

        try:
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {
                "text": "test", "language": "ta", "language_prob": 0.85,
                "segments": [{"start": 0.0, "end": 1.0, "text": "test"}],
            }
            mock_load.return_value = mock_model

            result = transcribe_audio(path, language="ta", model_name="base")

            # Verify language was passed to whisper
            call_kwargs = mock_model.transcribe.call_args[1]
            self.assertEqual(call_kwargs["language"], "ta")
            self.assertTrue(result["ok"])
        finally:
            os.unlink(path)

    def test_bytes_input_accepted(self):
        from modules.speech_to_text import transcribe_audio

        # This will fail at model loading (which is fine for testing the bytes → file path conversion)
        with patch("modules.speech_to_text._load_model", side_effect=ImportError("test")):
            result = transcribe_audio(b"fake audio bytes", model_name="base")
            self.assertFalse(result["ok"])
            self.assertIn("test", result["error"])

    def test_invalid_source_type_rejected(self):
        from modules.speech_to_text import transcribe_audio
        result = transcribe_audio(12345)
        self.assertFalse(result["ok"])
        self.assertIn("must be", result["error"])


class TestMaxDuration(unittest.TestCase):
    """Verify the max duration constant is reasonable."""

    def test_max_duration_is_10_minutes(self):
        self.assertEqual(MAX_DURATION_SECONDS, 600)


if __name__ == "__main__":
    unittest.main()
