"""Classify each melody-line note against the slice's chord and the song's key.

Phase improvement: instead of treating "anything not in the chord" as a
warning, we classify each melody note into one of three buckets:

    chord_tone        — pitch class is part of the surrounding harmony (skip)
    diatonic_tension  — pc is in the song's scale but not in the chord (info)
    chromatic         — pc is not in the song's scale (warning)

Only "melody-like" parts are checked. Parts whose names match harmony/bass
substrings (chord, comp, piano, epiano, synth, pad, keys, bass, ...) are
treated as the harmonic background, not the line being judged. If you want
to force-check a specific part, list it in params['target_parts'].

Short-duration notes (< params['ignore_durations_below'], default 0.25 beats)
are skipped — they're treated as passing/approach notes.

Params (from RuleConfig.params):
    ignore_durations_below: float (default 0.25)
    target_parts: list[str] (default None — auto-detect)
    harmony_keywords: list[str] (default standard harmony part names)
"""

from __future__ import annotations

from typing import Any

import music21 as m21

from ...model.issue import Issue
from ...model.score import NOTE_NAMES, Score
from ...model.slice import Slice

RULE_ID = "chord_tone_check"

DEFAULT_HARMONY_KEYWORDS = (
    "chord", "comp", "piano", "epiano", "ep", "rhodes", "wurli",
    "synth", "pad", "keys", "organ", "bass",
)


def _is_harmony_part(name: str, keywords: tuple[str, ...]) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in keywords)


def _chord_pitch_classes_excluding(slice_obj: Slice, exclude_part: str) -> set[int] | None:
    """Pitch classes of the harmonic background under a given part.

    We exclude the part being tested so the melody note itself doesn't get
    counted as part of "the chord", which would always make it look like a
    chord tone.
    """
    others = [n for n in slice_obj.notes if n.part != exclude_part]
    if not others:
        return None
    try:
        ch = m21.chord.Chord([n.pitch for n in others])
        return {p.pitchClass for p in ch.pitches}
    except Exception:
        return None


def _scale_pitch_classes(score: Score) -> set[int] | None:
    """Return the diatonic scale pitch classes for the score's key, if known."""
    name = score.metadata.key
    if not name:
        return None
    try:
        key = m21.key.Key(name.split()[0]) if " " in name else m21.key.Key(name)
        return {p.pitchClass for p in key.getScale().getPitches()}
    except Exception:
        return None


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    params = params or {}
    min_duration = float(params.get("ignore_durations_below", 0.25))
    keywords = tuple(params.get("harmony_keywords", DEFAULT_HARMONY_KEYWORDS))
    target_parts_explicit = params.get("target_parts")

    if target_parts_explicit:
        target_parts = set(target_parts_explicit)
    else:
        target_parts = {
            p.name for p in score.parts if not _is_harmony_part(p.name, keywords)
        }

    issues: list[Issue] = []
    scale_pcs = _scale_pitch_classes(score)

    for sl in slices:
        for note in sl.notes:
            if note.part not in target_parts:
                continue
            if note.duration < min_duration:
                continue

            chord_pcs = _chord_pitch_classes_excluding(sl, note.part)
            if chord_pcs is None:
                continue  # nothing else sounding -> can't judge

            pc = note.pitch % 12
            if pc in chord_pcs:
                continue  # chord tone — fine

            pc_name = NOTE_NAMES[pc]
            chord_label = sl.detected_chord or ",".join(sl.pitch_classes)

            if scale_pcs is not None and pc in scale_pcs:
                kind = "diatonic_tension"
                severity = "info"
                desc = (
                    f"{note.part}の{note.pitch_name}({pc_name})は{chord_label}に対して"
                    f"ダイアトニックなテンションです。"
                )
            else:
                kind = "chromatic"
                severity = "warning"
                desc = (
                    f"{note.part}の{note.pitch_name}({pc_name})は{chord_label}に対して"
                    f"スケール外のクロマティック音です。"
                )

            issues.append(
                Issue(
                    bar=sl.bar,
                    beat_in_bar=sl.beat_in_bar,
                    severity=severity,  # type: ignore[arg-type]
                    rule_id=RULE_ID,
                    description=desc,
                    affected_notes=[note],
                    affected_parts=[note.part],
                    context={"chord": chord_label, "note_pc": pc_name, "kind": kind},
                )
            )
    return issues
