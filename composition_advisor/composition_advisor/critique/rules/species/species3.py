"""Species 3 (4:1) rules.

Each cantus firmus note carries four counterpoint notes (quarter-note
motion against whole-note cantus). Strictness by position:

    beat 1 (downbeat)         -> consonant required
    beat 3 (secondary strong) -> consonant unless used as a neighbor /
                                 cambiata escape; we allow neighbor figures
    beat 2, 4 (weak)          -> dissonant OK as passing or neighbor

Implementation notes:
- We pair cp notes to their containing cf note via group_cp_under_cf.
- A neighbor figure is a-b-a where b is a step away.
- A passing tone is a-b-c where a..b..c step in one direction.
"""

from __future__ import annotations

from typing import Any

from ....model.issue import Issue
from ....model.score import Score
from ....model.slice import Slice
from ._helpers import (
    cf_and_cp,
    group_cp_under_cf,
    harmonic_interval,
    is_consonant,
    is_step,
)

DOWNBEAT_RULE_ID = "species3_downbeat_dissonance"
SECOND_STRONG_RULE_ID = "species3_secondary_strong_dissonance"
WEAK_BEAT_RULE_ID = "species3_weak_beat_dissonance"


def _is_passing(prev_n, cur, next_n) -> bool:
    if not (prev_n and next_n):
        return False
    if not (is_step(prev_n, cur) and is_step(cur, next_n)):
        return False
    d1 = cur.pitch - prev_n.pitch
    d2 = next_n.pitch - cur.pitch
    return (d1 > 0) == (d2 > 0)


def _is_neighbor(prev_n, cur, next_n) -> bool:
    if not (prev_n and next_n):
        return False
    return prev_n.pitch == next_n.pitch and is_step(prev_n, cur) and is_step(cur, next_n)


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    parts = cf_and_cp(score, params)
    if parts is None:
        return []
    cf, cp = parts
    flat_cp = sorted(cp.notes, key=lambda n: n.start_beat)
    cp_index = {id(n): i for i, n in enumerate(flat_cp)}
    groups = group_cp_under_cf(cf, cp)

    issues: list[Issue] = []
    for cf_note, cp_notes in groups:
        for idx, cp_note in enumerate(cp_notes):
            interval = harmonic_interval(cf_note, cp_note)
            consonant = is_consonant(interval)
            if consonant:
                continue
            i = cp_index[id(cp_note)]
            prev_n = flat_cp[i - 1] if i > 0 else None
            next_n = flat_cp[i + 1] if i + 1 < len(flat_cp) else None

            position = idx  # 0..3 within the cf bar
            if position == 0:
                rule_id = DOWNBEAT_RULE_ID
                desc_pre = "Downbeat (beat 1) dissonance"
            elif position == 2:
                rule_id = SECOND_STRONG_RULE_ID
                desc_pre = "Secondary strong (beat 3) dissonance"
            else:
                rule_id = WEAK_BEAT_RULE_ID
                desc_pre = f"Weak beat (beat {position + 1}) dissonance"

            # Always allow well-formed passing or neighbor.
            if _is_passing(prev_n, cp_note, next_n) or _is_neighbor(prev_n, cp_note, next_n):
                if position in (1, 3):
                    continue
                # On strong beats we still flag, but soften the message.

            issues.append(
                Issue(
                    bar=cp_note.bar,
                    beat_in_bar=cp_note.beat_in_bar,
                    severity="warning" if position in (0,) else "info",
                    rule_id=rule_id,
                    description=(
                        f"{desc_pre}: {cp.name} {cp_note.pitch_name} vs "
                        f"{cf.name} {cf_note.pitch_name} ({interval} semitones). "
                        f"Third species permits dissonance only as a stepwise "
                        f"passing or neighbor figure on weak beats."
                    ),
                    affected_notes=[cf_note, cp_note],
                    affected_parts=[cf.name, cp.name],
                    context={"interval_semitones": interval, "position": position + 1},
                )
            )

    return issues
