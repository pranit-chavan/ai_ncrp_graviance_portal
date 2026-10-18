"""
MODULE G — Speech-to-Text (Voice Input)

Converts audio recordings from citizens into text using OpenAI's Whisper
model running locally. This allows citizens who are uncomfortable typing,
semi-literate, or in extreme distress to simply speak their complaint
into a phone or microphone.

WHY THIS MATTERS
    Many cyber fraud victims in India are elderly, semi-literate, or in such
    emotional distress that typing a coherent complaint is beyond their ability
    in that moment. A recorded voice note — even a shaky, tearful, code-mixed
    Hinglish one — is far easier to produce than structured text. This module
    bridges that gap.

    The transcribed text feeds directly into the same pipeline as typed text:
      Module A  — narrative standardisation
      Module B  — classification
      Module C  — entity extraction (from transcribed text)
      Module D  — legal mapping
      Module E  — case file

DESIGN DECISION: Whisper (local), not a cloud STT API.
    The same air-gap principle as the rest of this project. Citizen voice
    recordings containing financial details, Aadhaar numbers, and emotional
    testimony MUST NOT leave the machine. Whisper runs fully offline after
    the one-time model download.

DESIGN DECISION: Multi-language support by default.
    Whisper natively supports Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati,
    Kannada, Malayalam, Punjabi, Urdu, and English. We let Whisper auto-detect
    the spoken language, or accept a hint from the dashboard. This handles the
    reality that citizens file complaints in their mother tongue.

SUPPORTED LANGUAGES (Indian)
    hi  — Hindi           ta  — Tamil          te  — Telugu
    bn  — Bengali         mr  — Marathi        gu  — Gujarati
    kn  — Kannada         ml  — Malayalam       pa  — Punjabi
    ur  — Urdu            en  — English

SETUP
    pip install openai-whisper

    First run will download the model (~1 GB for 'base', ~2.9 GB for 'medium').
    Runs on CPU. For faster transcription, install torch with CUDA support.

USAGE
    from modules.speech_to_text import transcribe_audio

    result = transcribe_audio("complaint.wav")
    result["text"]              full transcribed text
    result["language"]          detected language code (e.g. "hi")
    result["language_name"]     human-readable language name
    result["segments"]          list of timestamped segments
    result["duration_seconds"]  audio duration
    result["ok"]                True if transcription succeeded
"""

import os
import time
import tempfile
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language metadata for Indian languages supported by Whisper
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "en": "English",
    "or": "Odia",
    "as": "Assamese",
    "ne": "Nepali",
    "si": "Sinhala",
    "sa": "Sanskrit",
}

# Supported audio file extensions
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".mp4", ".wma", ".aac"}

# Maximum audio duration in seconds (10 minutes — long enough for a detailed
# complaint, short enough to keep inference reasonable on CPU)
MAX_DURATION_SECONDS = 600

# ---------------------------------------------------------------------------
# Model singleton — loaded once, reused across calls
# ---------------------------------------------------------------------------

_whisper_model = {"instance": None, "model_name": None}


def _load_model(model_name="base"):
    """
    Load or return cached Whisper model.

    Model sizes and approximate requirements:
        tiny   — 39M params, ~1 GB VRAM, fastest but lowest accuracy
        base   — 74M params, ~1 GB VRAM, good balance for Indian languages
        small  — 244M params, ~2 GB VRAM, better accuracy
        medium — 769M params, ~5 GB VRAM, best for code-mixed Hinglish
        large  — 1550M params, ~10 GB VRAM, highest accuracy (GPU recommended)

    For CPU-only deployment (typical government hardware), 'base' is recommended.
    """
    if _whisper_model["instance"] is not None and _whisper_model["model_name"] == model_name:
        return _whisper_model["instance"]

    try:
        import whisper
    except ImportError:
        raise ImportError(
            "OpenAI Whisper is not installed. Install it with:\n"
            "    pip install openai-whisper\n"
            "On Windows, you may also need ffmpeg:\n"
            "    choco install ffmpeg   OR   winget install ffmpeg"
        )

    logger.info(f"Loading Whisper model '{model_name}' (first load downloads ~1 GB)...")
    model = whisper.load_model(model_name)
    _whisper_model["instance"] = model
    _whisper_model["model_name"] = model_name
    logger.info(f"Whisper model '{model_name}' loaded successfully.")
    return model


