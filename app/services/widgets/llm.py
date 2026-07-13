"""
LLM factory for AIMS v3 widgets.

Builds a ChatOpenAI configured for either OpenAI or any OpenAI-compatible
endpoint (OpenRouter, Together, Groq, local via LitLLM, etc.) purely from
environment variables, so the generator and judge never hardcode a provider.

Resolution order:
1. OPENROUTER_API_KEY  -> base_url = OPENROUTER_BASE_URL (default
   https://openrouter.ai/api/v1), model = OPENROUTER_MODEL (default
   'openai/gpt-4o-mini').
2. OPENAI_API_KEY      -> base_url = OPENAI_BASE_URL (default None = OpenAI
   official), model = OPENAI_MODEL (default 'gpt-4o-mini').

If neither key is set, raises LLMConfigError. Callers that want to run
without an LLM (e.g. tests) should catch this and fall back to StubGenerator.
"""
from __future__ import annotations

import os
from typing import Optional

from langchain_openai import ChatOpenAI


class LLMConfigError(RuntimeError):
    """Raised when no LLM provider is configured."""


DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def build_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Build a ChatOpenAI from environment variables.

    Raises LLMConfigError if neither OPENROUTER_API_KEY nor OPENAI_API_KEY is
    set. Caller is responsible for falling back to a stub on tests.
    """
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if openrouter_key:
        return ChatOpenAI(
            model=os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
            temperature=temperature,
            api_key=openrouter_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL),
        )

    if openai_key:
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
            temperature=temperature,
            api_key=openai_key,
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )

    raise LLMConfigError(
        "No LLM provider configured. Set OPENROUTER_API_KEY or OPENAI_API_KEY "
        "in your environment."
    )


def llm_available() -> bool:
    """True if at least one provider key is set. Cheap, no construction."""
    return bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"))


def provider_name() -> Optional[str]:
    """Returns 'openrouter', 'openai', or None for diagnostics/logging."""
    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return None
