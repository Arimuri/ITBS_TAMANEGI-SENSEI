"""Species rule: counterpoint should have a single climax and stay within a tenth.

- climax: the highest pitch in the line should occur exactly once.
- range:  the line should not span more than a 10th (16 semitones) — Fux
  often allows up to a tenth, less is preferred.
- repeated_pitch: in strict first-species, immediate same-pitch repetition
  is forbidden (the line must move).
"""

from __future__ import annotations

from typing import Any

from ....model.issue import Issue
from ....model.score import Score
from ....model.slice import Slice
from ._helpers import cf_and_cp

RULE_ID = "species_climax_range"

MAX_RANGE_SEMITONES = 16  # major 10th


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    parts = cf_and_cp(score, params)
    if parts is None:
        return []
    _cf, cp = parts
    notes = sorted(cp.notes, key=lambda n: n.start_beat)
    if not notes:
        return []

    issues: list[Issue] = []

    pitches = [n.pitch for n in notes]
    span = max(pitches) - min(pitches)
    if span > MAX_RANGE_SEMITONES:
        lo = min(notes, key=lambda n: n.pitch)
        hi = max(notes, key=lambda n: n.pitch)
        issues.append(
            Issue(
                bar=hi.bar,
                beat_in_bar=hi.beat_in_bar,
                severity="info",
                rule_id=RULE_ID,
                description=(
                    f"{cp.name} の音域が {span} 半音 ({lo.pitch_name}..{hi.pitch_name}) "
                    f"あります。対位法では10度(16半音)以内に収めるのが基本です。"
                ),
                affected_notes=[lo, hi],
                affected_parts=[cp.name],
                context={"kind": "range_too_wide", "span_semitones": span},
            )
        )

    top = max(pitches)
    top_count = pitches.count(top)
    if top_count > 1:
        instances = [n for n in notes if n.pitch == top]
        issues.append(
            Issue(
                bar=instances[0].bar,
                beat_in_bar=instances[0].beat_in_bar,
                severity="info",
                rule_id=RULE_ID,
                description=(
                    f"クライマックス音 {instances[0].pitch_name} が {top_count} 回現れています。"
                    f"対位法の旋律は一度きりの最高音を頂点として形作るのが普通です。"
                ),
                affected_notes=instances,
                affected_parts=[cp.name],
                context={"kind": "multiple_climax", "count": top_count},
            )
        )

    for i in range(len(notes) - 1):
        a, b = notes[i], notes[i + 1]
        if a.pitch == b.pitch:
            issues.append(
                Issue(
                    bar=b.bar,
                    beat_in_bar=b.beat_in_bar,
                    severity="info",
                    rule_id=RULE_ID,
                    description=(
                        f"同音連打 {a.pitch_name}→{b.pitch_name}: "
                        f"1種対位法では同音の連続は禁則です。"
                    ),
                    affected_notes=[a, b],
                    affected_parts=[cp.name],
                    context={"kind": "repeated_pitch"},
                )
            )

    return issues
