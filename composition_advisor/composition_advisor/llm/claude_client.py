"""Thin wrapper around the anthropic SDK for composition critique."""

from __future__ import annotations

import logging
import os

import anthropic

from ..model.issue import AnalysisResult
from .prompt_builder import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-4-6"
DEFAULT_MAX_TOKENS = 4000


def critique(
    result: AnalysisResult,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Send an AnalysisResult to Claude and return the critique text.

    Reads ANTHROPIC_API_KEY from the environment (the SDK does this for us).
    Raises if the env var is missing.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it before using --llm."
        )

    user_prompt = build_user_prompt(result)
    logger.info("Calling Claude (%s), prompt length=%d chars", model, len(user_prompt))

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # Concatenate every text block — Claude usually returns one but the API
    # supports more.
    parts = [block.text for block in response.content if hasattr(block, "text")]
    return "\n".join(parts)
