"""Detect hidden (direct) fifths and octaves between adjacent parts.

A "hidden" or "direct" fifth/octave occurs when both voices move in the same
direction and arrive at a perfect fifth or octave. Classical counterpoint
treats this as a soft prohibition (especially when the upper voice does not
arrive by step). This rule fires `info` severity by default — a counterpoint
config can promote it to `warning`.

Implementation uses music21's VoiceLeadingQuartet.hiddenFifth/hiddenOctave
which already encode the textbook definition.
"""

from __future__ import annotations

import music21 as m21

from ...model.issue import Issue
from ...model.score import Score
from ...model.slice import Slice

RULE_ID = "hidden_motion"


def _highest_in_part(sl: Slice, part: str):
    notes = [n for n in sl.notes if n.part == part]
    return max(notes, key=lambda n: n.pitch) if notes else None


def check(score: Score, slices: list[Slice]) -> list[Issue]:
    issues: list[Issue] = []
    part_names = score.metadata.part_names

    for i in range(len(slices) - 1):
        s1, s2 = slices[i], slices[i + 1]
        for j in range(len(part_names)):
            for k in range(j + 1, len(part_names)):
                p1, p2 = part_names[j], part_names[k]
                n1a = _highest_in_part(s1, p1)
                n2a = _highest_in_part(s2, p1)
                n1b = _highest_in_part(s1, p2)
                n2b = _highest_in_part(s2, p2)
                if not all((n1a, n2a, n1b, n2b)):
                    continue
                if n1a.pitch == n2a.pitch and n1b.pitch == n2b.pitch:
                    continue
                try:
                    vlq = m21.voiceLeading.VoiceLeadingQuartet(
                        v1n1=m21.note.Note(n1a.pitch),
                        v1n2=m21.note.Note(n2a.pitch),
                        v2n1=m21.note.Note(n1b.pitch),
                        v2n2=m21.note.Note(n2b.pitch),
                    )
                    kind = None
                    if vlq.hiddenFifth():
                        kind = "fifth"
                    elif vlq.hiddenOctave():
                        kind = "octave"
                    if kind is None:
                        continue
                    desc = (
                        f"Hidden (direct) {kind}: {p1} {n1a.pitch_name}->{n2a.pitch_name} "
                        f"vs {p2} {n1b.pitch_name}->{n2b.pitch_name} "
                        f"(both voices move in the same direction into a perfect {kind})"
                    )
                    issues.append(
                        Issue(
                            bar=s2.bar,
                            beat_in_bar=s2.beat_in_bar,
                            severity="info",
                            rule_id=RULE_ID,
                            description=desc,
                            affected_notes=[n1a, n2a, n1b, n2b],
                            affected_parts=[p1, p2],
                            context={"kind": kind},
                        )
                    )
                except Exception:
                    continue
    return issues