def _validate_audio_file(file_path):
    """Validate that the file exists, has a supported extension, and is within size limits."""
    if not os.path.isfile(file_path):
        return False, f"File not found: {file_path}"

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False, (
            f"Unsupported audio format '{ext}'. "
            f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > 100:
        return False, f"Audio file too large ({size_mb:.1f} MB). Maximum: 100 MB."

    return True, ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe_audio(audio_source, language=None, model_name="base", verbose=False):
    """
    Transcribe an audio file to text using Whisper.

    Parameters
    ----------
    audio_source : str or bytes
        Either a file path to an audio file, or raw audio bytes.
        When bytes are provided, they are written to a temp file first.
    language : str, optional
        ISO 639-1 language code (e.g. 'hi' for Hindi). If None, Whisper
        auto-detects the language. Providing a hint improves accuracy for
        short recordings.
    model_name : str
        Whisper model size: 'tiny', 'base', 'small', 'medium', 'large'.
        Default 'base' balances accuracy and speed for CPU deployment.
    verbose : bool
        If True, prints progress to stdout.

    Returns
    -------
    dict with keys:
        ok              : bool — True if transcription succeeded
        text            : str — full transcribed text
        language        : str — detected language code (e.g. 'hi')
        language_name   : str — human-readable language name
        language_prob   : float — detection confidence (0–1)
        segments        : list of dict — timestamped segments with text
        duration_seconds: float — audio duration in seconds
        model_used      : str — which Whisper model was used
        latency_seconds : float — wall-clock time for transcription
        error           : str — error message if ok is False
    """
    log = print if verbose else (lambda *a, **k: None)
    t0 = time.time()

    # Handle bytes input — write to temp file
    temp_path = None
    if isinstance(audio_source, (bytes, bytearray)):
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".wav")
            with os.fdopen(fd, "wb") as f:
                f.write(audio_source)
            audio_path = temp_path
            log(f"[G] Wrote {len(audio_source)} bytes to temp file")
        except Exception as e:
            return _error_result(f"Failed to write audio bytes to temp file: {e}", t0)
    elif isinstance(audio_source, str):
        audio_path = audio_source
    else:
        return _error_result(f"audio_source must be a file path (str) or bytes, got {type(audio_source)}", t0)

    try:
        # Validate
        valid, msg = _validate_audio_file(audio_path)
        if not valid:
            return _error_result(msg, t0)

        # Load model
        log(f"[G] Loading Whisper model '{model_name}'...")
        model = _load_model(model_name)

        # Build transcription options
        options = {
            "fp16": False,  # CPU-safe: disable FP16 to avoid CUDA requirement
            "verbose": verbose,
        }

        if language:
            lang_code = language.lower().strip()
            if lang_code in SUPPORTED_LANGUAGES:
                options["language"] = lang_code
                log(f"[G] Language hint: {SUPPORTED_LANGUAGES[lang_code]} ({lang_code})")
            else:
                log(f"[G] Unknown language code '{lang_code}', letting Whisper auto-detect")

        # Transcribe
        log(f"[G] Transcribing audio: {os.path.basename(audio_path)}...")
        result = model.transcribe(audio_path, **options)

        elapsed = time.time() - t0
        text = (result.get("text") or "").strip()
        detected_lang = result.get("language", "unknown")
        lang_name = SUPPORTED_LANGUAGES.get(detected_lang, detected_lang.capitalize())

        # Extract segments with timestamps
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
            })

        # Estimate audio duration from last segment
        duration = segments[-1]["end"] if segments else 0.0

        if duration > MAX_DURATION_SECONDS:
            log(f"[G] WARNING: Audio is {duration:.0f}s (>{MAX_DURATION_SECONDS}s limit)")

        log(f"[G] Transcription complete: {len(text)} chars, language={lang_name}, "
            f"duration={duration:.1f}s, latency={elapsed:.1f}s")

        return {
            "ok": True,
            "text": text,
            "language": detected_lang,
            "language_name": lang_name,
            "language_prob": round(float(result.get("language_prob", 0.0)), 4),
            "segments": segments,
            "duration_seconds": round(duration, 2),
            "model_used": model_name,
            "latency_seconds": round(elapsed, 2),
            "error": None,
        }

    except ImportError as e:
        return _error_result(str(e), t0)
    except Exception as e:
        logger.exception("Speech-to-text transcription failed")
        return _error_result(f"Transcription failed: {e}", t0)
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def transcribe_audio_bytes(audio_bytes, filename="recording.wav", **kwargs):
    """
    Convenience wrapper for transcribing in-memory audio bytes.

    Useful when called from the Streamlit dashboard where audio comes from
    st.file_uploader as an UploadedFile object.

    Parameters
    ----------
    audio_bytes : bytes or file-like
        Raw audio data. If file-like (e.g. Streamlit UploadedFile), .read()
        is called automatically.
    filename : str
        Original filename (used to infer extension for temp file).
    **kwargs
        Forwarded to transcribe_audio().
    """
    if hasattr(audio_bytes, "seek"):
        try:
            audio_bytes.seek(0)
        except Exception:
            pass
    if hasattr(audio_bytes, "read"):
        audio_bytes = audio_bytes.read()

    # Determine extension from filename
    ext = os.path.splitext(filename)[1].lower() if filename else ".wav"
    if ext not in SUPPORTED_EXTENSIONS:
        ext = ".wav"

    # Write to temp file with correct extension
    fd, temp_path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(audio_bytes)
        return transcribe_audio(temp_path, **kwargs)
    finally:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def get_supported_languages():
    """Return dict of supported language codes → names."""
    return dict(SUPPORTED_LANGUAGES)


