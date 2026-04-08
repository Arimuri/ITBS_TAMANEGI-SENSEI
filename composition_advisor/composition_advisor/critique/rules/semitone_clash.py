"""Detect semitone clashes within a single Slice.

A "semitone clash" is two simultaneously sounding notes whose pitch difference,
modulo 12, is exactly 1 semitone (so a minor 2nd, a major 7th, a minor 9th,
etc. all count). Notes from the same Part are skipped — a single melodic line
crossing a chromatic neighbor is not a clash.
"""

from __future__ import annotations

from itertools import combinations

from ...model.issue import Issue
from ...model.score import Score
from ...model.slice import Slice

RULE_ID = "semitone_clash"


def check(score: Score, slices: list[Slice]) -> list[Issue]:
    """Return one Issue per detected clashing pair (per slice)."""
    issues: list[Issue] = []
    for sl in slices:
        for a, b in combinations(sl.notes, 2):
            if a.part == b.part:
                continue
            interval = abs(a.pitch - b.pitch)
            if interval == 0:
                continue
            if interval % 12 == 1 or interval % 12 == 11:
                lo, hi = (a, b) if a.pitch < b.pitch else (b, a)
                desc = (
                    f"Semitone clash: {lo.pitch_name} ({lo.part}) vs "
                    f"{hi.pitch_name} ({hi.part}) — {interval} semitones apart"
                )
                issues.append(
                    Issue(
                        bar=sl.bar,
                        beat_in_bar=sl.beat_in_bar,
                        severity="warning",
                        rule_id=RULE_ID,
                        description=desc,
                        affected_notes=[lo, hi],
                        affected_parts=sorted({lo.part, hi.part}),
                        context={
                            "interval_semitones": interval,
                            "duration_overlap": sl.duration,
                        },
                    )
                )
    return issues
