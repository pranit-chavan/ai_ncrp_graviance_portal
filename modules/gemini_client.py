"""Minimal Gemini Developer API client using the standard library."""

import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


def _load_project_env():
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            name, value = name.strip(), value.strip().strip("\"'")
            if name in {"GEMINI_API_KEY", "GOOGLE_API_KEY"} and name not in os.environ:
                os.environ[name] = value


def configured_gemini_model():
    return os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def gemini_generate_content(prompt, system_instruction, response_mime_type="application/json",
                            max_output_tokens=256, timeout=None, model=None):
    _load_project_env()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini API key is not configured (set GEMINI_API_KEY)")

    model = model or configured_gemini_model()
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + quote(model, safe="") + ":generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": max_output_tokens,
            **({"responseMimeType": response_mime_type} if response_mime_type else {}),
        },
    }
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    timeout_seconds = timeout or int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "45"))
    transient_statuses = {408, 429, 500, 502, 503, 504}
    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:240]
            if exc.code in transient_statuses and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Gemini API returned HTTP {exc.code}: {detail}") from exc
        except (TimeoutError, URLError, OSError) as exc:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Gemini API request failed after 3 attempts: {type(exc).__name__}") from exc

    candidates = result.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        reason = candidates[0].get("finishReason", "no candidate") if candidates else "no candidate"
        raise RuntimeError(f"Gemini API returned no text ({reason})")
    return text
