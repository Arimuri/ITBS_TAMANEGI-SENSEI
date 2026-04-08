"""Detect voice crossing between adjacent parts across consecutive slices.

Two voices "cross" when, between time t1 and t2, the lower-voice note rises
above the upper-voice note (or vice versa). We compare every pair of parts
between consecutive slices and use music21's VoiceLeadingQuartet to make the
judgement consistent with the rest of the codebase.
"""

from __future__ import annotations

import music21 as m21

from ...model.issue import Issue
from ...model.score import Score
from ...model.slice import Slice

RULE_ID = "voice_crossing"


def _highest_in_part(sl: Slice, part: str):
    notes = [n for n in sl.notes if n.part == part]
    return max(notes, key=lambda n: n.pitch) if notes else None


def check(score: Score, slices: list[Slice]) -> list[Issue]:
    issues: list[Issue] = []
    part_names = score.metadata.part_names

    for i in range(len(slices) - 1):
        s1, s2 = slices[i], slices[i + 1]
        for p_upper, p_lower in [(a, b) for a in part_names for b in part_names if a != b]:
            n1u = _highest_in_part(s1, p_upper)
            n1l = _highest_in_part(s1, p_lower)
            n2u = _highest_in_part(s2, p_upper)
            n2l = _highest_in_part(s2, p_lower)
            if not all((n1u, n1l, n2u, n2l)):
                continue
            if not (n1u.pitch > n1l.pitch):
                continue  # Only check from a state where p_upper actually started above
            try:
                vlq = m21.voiceLeading.VoiceLeadingQuartet(
                    v1n1=m21.note.Note(n1u.pitch),
                    v1n2=m21.note.Note(n2u.pitch),
                    v2n1=m21.note.Note(n1l.pitch),
                    v2n2=m21.note.Note(n2l.pitch),
                )
                if vlq.voiceCrossing():
                    desc = (
                        f"声部交叉: {p_upper}({n1u.pitch_name}→{n2u.pitch_name})が"
                        f"{p_lower}({n1l.pitch_name}→{n2l.pitch_name})と交差しています。"
                    )
                    issues.append(
                        Issue(
                            bar=s2.bar,
                            beat_in_bar=s2.beat_in_bar,
                            severity="warning",
                            rule_id=RULE_ID,
                            description=desc,
                            affected_notes=[n1u, n2u, n1l, n2l],
                            affected_parts=[p_upper, p_lower],
                        )
                    )
            except Exception:
                continue
    return issues
