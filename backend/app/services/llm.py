"""OpenRouter client.

Deliberately the only module that performs network I/O for the assistant, so
tests can replace one function and exercise the whole triage flow offline. CI
has no API key and must never make a real call.
"""

import json
import logging
import urllib.error
import urllib.request

from flask import current_app

logger = logging.getLogger(__name__)

DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"


def is_configured() -> bool:
    return bool(current_app.config.get("OPENROUTER_API_KEY"))


def complete(messages: list[dict], temperature: float = 0.2, max_tokens: int = 700) -> str | None:
    """Return the assistant's reply text, or None if the call cannot be made.

    Never raises. Every caller has a deterministic fallback, so an outage
    degrades the assistant rather than breaking it.
    """
    api_key = current_app.config.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.info("OPENROUTER_API_KEY not set - using offline fallback")
        return None

    payload = {
        "model": current_app.config.get("OPENROUTER_MODEL", "openrouter/auto"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    url = current_app.config.get("OPENROUTER_URL", DEFAULT_URL)
    if not url.startswith("https://"):
        # A misconfigured OPENROUTER_URL would otherwise let urlopen follow a
        # file:// or custom scheme and read from the server's own disk.
        logger.error("OPENROUTER_URL must be an https:// endpoint - refusing to call")
        return None

    request = urllib.request.Request(  # noqa: S310 - scheme validated above
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "CareSphere Health Assistant",
        },
        method="POST",
    )

    timeout = current_app.config.get("OPENROUTER_TIMEOUT", 40)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310  # nosec B310
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.warning("OpenRouter HTTP %s", exc.code)
        return None
    except Exception as exc:  # noqa: BLE001 - any failure falls back
        logger.warning("OpenRouter call failed: %s", exc)
        return None

    choices = body.get("choices") or []
    if not choices:
        return None
    return (choices[0].get("message") or {}).get("content")
