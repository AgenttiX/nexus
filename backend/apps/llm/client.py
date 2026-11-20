"""Access to language models through the OpenAI-compatible API of a LiteLLM proxy.

LiteLLM gives one API for both local and cloud models, so the rest of Nexus
only ever names a model and never cares where it runs.
"""

from typing import Any

from django.conf import settings
from openai import AsyncOpenAI

TIMEOUT_SECONDS = 600


class LLMNotConfiguredError(RuntimeError):
    """Raised when a language model is needed but the deployment has none configured."""


def default_model() -> str:
    """Return the model to use when a user has not chosen one."""
    if not settings.LLM_DEFAULT_MODEL:
        msg = "No language model is configured. Set LLM_DEFAULT_MODEL or choose a model in the settings."
        raise LLMNotConfiguredError(msg)
    return settings.LLM_DEFAULT_MODEL


def client() -> AsyncOpenAI:
    """Return a client for the configured LiteLLM proxy."""
    if not settings.LITELLM_BASE_URL:
        msg = "No LiteLLM proxy is configured. Set LITELLM_BASE_URL."
        raise LLMNotConfiguredError(msg)
    return AsyncOpenAI(
        base_url=settings.LITELLM_BASE_URL,
        api_key=settings.LITELLM_API_KEY or "none",
        timeout=TIMEOUT_SECONDS,
        max_retries=2,
    )


async def complete(
    llm: AsyncOpenAI,
    model: str,
    system: str,
    user: str,
    json_schema: dict[str, Any] | None = None,
) -> str:
    """Send one system and one user message, and return the model's answer.

    With ``json_schema`` the model is asked to answer with JSON of that shape.
    Not every model honours that, so callers must still validate the answer.
    """
    extra: dict[str, Any] = {}
    if json_schema is not None:
        extra["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "answer", "schema": json_schema, "strict": True},
        }
    response = await llm.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        **extra,
    )
    return response.choices[0].message.content or ""
