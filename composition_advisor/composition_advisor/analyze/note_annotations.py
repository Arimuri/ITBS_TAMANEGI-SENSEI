"""Per-note analytic annotations.

For each Note we compute:
    scale_degree            — その音がキーに対して何度か(例: C major で E なら "3"、F# なら "#4")
    scale_degree_int        — 1..7 の整数
    melodic_interval_prev   — 同じパート内で1つ前の音との旋律的インターバル
                              (符号付き semitones、最初の音は None)
    melodic_interval_label  — 上記を音楽用語で表現したラベル
                              (例: "+M3"(上行長3度), "-P5"(下行完全5度), "+P1"(同音))

Output is a list of NoteAnnotation, parallel to the score's Notes (one entry
per part, in order). The server side joins them onto the AnalysisResult
JSON so the browser can render them on top of the OSMD score.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

import music21 as m21

from ..model.score import Note, Part, Score

# Scale-degree label per chromatic offset (in semitones) from the key tonic.
# Major-key oriented: anything outside the diatonic 7 gets a #/b prefix
# pointing at the nearest diatonic neighbour.
DEGREE_LABELS = [
    "1",   # 0
    "♭2",  # 1
    "2",   # 2
    "♭3",  # 3
    "3",   # 4
    "4",   # 5
    "♯4",  # 6
    "5",   # 7
    "♭6",  # 8
    "6",   # 9
    "♭7",  # 10
    "7",   # 11
]
DEGREE_INT = [1, 2, 2, 3, 3, 4, 4, 5, 6, 6, 7, 7]

# Interval labels for absolute semitone counts (mod 12 falls back to compound).
INTERVAL_LABELS = {
    0: "P1",
    1: "m2",
    2: "M2",
    3: "m3",
    4: "M3",
    5: "P4",
    6: "TT",
    7: "P5",
    8: "m6",
    9: "M6",
    10: "m7",
    11: "M7",
    12: "P8",
}


def _label_interval(semitones: int) -> str:
    sign = "+" if semitones > 0 else ("-" if semitones < 0 else "")
    abs_st = abs(semitones)
    octaves, rest = divmod(abs_st, 12)
    base = INTERVAL_LABELS.get(rest, f"{rest}st")
    if octaves == 0:
        return sign + base
    if octaves == 1 and rest == 0:
        return sign + "P8"
    return f"{sign}{base}+{octaves}oct"


class NoteAnnotation(BaseModel):
    """Annotation aligned with one Note in one Part."""

    part: str
    note_index: int = Field(..., description="0-indexed within the part's note list")
    pitch: int
    pitch_name: str
    bar: int
    beat_in_bar: float
    start_beat: float
    duration: float = 4.0
    scale_degree: str | None
    scale_degree_int: int | None
    melodic_interval_prev: int | None
    melodic_interval_label: str | None


def _key_tonic_pc(key: m21.key.Key | None) -> int | None:
    if key is None:
        return None
    try:
        return key.tonic.pitchClass
    except Exception:
        return None


def annotate_score(score: Score, key: m21.key.Key | None = None) -> list[NoteAnnotation]:
    """Compute per-note annotations across every part of the internal Score."""
    tonic_pc = _key_tonic_pc(key)
    out: list[NoteAnnotation] = []

    for part in score.parts:
        ordered = sorted(part.notes, key=lambda n: n.start_beat)
        prev: Note | None = None
        for idx, n in enumerate(ordered):
            if tonic_pc is not None:
                offset = (n.pitch - tonic_pc) % 12
                degree_label = DEGREE_LABELS[offset]
                degree_int = DEGREE_INT[offset]
            else:
                degree_label = None
                degree_int = None

            if prev is None:
                mi = None
                mi_label = None
            else:
                mi = n.pitch - prev.pitch
                mi_label = _label_interval(mi)

            out.append(
                NoteAnnotation(
                    part=part.name,
                    note_index=idx,
                    pitch=n.pitch,
                    pitch_name=n.pitch_name,
                    bar=n.bar,
                    beat_in_bar=n.beat_in_bar,
                    start_beat=n.start_beat,
                    duration=n.duration,
                    scale_degree=degree_label,
                    scale_degree_int=degree_int,
                    melodic_interval_prev=mi,
                    melodic_interval_label=mi_label,
                )
            )
            prev = n

    return out
