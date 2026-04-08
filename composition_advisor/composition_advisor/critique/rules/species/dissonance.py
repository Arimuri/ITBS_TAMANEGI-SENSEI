"""Species 1 rule: every vertical interval must be consonant.

In first species (1:1) every cantus-firmus / counterpoint pair sounds on a
strong beat with no embellishment, so dissonant intervals are forbidden:
m2, M2, P4, TT, m7, M7. Mod-12 means we also catch their compound forms.
"""

from __future__ import annotations

from typing import Any

from ....model.issue import Issue
from ....model.score import Score
from ....model.slice import Slice
from ._helpers import (
    cf_and_cp,
    harmonic_interval,
    is_dissonant,
    pair_notes_by_position,
)

RULE_ID = "species_dissonance"


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    parts = cf_and_cp(score, params)
    if parts is None:
        return []
    cf, cp = parts
    pairs = pair_notes_by_position(cf, cp)

    INTERVAL_LABELS = {
        1: "m2", 2: "M2", 5: "P4", 6: "TT", 10: "m7", 11: "M7",
    }

    issues: list[Issue] = []
    for cf_n, cp_n in pairs:
        interval = harmonic_interval(cf_n, cp_n)
        if not is_dissonant(interval):
            continue
        label = INTERVAL_LABELS.get(interval % 12, f"{interval % 12}st")
        compound = " (compound)" if interval >= 12 else ""
        issues.append(
            Issue(
                bar=cp_n.bar,
                beat_in_bar=cp_n.beat_in_bar,
                severity="warning",
                rule_id=RULE_ID,
                description=(
                    f"Dissonant vertical {label}{compound} between "
                    f"{cp.name} {cp_n.pitch_name} and {cf.name} {cf_n.pitch_name}. "
                    f"First species requires all intervals to be consonant."
                ),
                affected_notes=[cf_n, cp_n],
                affected_parts=[cf.name, cp.name],
                context={"interval_semitones": interval, "label": label},
            )
        )
    return issues
