"""
Model client factory for AutoGen OpenAI-compatible LLM.

Loads configuration from environment variables only.
Never hardcodes API keys or credentials.
"""
from __future__ import annotations

import logging
import os

from autogen_ext.models.openai import OpenAIChatCompletionClient

logger = logging.getLogger(__name__)


def get_model_client() -> OpenAIChatCompletionClient:
    """
    Create and return an OpenAIChatCompletionClient from environment variables.

    Required env vars:
        OPENAI_API_KEY  — API key for the LLM endpoint
        OPENAI_MODEL    — Model / deployment name

    Optional env vars:
        OPENAI_BASE_URL — Base URL for OpenAI-compatible endpoints.
                         Leave blank or omit to use the default OpenAI endpoint.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None

    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable is not set. "
            "Copy .env.example to .env and provide your API key."
        )
    if not model:
        raise EnvironmentError("OPENAI_MODEL environment variable is not set.")

    # openai v2 reads OPENAI_BASE_URL directly from os.environ.
    # An empty string causes it to build a URL with no protocol and fail.
    # Remove the env var entirely when blank so openai uses its default endpoint.
    if not base_url and "OPENAI_BASE_URL" in os.environ:
        del os.environ["OPENAI_BASE_URL"]

    kwargs: dict = {
        "model": model,
        "api_key": api_key,
    }
    if base_url:
        kwargs["base_url"] = base_url
        logger.info("[MODEL_CLIENT] Using custom base URL: %s", base_url)
    else:
        logger.info("[MODEL_CLIENT] Using OpenAI default endpoint")

    logger.info("[MODEL_CLIENT] Model: %s", model)
    return OpenAIChatCompletionClient(**kwargs)
