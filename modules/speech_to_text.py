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
import threading

logger = logging.getLogger(__name__)

# Domain prompt conditioning Whisper language model priors for Indian cyber fraud complaints
CYBER_CRIME_INITIAL_PROMPT = (
    "National Cyber Crime Reporting Portal (NCRP) complaint in India. "
    "साइबर अपराध शिकायत, पुलिस एफआईआर, 1930 हेल्पलाइन। "
    "मेरे बैंक खाते से पैसे कट गए, फ्रॉड हुआ, अनधिकृत ट्रांजैक्शन, फर्जी कॉल, ओटीपी, यूपीआई पिन, यूटीआर। "
    "HDFC Bank, State Bank of India, SBI, ICICI Bank, Axis Bank, PNB, Kotak Mahindra, PhonePe, Google Pay, GPay, Paytm, "
    "WhatsApp, Telegram, debited, credited, unauthorized transaction, OTP, UPI PIN, UTR, freeze account."
)

LANGUAGE_PROMPTS = {
    "hi": (
        "राष्ट्रीय साइबर अपराध रिपोर्टिंग पोर्टल (NCRP) 1930 हेल्पलाइन। "
        "मेरे बैंक खाते से पैसे कट गए, फ्रॉड हुआ, अनधिकृत ट्रांजैक्शन, फर्जी कॉल, ओटीपी, यूपीआई पिन, यूटीआर। "
        "SBI, HDFC, ICICI, Axis Bank, PhonePe, Google Pay, GPay, Paytm, WhatsApp, Telegram, debited, OTP, UPI PIN, UTR."
    ),
    "mr": (
        "राष्ट्रीय सायबर गुन्हे नोंदणी पोर्टल (NCRP) 1930 हेल्पलाइन. "
        "माझ्या बँक खात्यातून पैसे कापले गेले, ऑनलाइन फसवणूक झाली, अनधिकृत व्यवहार, बनावट कॉल, ओटीपी, यूपीआय पिन, यूटीआर. "
        "SBI, HDFC, ICICI, Axis Bank, PhonePe, Google Pay, Paytm, WhatsApp, Telegram, debited, OTP, UPI PIN."
    ),
    "bn": (
        "জাতীয় সাইবার ক্রাইম রিপোর্টিং পোর্টাল (NCRP) অভিযোগ, ১৯৩০ হেল্পলাইন। "
        "আমার ব্যাঙ্ক অ্যাকাউন্ট থেকে টাকা কেটে নেওয়া হয়েছে, প্রতারণা হয়েছে, ওটিপি, ইউপিআই পিন, ইউটিआर। "
        "SBI, HDFC, ICICI, PhonePe, Google Pay, Paytm, WhatsApp, Telegram, debited, OTP, UPI PIN."
    ),
    "ta": (
        "தேசிய இணைய குற்றப் பதிவு போர்டல் (NCRP) புகார், 1930 உதவி எண். "
        "எனது வங்கிக் கணக்கிலிருந்து பணம் எடுக்கப்பட்டது, ஆன்லைன் மோசடி, அங்கீகரிக்கப்படாத பரிவர்த்தனை, OTP, UPI PIN, UTR. "
        "SBI, HDFC, ICICI, PhonePe, Google Pay, Paytm, WhatsApp, Telegram."
    ),
    "te": (
        "జాతీయ సైబర్ క్రైమ్ రిపోర్టింగ్ పోర్టల్ (NCRP) ఫిర్యాదు, 1930 హెల్ప్‌లైన్. "
        "నా బ్యాంక్ ఖాతా నుండి డబ్బు కట్ అయింది, ఆన్‌లైన్ మోసం, అనధికారిక లావాదేవీ, OTP, UPI PIN, UTR. "
        "SBI, HDFC, ICICI, PhonePe, Google Pay, Paytm, WhatsApp, Telegram."
    ),
    "gu": (
        "રાષ્ટ્રીય સાયબર ક્રાઇમ રિપોર્ટિંગ પોર્ટલ (NCRP) ફરિયાદ, ૧૯૩૦ હેલ્પલાઇન. "
        "મારા બેંક ખાતામાંથી પૈસા કપાઈ ગયા, ઓનલાઇન છેતરપિંડી, અનધિકૃત ટ્રાન્ઝેક્શન, OTP, UPI PIN, UTR. "
        "SBI, HDFC, ICICI, PhonePe, Google Pay, Paytm, WhatsApp, Telegram."
    ),
    "pa": (
        "ਰਾਸ਼ਟਰੀ ਸਾਈਬਰ ਕ੍ਰਾਈਮ ਰਿਪੋਰਟਿੰਗ ਪੋਰਟਲ (NCRP) ਸ਼ਿਕਾਇਤ, 1930 ਹੈਲਪਲਾਈਨ। "
        "ਮੇਰੇ ਬੈਂਕ ਖਾਤੇ ਵਿੱਚੋਂ ਪੈਸੇ ਕੱਟੇ ਗਏ, ਆਨਲਾਈਨ ਧੋਖਾਧੜੀ, OTP, UPI PIN, UTR, SBI, HDFC, PhonePe, Google Pay."
    ),
    "ur": (
        "قومی سائبر کرائم رپورٹنگ پورٹل (NCRP) شکایت، 1930 ہیلپ لائن۔ "
        "میرے بینک اکاؤنٹ سے پیسے کٹ گئے، آن لائن فراڈ، او ٹی پی، یو پی آئی پن، یو ٹی آر۔ "
        "SBI, HDFC, ICICI, PhonePe, Google Pay, Paytm, WhatsApp, Telegram."
    ),
    "en": (
        "NCRP, cyber fraud, unauthorized transaction, OTP, UPI, UTR, SBI, HDFC, ICICI, PhonePe, Google Pay, Paytm."
    ),
}


