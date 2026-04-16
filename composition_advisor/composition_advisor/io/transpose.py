"""Apply per-part octave transposition to a normalized Score.

Usage:
    offsets = {"bass": -12, "epiano": 24}   # semitones
    apply_transpose(score, offsets)

This mutates the Score in place: every Note whose `part` name matches
a key in `offsets` (case-insensitive substring match) gets its pitch,
pitch_name, and pitch_name_scientific updated.
"""

from __future__ import annotations

from ..model.score import Score, midi_to_scientific, midi_to_studio_one


def apply_transpose(score: Score, offsets: dict[str, int]) -> None:
    """Transpose notes in matching parts by the given semitone offsets.

    `offsets` maps a part-name keyword (case-insensitive substring) to
    a signed semitone offset. Example: {"bass": -12} transposes every
    note in a part whose name contains "bass" down one octave.
    """
    if not offsets:
        return
    for part in score.parts:
        offset = _find_offset(part.name, offsets)
        if offset == 0:
            continue
        for note in part.notes:
            note.pitch = max(0, min(127, note.pitch + offset))
            note.pitch_name = midi_to_studio_one(note.pitch)
            note.pitch_name_scientific = midi_to_scientific(note.pitch)


def _find_offset(part_name: str, offsets: dict[str, int]) -> int:
    lower = part_name.lower()
    for key, val in offsets.items():
        if key.lower() in lower:
            return val
    return 0


def parse_transpose_string(s: str) -> dict[str, int]:
    """Parse a comma-separated string like 'bass:-12,epiano:24' into a dict.

    Also accepts octave shorthand: 'bass:-1oct,epiano:+2oct' where
    1oct = 12 semitones.
    """
    if not s or not s.strip():
        return {}
    result: dict[str, int] = {}
    for pair in s.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        name, val_str = pair.split(":", 1)
        name = name.strip()
        val_str = val_str.strip().lower()
        if val_str.endswith("oct"):
            val_str = val_str[:-3].strip()
            multiplier = 12
        else:
            multiplier = 1
        try:
            result[name] = int(val_str) * multiplier
        except ValueError:
            continue
    return result
