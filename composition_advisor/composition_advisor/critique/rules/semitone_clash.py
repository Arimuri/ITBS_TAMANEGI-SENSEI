"""Detect semitone clashes within a single Slice.

A "semitone clash" is two simultaneously sounding notes whose pitch difference,
modulo 12, is exactly 1 semitone (so a minor 2nd, a major 7th, a minor 9th,
etc. all count). Notes from the same Part are skipped — a single melodic line
crossing a chromatic neighbor is not a clash.

Params (from RuleConfig.params):
    ignore_durations_below: float (beats, default 0.0)
        Skip slices whose overlap window is shorter than this — useful to
        absorb MIDI quantize jitter where two notes graze each other for a
        few ticks.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from ...model.issue import Issue
from ...model.score import Score
from ...model.slice import Slice

RULE_ID = "semitone_clash"


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    """Return one Issue per detected clashing pair (per slice)."""
    params = params or {}
    min_duration = float(params.get("ignore_durations_below", 0.0))

    issues: list[Issue] = []
    for sl in slices:
        if sl.duration < min_duration:
            continue
        for a, b in combinations(sl.notes, 2):
            if a.part == b.part:
                continue
            interval = abs(a.pitch - b.pitch)
            if interval == 0:
                continue
            if interval % 12 == 1 or interval % 12 == 11:
                lo, hi = (a, b) if a.pitch < b.pitch else (b, a)
                desc = (
                    f"半音衝突: {lo.pitch_name}({lo.part})と"
                    f"{hi.pitch_name}({hi.part})が{interval}半音でぶつかっています。"
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