def _post_process_cyber_transcription(text: str) -> str:
    """Keep the words Whisper heard; the user can correct them in the transcript."""
    return text.strip() if text else text

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
_whisper_lock = threading.Lock()


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
    with _whisper_lock:
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

        logger.info(f"Loading Whisper model '{model_name}' (first run downloads the model)...")
        model = whisper.load_model(model_name, device=os.getenv("WHISPER_DEVICE", "cpu"))
        _whisper_model["instance"] = model
        _whisper_model["model_name"] = model_name
        logger.info(f"Whisper model '{model_name}' loaded successfully.")
        return model


def warmup_speech_model(model_name="base"):
    """Load the cached model before the user records; this never downloads weights."""
    model_path = os.path.join(os.path.expanduser("~"), ".cache", "whisper", f"{model_name}.pt")
    if not os.path.isfile(model_path):
        return False
    _load_model(model_name)
    return True


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

def transcribe_audio(audio_source, language=None, model_name="base", initial_prompt=None, task="transcribe", verbose=False, **kwargs):
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
    initial_prompt : str, optional
        Optional text prefix / domain hints for conditioning Whisper.
        Defaults to CYBER_CRIME_INITIAL_PROMPT.
    task : str, optional
        'transcribe' (default) to transcribe in original language,
        or 'translate' to translate spoken audio directly into English.
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

        # Reject digital silence before neural decoding. Whisper's domain prompt can
        # otherwise be echoed as hallucinated speech, and CPU inference is costly.
        import numpy as np
        import whisper
        audio = whisper.load_audio(audio_path, sr=16000)
        if audio.size == 0 or (float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))) < 0.001
                               and float(np.max(np.abs(audio))) < 0.005):
            return _error_result("No clear speech detected. Please record again in a quiet place.", t0)

        # Load Whisper only after silence has been rejected. A first model load is
        # noticeable on CPU and should not delay a user who uploaded a blank clip.
        log(f"[G] Loading Whisper model '{model_name}'...")
        model = _load_model(model_name)

        # Optimize CPU threads for PyTorch inference
        try:
            import torch
            if not torch.cuda.is_available():
                torch.set_num_threads(min(8, os.cpu_count() or 4))
        except Exception:
            pass

        # Select language code
        lang_code = language.lower().strip() if language else None
        if lang_code and lang_code not in SUPPORTED_LANGUAGES:
            log(f"[G] Unknown language code '{lang_code}', letting Whisper auto-detect")
            lang_code = None

        # Determine prompt conditioning
        prompt_to_use = initial_prompt
        if not prompt_to_use:
            if (task or "").lower() == "translate":
                prompt_to_use = LANGUAGE_PROMPTS.get("en", CYBER_CRIME_INITIAL_PROMPT)
            elif lang_code and lang_code in LANGUAGE_PROMPTS:
                prompt_to_use = LANGUAGE_PROMPTS[lang_code]
            else:
                prompt_to_use = CYBER_CRIME_INITIAL_PROMPT

        # Build transcription options - single-pass greedy decode for real-time responsiveness
        options = {
            "fp16": str(getattr(model, "device", "cpu")).startswith("cuda"),  # Use GPU acceleration when available
            "verbose": verbose,
            "task": task or "transcribe",
            "initial_prompt": prompt_to_use,
            "temperature": 0.0,                   # Fast single-pass, disables slow 6-step temperature fallback loop
            "beam_size": 1,                       # Greedy decode (3x-5x faster than beam search on CPU)
            "best_of": 1,                         # 1 candidate per chunk
            "condition_on_previous_text": False,   # Avoids repetitive context re-evaluation delay
        }

        if lang_code:
            options["language"] = lang_code
            log(f"[G] Language set: {SUPPORTED_LANGUAGES.get(lang_code, lang_code)} ({lang_code})")

        # Transcribe
        log(f"[G] Transcribing audio: {os.path.basename(audio_path)}...")
        result = model.transcribe(audio, **options)

        elapsed = time.time() - t0
        detected_segments = result.get("segments", [])
        # A domain prompt can make Whisper repeat its prompt over silence. Do not
        # turn a high no-speech score into facts in a citizen's account.
        speech_segments = [seg for seg in detected_segments
                           if float(seg.get("no_speech_prob", 0.0)) < 0.70]
        raw_text = " ".join(str(seg.get("text", "")).strip() for seg in speech_segments).strip()
        text = _post_process_cyber_transcription(raw_text)
        detected_lang = result.get("language", "unknown")
        lang_name = SUPPORTED_LANGUAGES.get(detected_lang, detected_lang.capitalize())

        # Extract segments with timestamps
        segments = []
        for seg in speech_segments:
            segments.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": _post_process_cyber_transcription(seg["text"].strip()),
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
        # Keep the cached model weights resident, but return unused inference
        # buffers to the GPU so Ollama and the next audio request have headroom.
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
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
