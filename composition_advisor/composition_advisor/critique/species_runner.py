"""Run all Species Counterpoint rules and return Issues.

Right now Species 1 (note-against-note) is the only species fully covered.
Other species fall back to a subset of rules and warn that some checks are
not implemented yet.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ..model.issue import Issue
from ..model.score import Score
from ..model.slice import Slice
from .rules import hidden_motion, parallel_motion, voice_crossing
from .rules.species import climax_range, dissonance, melodic_leap, start_end

logger = logging.getLogger(__name__)

SpeciesRule = Callable[[Score, list[Slice], dict[str, Any] | None], list[Issue]]

# Map species number -> list of (rule_id, callable). Voice-leading rules from
# the regular ruleset are reused so opening species inherits parallel/hidden
# motion checks.
SPECIES_RULES: dict[int, list[tuple[str, Callable]]] = {
    1: [
        ("species_start_end_perfect", start_end.check),
        ("species_dissonance", dissonance.check),
        ("species_melodic_leap", melodic_leap.check),
        ("species_climax_range", climax_range.check),
        ("parallel_motion", parallel_motion.check),
        ("hidden_motion", hidden_motion.check),
        ("voice_crossing", voice_crossing.check),
    ],
}


def run_species(
    score: Score,
    slices: list[Slice],
    species: int = 1,
    params: dict[str, Any] | None = None,
) -> list[Issue]:
    rules = SPECIES_RULES.get(species)
    if rules is None:
        logger.warning("species %s is not implemented yet; falling back to species 1", species)
        rules = SPECIES_RULES[1]

    issues: list[Issue] = []
    for name, rule in rules:
        try:
            sig_params = (params or {}) if name.startswith("species_") else None
            if sig_params is not None:
                new_issues = rule(score, slices, params=sig_params)
            else:
                new_issues = rule(score, slices)
            logger.info("species rule %s -> %d issues", name, len(new_issues))
            issues.extend(new_issues)
        except Exception as e:
            logger.warning("species rule %s failed: %s", name, e)

    issues.sort(key=lambda i: (i.bar, i.beat_in_bar, i.rule_id))
    return issues