def is_whisper_available():
    """Check if Whisper is installed and importable."""
    try:
        import whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _error_result(message, t0):
    """Build a standardised error result dict."""
    return {
        "ok": False,
        "text": "",
        "language": "unknown",
        "language_name": "Unknown",
        "language_prob": 0.0,
        "segments": [],
        "duration_seconds": 0.0,
        "model_used": "",
        "latency_seconds": round(time.time() - t0, 2),
        "error": message,
    }


# ---------------------------------------------------------------------------
# CLI entry point for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="MODULE G — Speech-to-Text (Whisper)")
    ap.add_argument("audio", help="Path to audio file (.wav, .mp3, .m4a, .ogg, .flac, etc.)")
    ap.add_argument("--language", "-l", default=None,
                    help="Language hint (e.g. 'hi' for Hindi). Auto-detects if omitted.")
    ap.add_argument("--model", "-m", default="base",
                    choices=["tiny", "base", "small", "medium", "large"],
                    help="Whisper model size (default: base)")
    ap.add_argument("--segments", "-s", action="store_true",
                    help="Print timestamped segments")
    ap.add_argument("--check", action="store_true",
                    help="Check if Whisper is installed and exit")
    args = ap.parse_args()

    if args.check:
        if is_whisper_available():
            print("Whisper is installed and ready.")
            print(f"Supported languages: {', '.join(f'{v} ({k})' for k, v in SUPPORTED_LANGUAGES.items())}")
        else:
            print("Whisper is NOT installed. Run: pip install openai-whisper")
        exit(0)

    result = transcribe_audio(args.audio, language=args.language, model_name=args.model, verbose=True)

    if result["ok"]:
        print("\n" + "=" * 70)
        print("TRANSCRIPTION RESULT")
        print("=" * 70)
        print(f"Language : {result['language_name']} ({result['language']}) "
              f"[confidence: {result['language_prob']:.1%}]")
        print(f"Duration : {result['duration_seconds']:.1f} seconds")
        print(f"Latency  : {result['latency_seconds']:.1f} seconds")
        print(f"Model    : {result['model_used']}")
        print("-" * 70)
        print(result["text"])
        print("-" * 70)

        if args.segments and result["segments"]:
            print("\nTIMESTAMPED SEGMENTS:")
            for seg in result["segments"]:
                print(f"  [{seg['start']:>7.2f}s → {seg['end']:>7.2f}s]  {seg['text']}")
    else:
        print(f"\nERROR: {result['error']}")
