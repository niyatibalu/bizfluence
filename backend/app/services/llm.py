"""LLM layer — Gemini with model fallbacks; offline writers when all models fail."""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings

# Prefer models that still have free-tier headroom on new keys.
# Older 2.0 / 1.5 ids often return 429 with limit:0 — try others before giving up.
_MODELS = (
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
)


def last_llm_status() -> dict[str, Any]:
    return dict(_LAST_STATUS)


_LAST_STATUS: dict[str, Any] = {"ok": False, "mode": "offline", "detail": ""}


def _set_status(ok: bool, mode: str, detail: str = "") -> None:
    _LAST_STATUS.clear()
    _LAST_STATUS.update({"ok": ok, "mode": mode, "detail": detail})


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "resourceexhausted" in msg or "rate" in msg


def generate_json(system: str, user: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    get_settings.cache_clear()
    settings = get_settings()
    if not (settings.gemini_api_key or "").strip():
        _set_status(False, "offline", "No GEMINI_API_KEY")
        return dict(fallback) if fallback is not None else {"error": "no_key"}

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key.strip())
        last_err: Exception | None = None
        for model_name in _MODELS:
            try:
                model = genai.GenerativeModel(
                    model_name,
                    system_instruction=system
                    + "\n\nAlways respond with valid JSON only. No markdown fences.",
                )
                response = model.generate_content(user)
                text = (response.text or "").strip()
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
                data = json.loads(text)
                _set_status(True, "gemini", model_name)
                return data
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                # Quota on one model → try the next; don't abort the whole list
                continue
        _set_status(False, "offline", str(last_err)[:240] if last_err else "gemini_failed")
        return dict(fallback) if fallback is not None else {"error": str(last_err)}
    except Exception as exc:  # noqa: BLE001
        _set_status(False, "offline", str(exc)[:240])
        return dict(fallback) if fallback is not None else {"error": str(exc)}


def generate_text(system: str, user: str, fallback: str = "") -> str:
    get_settings.cache_clear()
    settings = get_settings()
    if not (settings.gemini_api_key or "").strip():
        _set_status(False, "offline", "No GEMINI_API_KEY")
        return fallback

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key.strip())
        last_err: Exception | None = None
        for model_name in _MODELS:
            try:
                model = genai.GenerativeModel(model_name, system_instruction=system)
                response = model.generate_content(user)
                text = (response.text or "").strip()
                if text:
                    _set_status(True, "gemini", model_name)
                    return text
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue
        _set_status(False, "offline", str(last_err)[:240] if last_err else "gemini_failed")
        return fallback
    except Exception as exc:  # noqa: BLE001
        _set_status(False, "offline", str(exc)[:240])
        return fallback
