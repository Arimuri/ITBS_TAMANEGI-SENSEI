"""Species 2 (2:1) rules.

For every cantus firmus note there are two counterpoint notes:
    downbeat (= same start as cf note)  -> must be consonant
    upbeat   (= half-way through cf)    -> may be dissonant only as a
                                           passing tone (stepwise approach
                                           AND stepwise resolution).

This module emits two issue ids:
    species2_downbeat_dissonance   — strong-beat dissonance is forbidden
    species2_upbeat_dissonance     — weak-beat dissonance that is not a
                                     properly used passing tone
"""

from __future__ import annotations

from typing import Any

from ....model.issue import Issue
from ....model.score import Score
from ....model.slice import Slice
from ._helpers import (
    cf_active_at,
    cf_and_cp,
    group_cp_under_cf,
    harmonic_interval,
    is_consonant,
    is_dissonant,
    is_step,
)

DOWNBEAT_RULE_ID = "species2_downbeat_dissonance"
UPBEAT_RULE_ID = "species2_upbeat_dissonance"


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    parts = cf_and_cp(score, params)
    if parts is None:
        return []
    cf, cp = parts
    groups = group_cp_under_cf(cf, cp)

    # Flatten cp notes for previous/next lookup
    flat_cp = sorted(cp.notes, key=lambda n: n.start_beat)
    cp_index = {id(n): i for i, n in enumerate(flat_cp)}

    issues: list[Issue] = []
    for cf_note, cp_notes in groups:
        if len(cp_notes) < 1:
            continue
        for idx, cp_note in enumerate(cp_notes):
            interval = harmonic_interval(cf_note, cp_note)
            on_downbeat = idx == 0
            if on_downbeat:
                if not is_consonant(interval):
                    issues.append(
                        Issue(
                            bar=cp_note.bar,
                            beat_in_bar=cp_note.beat_in_bar,
                            severity="warning",
                            rule_id=DOWNBEAT_RULE_ID,
                            description=(
                                f"強拍の不協和({interval}半音): "
                                f"{cp.name} {cp_note.pitch_name} と "
                                f"{cf.name} {cf_note.pitch_name}。"
                                f"2種対位法では強拍は協和音である必要があります。"
                            ),
                            affected_notes=[cf_note, cp_note],
                            affected_parts=[cf.name, cp.name],
                            context={"interval_semitones": interval, "position": "downbeat"},
                        )
                    )
                continue

            # upbeat
            if is_consonant(interval):
                continue
            # Dissonant upbeat -> only OK if it is a passing tone:
            # previous cp note is a step away in the SAME direction as the next.
            i = cp_index[id(cp_note)]
            prev_n = flat_cp[i - 1] if i > 0 else None
            next_n = flat_cp[i + 1] if i + 1 < len(flat_cp) else None
            if prev_n and next_n and is_step(prev_n, cp_note) and is_step(cp_note, next_n):
                d1 = cp_note.pitch - prev_n.pitch
                d2 = next_n.pitch - cp_note.pitch
                if (d1 > 0) == (d2 > 0):
                    continue  # genuine passing tone
            issues.append(
                Issue(
                    bar=cp_note.bar,
                    beat_in_bar=cp_note.beat_in_bar,
                    severity="warning",
                    rule_id=UPBEAT_RULE_ID,
                    description=(
                        f"弱拍の不協和: {cp_note.pitch_name} は {cf_note.pitch_name} に対して"
                        f"正しい経過音ではありません(順次進行で接近して同方向に順次進行で抜ける必要があります)。"
                    ),
                    affected_notes=[cf_note, cp_note],
                    affected_parts=[cf.name, cp.name],
                    context={"interval_semitones": interval, "position": "upbeat"},
                )
            )

    return issues
