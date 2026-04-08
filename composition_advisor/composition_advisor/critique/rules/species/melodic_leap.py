"""Species rule: melodic leaps in the counterpoint should be controlled.

Restrictions checked here:
- No melodic interval larger than a perfect octave (12 semitones).
- Two consecutive leaps in the same direction are flagged as suspicious.
- A leap larger than a fourth should ideally be followed by stepwise motion
  in the opposite direction.
- The melodic interval of a tritone (6 semitones) is forbidden.
- Augmented / diminished intervals are flagged as a tritone-like motion via
  semitone count (chromatic semitone == 1 semitone, so we focus on TT).
"""

from __future__ import annotations

from typing import Any

from ....model.issue import Issue
from ....model.score import Score
from ....model.slice import Slice
from ._helpers import cf_and_cp, melodic_interval

RULE_ID = "species_melodic_leap"

LEAP_THRESHOLD = 5         # 5 semitones = perfect 4th boundary
LARGE_LEAP_THRESHOLD = 12  # > octave


def _classify(interval: int) -> str:
    a = abs(interval)
    if a > LARGE_LEAP_THRESHOLD:
        return "too_large"
    if a == 6:
        return "tritone"
    return "ok"


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    parts = cf_and_cp(score, params)
    if parts is None:
        return []
    _cf, cp = parts
    notes = sorted(cp.notes, key=lambda n: n.start_beat)
    if len(notes) < 2:
        return []

    issues: list[Issue] = []
    intervals = [
        (i, melodic_interval(notes[i], notes[i + 1])) for i in range(len(notes) - 1)
    ]

    for idx, mi in intervals:
        kind = _classify(mi)
        a = notes[idx]
        b = notes[idx + 1]
        if kind == "too_large":
            issues.append(
                Issue(
                    bar=b.bar,
                    beat_in_bar=b.beat_in_bar,
                    severity="warning",
                    rule_id=RULE_ID,
                    description=(
                        f"旋律的跳躍 {abs(mi)} 半音 "
                        f"({a.pitch_name}→{b.pitch_name}) はオクターブを超えています。"
                    ),
                    affected_notes=[a, b],
                    affected_parts=[cp.name],
                    context={"interval_semitones": mi, "kind": "too_large"},
                )
            )
        elif kind == "tritone":
            issues.append(
                Issue(
                    bar=b.bar,
                    beat_in_bar=b.beat_in_bar,
                    severity="warning",
                    rule_id=RULE_ID,
                    description=(
                        f"旋律的三全音 {a.pitch_name}→{b.pitch_name}: "
                        f"対位法では増4度・減5度の進行は避けます。"
                    ),
                    affected_notes=[a, b],
                    affected_parts=[cp.name],
                    context={"interval_semitones": mi, "kind": "tritone"},
                )
            )

    # Two consecutive leaps in the same direction
    for i in range(len(intervals) - 1):
        _, m1 = intervals[i]
        _, m2 = intervals[i + 1]
        if abs(m1) > LEAP_THRESHOLD and abs(m2) > LEAP_THRESHOLD and (m1 > 0) == (m2 > 0):
            a, b, c = notes[i], notes[i + 1], notes[i + 2]
            issues.append(
                Issue(
                    bar=c.bar,
                    beat_in_bar=c.beat_in_bar,
                    severity="info",
                    rule_id=RULE_ID,
                    description=(
                        f"同方向への連続跳躍 "
                        f"({a.pitch_name}→{b.pitch_name}→{c.pitch_name}): "
                        f"対位法では跳躍の後は順次進行で釣り合いを取るのが基本です。"
                    ),
                    affected_notes=[a, b, c],
                    affected_parts=[cp.name],
                    context={"kind": "consecutive_same_direction"},
                )
            )

    # Large leap not resolved by stepwise contrary motion
    for i in range(len(intervals) - 1):
        _, m1 = intervals[i]
        _, m2 = intervals[i + 1]
        if abs(m1) > LEAP_THRESHOLD:
            same_direction = (m1 > 0) == (m2 > 0)
            stepwise_recovery = abs(m2) <= 2
            if same_direction or not stepwise_recovery:
                a, b, c = notes[i], notes[i + 1], notes[i + 2]
                issues.append(
                    Issue(
                        bar=c.bar,
                        beat_in_bar=c.beat_in_bar,
                        severity="info",
                        rule_id=RULE_ID,
                        description=(
                            f"跳躍 {a.pitch_name}→{b.pitch_name} の後は逆方向の順次進行で"
                            f"解決すべきですが、{b.pitch_name}→{c.pitch_name} となっています。"
                        ),
                        affected_notes=[a, b, c],
                        affected_parts=[cp.name],
                        context={"kind": "unrecovered_leap"},
                    )
                )
    return issues
