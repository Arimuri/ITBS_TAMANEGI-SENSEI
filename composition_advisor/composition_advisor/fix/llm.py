"""LLM-based fix proposal generator.

Asks Claude to return a strict JSON list of edits, then maps each entry back
onto a Note object so the applier can use it. We deliberately limit Claude
to the issues that ruleband cannot resolve well (semitone_clash,
parallel_motion, chord_tone_check).

The prompt asks Claude to return ONLY valid JSON of the shape:

[
  {
    "issue_index": 0,
    "part": "epiano",
    "bar": 4,
    "beat_in_bar": 3.28,
    "old_pitch_name": "F#2",
    "action": "transpose",            // or "delete"
    "new_pitch_name": "F2",           // for transpose
    "rationale": "..."
  },
  ...
]

The matching back to Note is fuzzy on (part, bar, |beat-target|<EPS, pitch).
"""

from __future__ import annotations

import json
import logging
import os
import re

import anthropic

from ..llm.claude_client import DEFAULT_MAX_TOKENS, DEFAULT_MODEL
from ..llm.prompt_builder import build_user_prompt
from ..model.fix import Fix
from ..model.issue import AnalysisResult
from ..model.score import NOTE_NAMES, Note, Score, midi_to_studio_one

logger = logging.getLogger(__name__)

LLM_FIXABLE_RULES = {"semitone_clash", "parallel_motion", "chord_tone_check"}

SYSTEM_PROMPT = """\
You are a jazz/fusion-aware composition coach. The user has detected
specific harmonic / voice-leading issues in a MIDI score and wants concrete
fixes expressed as note edits.

For each issue you decide to fix, return ONE JSON object describing the
edit. Use Studio One pitch names (middle C = C3). Do NOT include prose,
markdown, or commentary — output a single JSON array and nothing else.

Each fix object MUST have:
- issue_index   (int)   — index into the issues list, starting at 0
- part          (str)   — exact part name from the score
- bar           (int)
- beat_in_bar   (float)
- old_pitch_name (str)  — Studio One name of the note to edit
- action        ("transpose" | "delete")
- new_pitch_name (str)  — required for transpose, omit for delete
- rationale     (str)   — short reason

You may skip an issue if you think it is intentional. In that case omit it
from the output. Output [] if no fixes are warranted.
"""


def _user_prompt(result: AnalysisResult, target_indices: list[int]) -> str:
    base = build_user_prompt(result)
    target_lines = "\n".join(
        f"  index {i}: {result.issues[i].rule_id} bar{result.issues[i].bar} "
        f"beat{result.issues[i].beat_in_bar:.2f} — {result.issues[i].description}"
        for i in target_indices
    )
    return (
        base
        + "\n\n# Fix targets\n"
        + "Only consider these issue indices for fixes (skip everything else):\n"
        + target_lines
        + "\n\nReturn JSON array only."
    )


def _parse_pitch_name(name: str) -> int | None:
    """'F#2' -> MIDI 30 (Studio One: middle C = C3 = 60)."""
    name = name.strip().replace("♯", "#").replace("♭", "b")
    m = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d+)", name)
    if not m:
        return None
    letter = m.group(1).upper()
    accidental = m.group(2)
    octave = int(m.group(3))
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[letter]
    if accidental == "#":
        base += 1
    elif accidental == "b":
        base -= 1
    # Studio One: C3 == MIDI 60 → midi = base + (octave + 2) * 12
    return base + (octave + 2) * 12


def _find_note(score: Score, part: str, bar: int, beat: float, midi: int) -> Note | None:
    """Locate the matching Note (fuzzy on beat) in the score."""
    EPS = 0.05
    for p in score.parts:
        if p.name != part:
            continue
        for n in p.notes:
            if n.bar == bar and abs(n.beat_in_bar - beat) < EPS and n.pitch == midi:
                return n
    return None


def _extract_json(text: str) -> list[dict] | None:
    text = text.strip()
    # Strip ``` fences if Claude added them despite the prompt.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("LLM fix JSON parse failed: %s", e)
        return None
    if not isinstance(data, list):
        logger.warning("LLM fix JSON root is not a list: %s", type(data))
        return None
    return data


def propose(
    score: Score,
    result: AnalysisResult,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[Fix]:
    """Ask Claude for fixes to the LLM-fixable issues, return parsed Fix list."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set; cannot run LLM fix.")

    target_indices = [
        i for i, iss in enumerate(result.issues) if iss.rule_id in LLM_FIXABLE_RULES
    ]
    if not target_indices:
        return []

    prompt = _user_prompt(result, target_indices)
    logger.info("LLM fix: %d targets, prompt %d chars", len(target_indices), len(prompt))

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "\n".join(b.text for b in response.content if hasattr(b, "text"))
    raw_fixes = _extract_json(text)
    if not raw_fixes:
        return []

    fixes: list[Fix] = []
    for entry in raw_fixes:
        try:
            idx = int(entry["issue_index"])
            part = str(entry["part"])
            bar = int(entry["bar"])
            beat = float(entry["beat_in_bar"])
            old_name = str(entry["old_pitch_name"])
            action = str(entry["action"])
        except (KeyError, ValueError, TypeError):
            logger.warning("LLM fix entry malformed, skipping: %s", entry)
            continue

        old_midi = _parse_pitch_name(old_name)
        if old_midi is None:
            logger.warning("LLM fix: cannot parse pitch %r", old_name)
            continue
        target = _find_note(score, part, bar, beat, old_midi)
        if target is None:
            logger.warning(
                "LLM fix: cannot locate note part=%s bar=%s beat=%s pitch=%s",
                part, bar, beat, old_name,
            )
            continue

        fix_kwargs = dict(
            rule_id=result.issues[idx].rule_id if 0 <= idx < len(result.issues) else "unknown",
            issue_index=idx,
            target=target,
            rationale=str(entry.get("rationale", "")),
            source="llm",
        )

        if action == "transpose":
            new_name = entry.get("new_pitch_name")
            if not new_name:
                continue
            new_midi = _parse_pitch_name(new_name)
            if new_midi is None:
                continue
            fix_kwargs.update(
                action="transpose",
                new_pitch=new_midi,
                new_pitch_name=midi_to_studio_one(new_midi),
            )
        elif action == "delete":
            fix_kwargs.update(action="delete")
        else:
            logger.warning("LLM fix: unknown action %r", action)
            continue

        fixes.append(Fix(**fix_kwargs))

    return fixes
