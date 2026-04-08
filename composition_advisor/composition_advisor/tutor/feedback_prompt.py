"""Counterpoint tutor prompt + Claude wrapper.

Reuses the existing claude_client transport, but swaps the system prompt
for one tailored to species-counterpoint feedback. The user prompt is
generated from the AnalysisResult of running species_runner.
"""

from __future__ import annotations

import logging
import os

import anthropic

from ..llm.claude_client import DEFAULT_MAX_TOKENS, DEFAULT_MODEL
from ..llm.prompt_builder import build_user_prompt
from ..model.issue import AnalysisResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a strict but encouraging counterpoint teacher in the Fux/Jeppesen
tradition. The student is practising species counterpoint and has just
submitted an exercise. Your job is to:

1. Identify each issue and explain it in textbook terms (parallel fifths,
   unprepared dissonance, leap not balanced, etc.).
2. Distinguish between hard prohibitions (parallel perfect intervals,
   dissonance on a strong beat in 1st species, melodic tritone) and softer
   stylistic preferences (unrecovered leap, climax repetition).
3. Suggest concrete, note-name fixes using Studio One pitch names
   (middle C = C3). Where possible give two alternatives so the student
   can choose.
4. Praise good moments — note where the line is shaped well, where contrary
   motion is used effectively, where the climax is well-placed.
5. End with a one-sentence overall verdict and a single concrete next step.

Tone: a kind, focused private teacher. Concise, never preachy. Always use
musical pitch names rather than abstract pitch classes.
"""


def build_tutor_prompt(result: AnalysisResult, species: int = 1) -> str:
    base = build_user_prompt(result)
    return (
        f"# Species counterpoint exercise (Species {species})\n\n"
        + base
        + "\n\n# What I want from you\n"
        "For each issue, write a numbered section with:\n"
        "1. Diagnosis (one short sentence in counterpoint vocabulary)\n"
        "2. Severity: prohibition / preference / minor\n"
        "3. Concrete fix(es) in Studio One pitch names\n"
        "4. (optional) Why the fix sounds better\n\n"
        "After all numbered issues, finish with:\n"
        "- '## What you did well' — 2 short bullets\n"
        "- '## Next step' — one concrete practice goal\n"
    )


def critique_species(
    result: AnalysisResult,
    species: int = 1,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it before requesting tutor feedback."
        )

    prompt = build_tutor_prompt(result, species=species)
    logger.info(
        "Calling Claude tutor (%s) species=%d, prompt length=%d chars",
        model, species, len(prompt),
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in response.content if hasattr(b, "text"))
