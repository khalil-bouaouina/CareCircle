"""HTTP call to the model provider (A1). Two strings in, one string out.

This file must not know what a statement or a visit is.
"""

from __future__ import annotations

import httpx

from .. import config

API_URL = "https://api.anthropic.com/v1/messages"


class ModelUnavailable(Exception):
    """Missing key, HTTP error, timeout, or an unexpected response shape."""


def call_model(system: str, user: str, timeout: float = 8.0) -> str:
    """Send one message, return the raw text of the first content block.

    The eight-second timeout is deliberate: a brief arriving in nine seconds is
    a failed demo, and the fallback renders instantly. Prefer a slightly worse
    brief over a stalled screen.
    """
    if not config.ANTHROPIC_API_KEY:
        raise ModelUnavailable("ANTHROPIC_API_KEY is not set")

    try:
        response = httpx.post(
            API_URL,
            timeout=timeout,
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": config.ANTHROPIC_MODEL,
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        response.raise_for_status()
        # Not content[0]: a thinking-capable model puts a thinking block first.
        # Take the first text block so the model is swappable in .env.
        blocks = response.json()["content"]
        return next(b["text"] for b in blocks if b.get("type") == "text")
    except Exception as exc:  # httpx errors, JSON errors, missing keys
        raise ModelUnavailable(str(exc)) from exc
