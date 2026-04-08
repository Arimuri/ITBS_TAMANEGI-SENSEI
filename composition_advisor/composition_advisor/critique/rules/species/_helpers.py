"""Helpers shared by Species Counterpoint rules.

These rules expect a Score with two parts: a `cantus_firmus` part (the
fixed melody) and a `counterpoint` (or any other name) part. The runner is
told which part is which through `params['cantus_firmus_part']` and
`params['counterpoint_part']`. If those are absent we fall back to part
names containing the substrings "cantus" / "counter".
"""

from __future__ import annotations

from typing import Any

from ....model.score import Note, Part, Score

PERFECT_INTERVALS = {0, 7, 12}  # unison, perfect 5th, octave (mod 12 below)
CONSONANT_INTERVALS = {0, 3, 4, 7, 8, 9, 12}  # P1, m3, M3, P5, m6, M6, P8
DISSONANT_INTERVALS = {1, 2, 5, 6, 10, 11}    # m2, M2, P4, TT, m7, M7


def find_part(score: Score, params: dict[str, Any], role: str, fallback_kw: str) -> Part | None:
    """Locate a part by params override or by name keyword."""
    name_override = params.get(role) if params else None
    if name_override:
        for p in score.parts:
            if p.name == name_override:
                return p
        return None
    for p in score.parts:
        if fallback_kw in p.name.lower():
            return p
    return None


def cf_and_cp(score: Score, params: dict[str, Any] | None) -> tuple[Part, Part] | None:
    """Return (cantus_firmus, counterpoint) parts, or None if undetectable."""
    params = params or {}
    cf = find_part(score, params, "cantus_firmus_part", "cantus")
    cp = find_part(score, params, "counterpoint_part", "counter")
    if cf is None or cp is None:
        return None
    return cf, cp


def harmonic_interval(a: Note, b: Note) -> int:
    """Absolute interval in semitones, modulo octaves above 12."""
    diff = abs(a.pitch - b.pitch)
    return diff


def melodic_interval(a: Note, b: Note) -> int:
    """Signed melodic interval in semitones from a to b."""
    return b.pitch - a.pitch


def is_perfect(semitones: int) -> bool:
    return semitones % 12 in (0, 7) and semitones >= 0


def is_consonant(semitones: int) -> bool:
    return (semitones % 12) in CONSONANT_INTERVALS


def is_dissonant(semitones: int) -> bool:
    return (semitones % 12) in DISSONANT_INTERVALS


def pair_notes_by_position(cf: Part, cp: Part) -> list[tuple[Note, Note]]:
    """Pair cantus firmus notes with counterpoint notes whose start_beat matches.

    For Species 1 this is a 1:1 alignment. We tolerate small float drift
    (1e-3 beats). Notes that don't pair up are skipped.
    """
    pairs: list[tuple[Note, Note]] = []
    EPS = 1e-3
    cp_by_start: dict[int, Note] = {}
    for n in cp.notes:
        key = round(n.start_beat * 1000)
        cp_by_start[key] = n
    for cf_note in cf.notes:
        key = round(cf_note.start_beat * 1000)
        cp_note = cp_by_start.get(key)
        if cp_note is None:
            # try near match
            for k, v in cp_by_start.items():
                if abs(k - key) < EPS * 1000:
                    cp_note = v
                    break
        if cp_note is not None:
            pairs.append((cf_note, cp_note))
    return pairs


def cf_active_at(cf: Part, beat: float) -> Note | None:
    """Return the cantus firmus note that is sounding at the given absolute beat."""
    EPS = 1e-3
    for n in cf.notes:
        if n.start_beat - EPS <= beat < n.start_beat + n.duration - EPS:
            return n
    return None


def group_cp_under_cf(cf: Part, cp: Part) -> list[tuple[Note, list[Note]]]:
    """Group counterpoint notes by which cantus firmus note they sound under.

    Returns a list of (cf_note, [cp_notes]) where cp_notes are the counterpoint
    notes whose start_beat falls inside the cf_note's duration. Used by
    Species 2-5 where multiple cp notes share one cf note.
    """
    EPS = 1e-3
    out: list[tuple[Note, list[Note]]] = []
    for cf_n in cf.notes:
        cp_in = [
            n for n in cp.notes
            if cf_n.start_beat - EPS <= n.start_beat < cf_n.start_beat + cf_n.duration - EPS
        ]
        cp_in.sort(key=lambda x: x.start_beat)
        out.append((cf_n, cp_in))
    return out


def is_step(a: Note, b: Note) -> bool:
    """True iff two consecutive counterpoint notes move by a 2nd (1 or 2 semitones)."""
    return abs(a.pitch - b.pitch) in (1, 2)


def is_neighbor(a: Note, b: Note, c: Note) -> bool:
    """True iff a-b-c forms a neighbor figure: step away then step back to the same pitch."""
    return a.pitch == c.pitch and is_step(a, b) and is_step(b, c)
