"""Detect notes outside the practical range of a part's instrument.

Phase 3 keeps the instrument map small and easily extendable. Part names are
matched against keys (case-insensitive substring). If no key matches, the
part is skipped — better to be silent than to flag false positives.
"""

from __future__ import annotations

from ...model.issue import Issue
from ...model.score import Score
from ...model.score import midi_to_studio_one
from ...model.slice import Slice

RULE_ID = "range_check"

# (low_midi, high_midi) inclusive practical ranges, conservative.
# Part name keywords are matched case-insensitively as substrings.
INSTRUMENT_RANGES: dict[str, tuple[int, int]] = {
    "trumpet":   (54, 84),  # F#3 .. C6
    "tp":        (54, 84),
    "trombone":  (40, 70),  # E2 .. Bb4
    "tb":        (40, 70),
    "alto":      (49, 81),  # alto sax C#3 .. A5
    "tenor":     (44, 75),  # tenor sax Ab2 .. Eb5
    "bari":      (37, 70),  # bari sax C#2 .. Bb4
    "violin":    (55, 96),  # G3 .. C7
    "viola":     (48, 84),  # C3 .. C6
    "cello":     (36, 76),  # C2 .. E5
    "bass":      (28, 60),  # double/electric bass E1 .. C4
    "guitar":    (40, 84),  # E2 .. C6
    "epiano":    (28, 103),
    "piano":     (21, 108),
    "synth":     (12, 120),
}


def _range_for(part_name: str) -> tuple[int, int] | None:
    name = part_name.lower()
    for key, rng in INSTRUMENT_RANGES.items():
        if key in name:
            return rng
    return None


def check(score: Score, slices: list[Slice]) -> list[Issue]:
    issues: list[Issue] = []
    seen: set[tuple[str, int, int, float]] = set()  # dedupe across slices

    for sl in slices:
        for note in sl.notes:
            rng = _range_for(note.part)
            if rng is None:
                continue
            low, high = rng
            if low <= note.pitch <= high:
                continue
            key = (note.part, note.pitch, note.bar, note.beat_in_bar)
            if key in seen:
                continue
            seen.add(key)
            direction = "below" if note.pitch < low else "above"
            limit = midi_to_studio_one(low if direction == "below" else high)
            issues.append(
                Issue(
                    bar=note.bar,
                    beat_in_bar=note.beat_in_bar,
                    severity="warning",
                    rule_id=RULE_ID,
                    description=(
                        f"{note.part} {note.pitch_name} is {direction} the practical "
                        f"range (limit {limit})"
                    ),
                    affected_notes=[note],
                    affected_parts=[note.part],
                    context={"range_low": low, "range_high": high},
                )
            )
    return issues
