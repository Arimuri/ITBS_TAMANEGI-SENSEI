"""Species 4 (suspension) rules.

Fourth species ties the off-beat counterpoint note across the bar so that
the strong beat sounds dissonant against the new cantus note. The
suspension must:

    1. be PREPARED — the tied note arrives as a consonance over the
       previous cantus note.
    2. CLASH on the strong beat over the new cantus note.
    3. RESOLVE downward by step on the next weak beat to a consonance.

We model this by walking each counterpoint note that starts on a weak beat
and is long enough to overlap the next cantus note. For such "potential
suspension" notes we check the three properties above.
"""

from __future__ import annotations

from typing import Any

from ....model.issue import Issue
from ....model.score import Score
from ....model.slice import Slice
from ._helpers import (
    cf_active_at,
    cf_and_cp,
    harmonic_interval,
    is_consonant,
    is_dissonant,
)

PREP_RULE_ID = "species4_unprepared_suspension"
RESOLVE_RULE_ID = "species4_unresolved_suspension"
NO_DISSONANCE_RULE_ID = "species4_missing_dissonance"


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    parts = cf_and_cp(score, params)
    if parts is None:
        return []
    cf, cp = parts

    flat_cp = sorted(cp.notes, key=lambda n: n.start_beat)
    if not flat_cp:
        return []
    cf_starts = sorted({n.start_beat for n in cf.notes})
    if not cf_starts:
        return []

    EPS = 1e-3
    issues: list[Issue] = []

    for i, cp_note in enumerate(flat_cp):
        end = cp_note.start_beat + cp_note.duration
        # Find the cf boundary, if any, that this cp note crosses.
        crossing = next(
            (s for s in cf_starts if cp_note.start_beat + EPS < s < end - EPS),
            None,
        )
        if crossing is None:
            continue

        cf_before = cf_active_at(cf, cp_note.start_beat)
        cf_after = cf_active_at(cf, crossing + EPS)
        if cf_before is None or cf_after is None:
            continue

        # 1. preparation: must be consonant against cf_before
        prep_interval = harmonic_interval(cf_before, cp_note)
        if not is_consonant(prep_interval):
            issues.append(
                Issue(
                    bar=cp_note.bar,
                    beat_in_bar=cp_note.beat_in_bar,
                    severity="warning",
                    rule_id=PREP_RULE_ID,
                    description=(
                        f"Suspension at {cp_note.pitch_name} is not properly prepared: "
                        f"the tie starts on a {prep_interval}-semitone interval, "
                        f"which is not consonant."
                    ),
                    affected_notes=[cf_before, cp_note],
                    affected_parts=[cf.name, cp.name],
                    context={"phase": "preparation"},
                )
            )
            continue

        # 2. clash: should be dissonant against cf_after
        clash_interval = harmonic_interval(cf_after, cp_note)
        if not is_dissonant(clash_interval):
            issues.append(
                Issue(
                    bar=cp_note.bar,
                    beat_in_bar=cp_note.beat_in_bar,
                    severity="info",
                    rule_id=NO_DISSONANCE_RULE_ID,
                    description=(
                        f"Tied note {cp_note.pitch_name} is consonant against the new "
                        f"cantus note ({cf_after.pitch_name}); fourth species shines on "
                        f"a properly prepared and resolved dissonant suspension here."
                    ),
                    affected_notes=[cf_after, cp_note],
                    affected_parts=[cf.name, cp.name],
                    context={"phase": "clash"},
                )
            )
            continue

        # 3. resolve: next cp note should be a step down to a consonance
        next_n = flat_cp[i + 1] if i + 1 < len(flat_cp) else None
        if next_n is None:
            issues.append(
                Issue(
                    bar=cp_note.bar,
                    beat_in_bar=cp_note.beat_in_bar,
                    severity="warning",
                    rule_id=RESOLVE_RULE_ID,
                    description=(
                        f"Suspension {cp_note.pitch_name} has no following note "
                        f"to resolve to."
                    ),
                    affected_notes=[cf_after, cp_note],
                    affected_parts=[cf.name, cp.name],
                    context={"phase": "resolution_missing"},
                )
            )
            continue

        delta = next_n.pitch - cp_note.pitch
        if delta not in (-1, -2):
            issues.append(
                Issue(
                    bar=next_n.bar,
                    beat_in_bar=next_n.beat_in_bar,
                    severity="warning",
                    rule_id=RESOLVE_RULE_ID,
                    description=(
                        f"Suspension {cp_note.pitch_name} should resolve down by step; "
                        f"got {next_n.pitch_name} (interval {delta:+d} semitones)."
                    ),
                    affected_notes=[cf_after, cp_note, next_n],
                    affected_parts=[cf.name, cp.name],
                    context={"phase": "resolution_wrong_motion", "interval_semitones": delta},
                )
            )
            continue

        cf_at_next = cf_active_at(cf, next_n.start_beat)
        if cf_at_next is not None:
            res_interval = harmonic_interval(cf_at_next, next_n)
            if not is_consonant(res_interval):
                issues.append(
                    Issue(
                        bar=next_n.bar,
                        beat_in_bar=next_n.beat_in_bar,
                        severity="warning",
                        rule_id=RESOLVE_RULE_ID,
                        description=(
                            f"Suspension resolves to {next_n.pitch_name}, but that note "
                            f"is dissonant ({res_interval} semitones) against the cantus."
                        ),
                        affected_notes=[cf_at_next, next_n],
                        affected_parts=[cf.name, cp.name],
                        context={"phase": "resolution_to_dissonance"},
                    )
                )

    return issues
