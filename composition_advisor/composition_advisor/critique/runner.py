"""Run all critique rules and return a flat list of Issues."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable

from ..model.issue import Issue
from ..model.score import Score
from ..model.slice import Slice
from .config import DEFAULT_CONFIG, CritiqueConfig
from .rules import (
    bass_below,
    chord_tone_check,
    parallel_motion,
    range_check,
    semitone_clash,
    voice_crossing,
)

logger = logging.getLogger(__name__)

# Rules may optionally accept a `params` keyword. The runner introspects the
# signature so existing rules without params still work.
Rule = Callable[..., list[Issue]]

ALL_RULES: list[tuple[str, Rule]] = [
    ("semitone_clash", semitone_clash.check),
    ("voice_crossing", voice_crossing.check),
    ("bass_below", bass_below.check),
    ("parallel_motion", parallel_motion.check),
    ("range_check", range_check.check),
    ("chord_tone_check", chord_tone_check.check),
]


def run_all(
    score: Score,
    slices: list[Slice],
    config: CritiqueConfig | None = None,
) -> list[Issue]:
    """Execute every enabled rule and return the concatenated issues.

    The config controls per-rule enabled/severity. Disabled rules are skipped
    entirely; severity overrides are applied to every Issue the rule emits.
    """
    cfg = config or DEFAULT_CONFIG
    issues: list[Issue] = []

    for name, rule in ALL_RULES:
        rule_cfg = cfg.for_rule(name)
        if not rule_cfg.enabled:
            logger.info("rule %s -> skipped (disabled by config)", name)
            continue
        try:
            new_issues = _call_rule(rule, score, slices, rule_cfg.params)
            if rule_cfg.severity:
                for iss in new_issues:
                    iss.severity = rule_cfg.severity  # type: ignore[assignment]
            logger.info("rule %s -> %d issues", name, len(new_issues))
            issues.extend(new_issues)
        except Exception as e:
            logger.warning("rule %s failed: %s", name, e)

    issues.sort(key=lambda i: (i.bar, i.beat_in_bar, i.rule_id))
    return issues


def _call_rule(
    rule: Rule, score: Score, slices: list[Slice], params: dict[str, Any]
) -> list[Issue]:
    """Call a rule with `params` if its signature accepts it, else without."""
    sig = inspect.signature(rule)
    if "params" in sig.parameters:
        return rule(score, slices, params=params)
    return rule(score, slices)
