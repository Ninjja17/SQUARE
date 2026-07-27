"""LLM client wrapper — uses Groq for inference."""
from __future__ import annotations

import json
import logging
from typing import Any

from groq import Groq

from app.config import get_settings

logger = logging.getLogger(__name__)
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        settings = get_settings()
        key = settings.GROQ_API_KEY
        if not key:
            raise ValueError("GROQ_API_KEY environment variable is missing or empty.")
        _client = Groq(api_key=key)
    return _client


def _call_granite(system_prompt: str, user_prompt: str) -> str:
    """Call Groq and return the raw text response."""
    try:
        settings = get_settings()
        client = _get_client()
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            top_p=0.9,
            max_tokens=1500,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("Groq API call failed: %s", exc)
        raise


def call_granite_json(system_prompt: str, user_prompt: str) -> Any:
    """Call Gemini and parse JSON from the response."""
    raw = _call_granite(system_prompt, user_prompt)
    # Extract JSON block if wrapped in markdown fences
    text = raw.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        block = text[start + 3: end]
        if block.startswith("json"):
            block = block[4:]
        text = block.strip()
    return json.loads(text)
