"""Run a Lesson against a Score and return Issues + LLM critique.

Resolves a lesson's `rules` list to actual callables across the regular
ruleset and the species-specific ruleset, applies severity overrides,
and forwards lesson-specific params (cantus_firmus_part / counterpoint_part)
into the rule signature when supported.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable

from ..critique.rules import (
    bass_below,
    chord_tone_check,
    hidden_motion,
    imitation_check,
    multi_voice_voicing,
    parallel_motion,
    range_check,
    semitone_clash,
    voice_crossing,
)
from ..critique.rules.species import (
    climax_range,
    dissonance,
    melodic_leap,
    species2,
    species3,
    species4,
    species5,
    start_end,
)
from ..model.issue import Issue
from ..model.score import Score
from ..model.slice import Slice
from .tracks import LessonDef

logger = logging.getLogger(__name__)


# Map every supported rule_id used in lesson yaml -> callable.
RULE_TABLE: dict[str, Callable] = {
    # 一般ルール
    "semitone_clash": semitone_clash.check,
    "voice_crossing": voice_crossing.check,
    "bass_below": bass_below.check,
    "parallel_motion": parallel_motion.check,
    "hidden_motion": hidden_motion.check,
    "range_check": range_check.check,
    "chord_tone_check": chord_tone_check.check,
    # Species 系
    "species_start_end_perfect": start_end.check,
    "species_dissonance": dissonance.check,
    "species_melodic_leap": melodic_leap.check,
    "species_climax_range": climax_range.check,
    "species2_dissonance": species2.check,
    "species3_dissonance": species3.check,
    "species4_suspension": species4.check,
    "species5_florid": species5.check,
    # 模倣・3声・4声
    "imitation_check": imitation_check.check,
    "three_voice_voicing": multi_voice_voicing.three_voice_voicing,
    "three_voice_independence": multi_voice_voicing.three_voice_independence,
    "four_voice_voicing": multi_voice_voicing.four_voice_voicing,
    "four_voice_doubling": multi_voice_voicing.four_voice_doubling,
}


def run_lesson(
    lesson: LessonDef,
    score: Score,
    slices: list[Slice],
    params: dict[str, Any] | None = None,
) -> list[Issue]:
    """Execute every rule the lesson references and return concatenated issues.

    `params` is forwarded to rules whose signature accepts a `params`
    keyword (typically the species rules: cantus_firmus_part /
    counterpoint_part).
    """
    issues: list[Issue] = []
    extra_params = params or {}

    for rule_id in lesson.rules:
        rule = RULE_TABLE.get(rule_id)
        if rule is None:
            logger.warning("lesson %s references unknown rule_id %s", lesson.id, rule_id)
            continue
        try:
            sig = inspect.signature(rule)
            if "params" in sig.parameters:
                new_issues = rule(score, slices, params=extra_params)
            else:
                new_issues = rule(score, slices)
        except Exception as e:
            logger.warning("rule %s failed: %s", rule_id, e)
            continue

        # severity override(YAML で rule_id 単位 or rule の Issue.rule_id 単位で指定可)
        for iss in new_issues:
            override = (
                lesson.rule_severity_overrides.get(iss.rule_id)
                or lesson.rule_severity_overrides.get(rule_id)
            )
            if override:
                iss.severity = override  # type: ignore[assignment]

        logger.info("lesson %s rule %s -> %d issues", lesson.id, rule_id, len(new_issues))
        issues.extend(new_issues)

    issues.sort(key=lambda i: (i.bar, i.beat_in_bar, i.rule_id))
    return issues


def build_lesson_system_prompt(lesson: LessonDef) -> str:
    """Compose a Claude system prompt from the lesson's teacher persona."""
    persona = lesson.teacher_persona.strip() or (
        "あなたは古典対位法を教える親切な個人教師です。"
    )
    return persona + "\n\n**必ず日本語で返答してください。**"


def build_lesson_user_prompt(lesson: LessonDef, base_prompt: str) -> str:
    """Add the lesson's output instructions on top of the standard analysis prompt."""
    instructions = lesson.output_instructions.strip()
    extra = ""
    if instructions:
        extra = f"\n\n# レッスン固有の指示\n{instructions}\n"
    return f"# レッスン: {lesson.title}\n{lesson.summary}\n\n" + base_prompt + extra
