"""Species 1 rule: opening and closing intervals must be perfect consonances.

Fux: the first and last vertical interval must be a perfect consonance
(unison, fifth, or octave). Modern teachers usually accept any of these for
the opening, but the closing typically lands on a unison or octave.
"""

from __future__ import annotations

from typing import Any

from ....model.issue import Issue
from ....model.score import Score
from ....model.slice import Slice
from ._helpers import cf_and_cp, harmonic_interval, is_perfect, pair_notes_by_position

RULE_ID = "species_start_end_perfect"


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    parts = cf_and_cp(score, params)
    if parts is None:
        return []
    cf, cp = parts
    pairs = pair_notes_by_position(cf, cp)
    if len(pairs) < 2:
        return []

    issues: list[Issue] = []
    for label, idx in (("opening", 0), ("closing", -1)):
        cf_n, cp_n = pairs[idx]
        interval = harmonic_interval(cf_n, cp_n)
        if not is_perfect(interval):
            issues.append(
                Issue(
                    bar=cp_n.bar,
                    beat_in_bar=cp_n.beat_in_bar,
                    severity="warning",
                    rule_id=RULE_ID,
                    description=(
                        f"{label.capitalize()} interval is {interval} semitones; "
                        f"counterpoint should open/close on a perfect consonance "
                        f"(unison, P5, or P8)."
                    ),
                    affected_notes=[cf_n, cp_n],
                    affected_parts=[cf.name, cp.name],
                    context={"position": label, "interval_semitones": interval},
                )
            )
    return issues
