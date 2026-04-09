"""Detect (or fail to detect) imitation between two voices.

Used by Bach two-part invention style lessons. The rule looks for short
melodic motifs (3 to 6 notes) introduced in one voice and then echoed in
the other voice within the next several beats. We compare *interval
sequences* (signed semitone differences between consecutive notes), not
absolute pitches, so a subject in C-major can be imitated up a 5th and
still match.

Two issues are emitted:
- imitation_detected (severity info, "good job")  — when at least one
  motif of length >= MIN_MOTIF is followed by an imitation in the other
  voice.
- imitation_missing (severity info, "consider")    — when no imitation is
  found at all in the whole piece. (We do not flag every motif that
  failed to imitate; that would be noisy.)
"""

from __future__ import annotations

from typing import Any

from ...model.issue import Issue
from ...model.score import Score
from ...model.slice import Slice

RULE_ID = "imitation_check"
MIN_MOTIF = 3
MAX_MOTIF = 6
MAX_LAG_BEATS = 16.0


def _interval_seq(notes: list) -> list[int]:
    return [notes[i + 1].pitch - notes[i].pitch for i in range(len(notes) - 1)]


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    if len(score.parts) < 2:
        return []
    parts = score.parts[:2]
    a_notes = sorted(parts[0].notes, key=lambda n: n.start_beat)
    b_notes = sorted(parts[1].notes, key=lambda n: n.start_beat)
    if len(a_notes) < MIN_MOTIF or len(b_notes) < MIN_MOTIF:
        return []

    issues: list[Issue] = []
    found_any = False

    for source_part_idx, (src, dst) in enumerate([(a_notes, b_notes), (b_notes, a_notes)]):
        for length in range(MAX_MOTIF, MIN_MOTIF - 1, -1):
            for i in range(len(src) - length + 1):
                motif = src[i : i + length]
                motif_iv = _interval_seq(motif)
                motif_start = motif[0].start_beat

                # search dst for the same interval sequence later than motif_start
                for j in range(len(dst) - length + 1):
                    cand = dst[j : j + length]
                    if cand[0].start_beat <= motif_start:
                        continue
                    if cand[0].start_beat - motif_start > MAX_LAG_BEATS:
                        continue
                    if _interval_seq(cand) == motif_iv:
                        found_any = True
                        src_name = parts[source_part_idx].name
                        dst_name = parts[1 - source_part_idx].name
                        lag = cand[0].start_beat - motif_start
                        issues.append(
                            Issue(
                                bar=cand[0].bar,
                                beat_in_bar=cand[0].beat_in_bar,
                                severity="info",
                                rule_id=RULE_ID,
                                description=(
                                    f"{src_name}が提示した{length}音の主題を、"
                                    f"{dst_name}が{lag:.1f}拍後に模倣しています。"
                                    f"({motif[0].pitch_name}…{motif[-1].pitch_name} → "
                                    f"{cand[0].pitch_name}…{cand[-1].pitch_name})"
                                ),
                                affected_notes=list(motif) + list(cand),
                                affected_parts=[src_name, dst_name],
                                context={"length": length, "lag_beats": lag, "kind": "imitation_detected"},
                            )
                        )
                        # 1個見つかれば長さ length のループは打ち切り
                        break
                else:
                    continue
                break

    if not found_any:
        # 0件: 静かな警告
        issues.append(
            Issue(
                bar=1,
                beat_in_bar=1.0,
                severity="info",
                rule_id=RULE_ID,
                description=(
                    "2声間で模倣 (imitation) が検出されませんでした。"
                    "2声インベンションでは片方の声部が主題を提示し、"
                    "もう片方が遅れて模倣する書法が中心になります。"
                ),
                affected_notes=[],
                affected_parts=[p.name for p in parts],
                context={"kind": "imitation_missing"},
            )
        )

    return issues
