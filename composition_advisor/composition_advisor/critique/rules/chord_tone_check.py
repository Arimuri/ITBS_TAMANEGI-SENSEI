"""Detect notes that are not chord tones / acceptable tensions for the slice's chord.

Phase 3 implementation: classify each note in a slice against the slice's
detected chord pitch-class set. Notes that are NOT in the chord-tone set are
flagged. Tensions and avoid notes will be added in Phase 5 with genre tuning;
for now everything outside the chord tones is "warning" severity.

Notes from the bass part are skipped (the bass typically plays the root /
chord tones with passing notes that aren't worth flagging at this level).
"""

from __future__ import annotations

import music21 as m21

from ...model.issue import Issue
from ...model.score import NOTE_NAMES, Score
from ...model.slice import Slice

RULE_ID = "chord_tone_check"


def _chord_pitch_classes(slice_obj: Slice) -> set[int] | None:
    """Return chord-tone pitch class integers (0..11), or None if undetectable."""
    if not slice_obj.notes:
        return None
    try:
        ch = m21.chord.Chord([n.pitch for n in slice_obj.notes])
        return {p.pitchClass for p in ch.pitches}
    except Exception:
        return None


def check(score: Score, slices: list[Slice]) -> list[Issue]:
    issues: list[Issue] = []
    bass_parts = {p.name for p in score.parts if "bass" in p.name.lower()}

    for sl in slices:
        chord_pcs = _chord_pitch_classes(sl)
        if chord_pcs is None:
            continue
        for note in sl.notes:
            if note.part in bass_parts:
                continue
            if note.pitch % 12 in chord_pcs:
                continue
            pc_name = NOTE_NAMES[note.pitch % 12]
            chord_label = sl.detected_chord or ",".join(sl.pitch_classes)
            issues.append(
                Issue(
                    bar=sl.bar,
                    beat_in_bar=sl.beat_in_bar,
                    severity="warning",
                    rule_id=RULE_ID,
                    description=(
                        f"{note.part} {note.pitch_name} ({pc_name}) is not a chord tone "
                        f"of {chord_label}"
                    ),
                    affected_notes=[note],
                    affected_parts=[note.part],
                    context={"chord": chord_label, "note_pc": pc_name},
                )
            )
    return issues
