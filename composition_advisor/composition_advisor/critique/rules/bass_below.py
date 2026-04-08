"""Detect notes from non-bass parts that go below the bass part's lowest note.

Heuristic: any Part whose name contains "bass" (case-insensitive) is treated
as the bass. If no such part exists, the rule emits no issues.
"""

from __future__ import annotations

from ...model.issue import Issue
from ...model.score import Score
from ...model.slice import Slice

RULE_ID = "bass_below"


def _bass_part_names(score: Score) -> set[str]:
    return {p.name for p in score.parts if "bass" in p.name.lower()}


def check(score: Score, slices: list[Slice]) -> list[Issue]:
    bass_names = _bass_part_names(score)
    if not bass_names:
        return []

    issues: list[Issue] = []
    for sl in slices:
        bass_notes = [n for n in sl.notes if n.part in bass_names]
        other_notes = [n for n in sl.notes if n.part not in bass_names]
        if not bass_notes or not other_notes:
            continue
        bass_low = min(bass_notes, key=lambda n: n.pitch)
        offenders = [n for n in other_notes if n.pitch < bass_low.pitch]
        for off in offenders:
            issues.append(
                Issue(
                    bar=sl.bar,
                    beat_in_bar=sl.beat_in_bar,
                    severity="warning",
                    rule_id=RULE_ID,
                    description=(
                        f"{off.part} note {off.pitch_name} is below the bass "
                        f"({bass_low.part} {bass_low.pitch_name})"
                    ),
                    affected_notes=[off, bass_low],
                    affected_parts=sorted({off.part, bass_low.part}),
                )
            )
    return issues
