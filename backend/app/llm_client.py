"""
Thin LLM client abstraction — wraps Ollama's HTTP API.

Usage:
    from app.llm_client import call_llm

    response = await call_llm(
        system_prompt="You are a helpful assistant.",
        user_prompt="What is 2 + 2?"
    )

The model and endpoint are configured via OLLAMA_HOST / OLLAMA_MODEL
environment variables (see config.py).
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    timeout: float = 120.0,
    model: Optional[str] = None,
) -> str:
    """
    Call the LLM via Ollama's /api/generate endpoint.

    Args:
        system_prompt: The system-level instruction for the LLM.
        user_prompt: The user-level input (e.g., transcript text).
        temperature: Sampling temperature (low = more deterministic).
        timeout: Request timeout in seconds.
        model: Override the default model from config.

    Returns:
        The LLM's text response as a string.

    Raises:
        httpx.HTTPStatusError: If the Ollama API returns an error status.
        httpx.ConnectError: If Ollama is not reachable.
    """
    settings = get_settings()
    ollama_host = settings.ollama_host.rstrip("/")
    ollama_model = model or settings.ollama_model

    url = f"{ollama_host}/api/generate"

    payload = {
        "model": ollama_model,
        "prompt": user_prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    logger.info(
        "Calling LLM",
        extra={
            "model": ollama_model,
            "system_prompt_length": len(system_prompt),
            "user_prompt_length": len(user_prompt),
        },
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    result = response.json()
    text = result.get("response", "")

    logger.info(
        "LLM response received",
        extra={
            "model": ollama_model,
            "response_length": len(text),
            "total_duration_ns": result.get("total_duration"),
        },
    )

    return text


async def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    timeout: float = 120.0,
    model: Optional[str] = None,
) -> dict | list:
    """
    Call the LLM and parse the response as JSON.

    Attempts to extract JSON from the response even if the LLM wraps it
    in markdown code fences or extra text. On parse failure, retries once
    with a stricter prompt.

    Returns:
        Parsed JSON (dict or list).

    Raises:
        ValueError: If the response cannot be parsed as JSON after retry.
    """
    raw = await call_llm(
        system_prompt, user_prompt,
        temperature=temperature, timeout=timeout, model=model,
    )

    # Attempt 1: parse directly
    parsed = _try_parse_json(raw)
    if parsed is not None:
        return parsed

    # Attempt 2: retry with strict instruction
    logger.warning("LLM JSON parse failed on first attempt, retrying with strict prompt")
    strict_suffix = (
        "\n\nIMPORTANT: Your previous response was not valid JSON. "
        "Return ONLY valid JSON — no markdown, no explanation, no code fences. "
        "Start your response with [ or { and end with ] or }."
    )
    raw_retry = await call_llm(
        system_prompt, user_prompt + strict_suffix,
        temperature=0.0, timeout=timeout, model=model,
    )

    parsed = _try_parse_json(raw_retry)
    if parsed is not None:
        return parsed

    raise ValueError(
        f"LLM failed to return valid JSON after 2 attempts. "
        f"Last raw response: {raw_retry[:500]}"
    )


def _try_parse_json(text: str) -> dict | list | None:
    """Try to parse JSON from LLM output, handling common wrapping patterns."""
    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    if "```" in text:
        # Find content between first ``` and last ```
        parts = text.split("```")
        for part in parts[1:]:  # skip text before first fence
            # Remove optional language tag (e.g., "json\n")
            content = part.strip()
            if content.startswith("json"):
                content = content[4:].strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                continue

    # Try to find JSON array or object in the text
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start_idx = text.find(start_char)
        end_idx = text.rfind(end_char)
        if start_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(text[start_idx : end_idx + 1])
            except json.JSONDecodeError:
                continue

    return None
