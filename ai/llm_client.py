"""ai/llm_client.py

The ONLY file that talks to the LLM provider.
Uses the OpenAI Chat Completions API through httpx (no extra package needed).
"""
import logging
from typing import List, Optional

import httpx

from core.config import settings
from core.exceptions import LLMError, TransientError
from utils.retry import RETRY_STATUS_CODES, parse_retry_after, retry_async

logger = logging.getLogger(__name__)
_client: Optional[httpx.AsyncClient] = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=settings.llm_timeout_seconds,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client

async def close_llm_client() -> None:
    """Called once when the app stops."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None

def _models_to_try() -> List[str]:
    models = [settings.llm_model]
    fallback = (settings.llm_fallback_model or "").strip()
    if fallback and fallback != settings.llm_model:
        models.append(fallback)
    return models

async def _call_model(model: str, system_prompt: str, user_prompt: str) -> str:
    """One attempt with ONE model. Raises LLMError on any problem."""
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": settings.llm_max_tokens,
    }
    # Only sent if you set LLM_TEMPERATURE. Some models reject it.
    if settings.llm_temperature is not None:
        payload["temperature"] = settings.llm_temperature

    try:
        response = await _get_client().post(settings.llm_api_url, json=payload, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in RETRY_STATUS_CODES:
            raise TransientError(
                    f"OpenAI API failed with status {status} (model {model}): {exc.response.text[:200]}",
                    status,
                    parse_retry_after(exc.response.headers.get("Retry-After")),
            ) from exc
        logger.error("OpenAI API error (model %s): %s %s", model, status, exc.response.text)
        raise LLMError(f"OpenAI API failed with status {status} (model {model})", status) from exc
    except httpx.RequestError as exc:  # includes timeouts
        raise TransientError(f"Could not reach the OpenAI API (model {model})") from exc

    data = response.json()
    try:
        choice = data["choices"][0]
        text = (choice["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected response format from OpenAI (model {model})") from exc

    if not text:
        raise LLMError(
            f"OpenAI returned empty text (model {model}, finish_reason={choice.get('finish_reason')})"
        )
    return text

async def _call_model_with_retry(model: str, system_prompt: str, user_prompt: str) -> str:
    try:
        return await retry_async(
            lambda: _call_model(model, system_prompt, user_prompt),
            name=f"OpenAI ({model})",
            attempts=int(getattr(settings, "llm_max_attempts", 2)),
            base_delay=float(getattr(settings, "llm_retry_base_delay", 0.5)),
            retry_on=(TransientError,),
        )
    except TransientError as exc:
        raise LLMError(str(exc), exc.status_code) from exc

async def generate_text(system_prompt: str, user_prompt: str) -> str:
    last_error: Optional[LLMError] = None

    for index, model in enumerate(_models_to_try()):
        try:
            text = await _call_model_with_retry(model, system_prompt, user_prompt)
        except LLMError as exc:
            last_error = exc
            if exc.status_code == 401:
                # wrong API key: another model with the same key cannot help
                break
            logger.warning("Model '%s' failed, trying the next model. Reason: %s", model, exc)
            continue

        if index > 0:
            logger.warning("Primary model failed; the text was written by fallback model '%s'", model)
        return text

    raise last_error or LLMError("No LLM model is configured")