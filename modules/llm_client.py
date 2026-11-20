"""Shared local Ollama client for the complaint-assistant LLM features."""

import json
import os
from urllib.request import Request, urlopen


DEFAULT_MODEL = "qwen2.5:3b"


class OllamaError(RuntimeError):
    pass


def configured_model():
    return os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def ollama_chat(messages, model=None, temperature=0.2, json_mode=False, think=None,
                num_predict=None, timeout=None):
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model_name = model or configured_model()
    request_body = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "30m"),
        "options": {
            "temperature": temperature,
            "num_ctx": int(os.environ.get("OLLAMA_NUM_CTX", "2048")),
        },
    }
    if num_predict is not None:
        request_body["options"]["num_predict"] = num_predict
    if json_mode:
        request_body["format"] = "json"
    if think is not None:
        request_body["think"] = think

    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout_seconds = timeout or int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "90"))
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise OllamaError(f"Ollama request failed: {type(exc).__name__}: {str(exc)[:180]}") from exc

    message = payload.get("message", {}).get("content", "").strip()
    if not message:
        raise OllamaError("Ollama returned an empty response")
    return message
