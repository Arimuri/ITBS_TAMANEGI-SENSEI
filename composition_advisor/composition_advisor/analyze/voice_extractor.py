"""Build vertical Slices from a normalized internal Score.

A Slice is the set of notes sounding at a given moment. We compute the slice
boundaries by collecting every distinct note start/end onset across all parts
(a "sweep line"), then for each segment between consecutive onsets we collect
all notes whose [start, start+duration) interval contains the segment.

Each Slice is also annotated with `pitch_classes`, `bass_note`, and a
best-effort `detected_chord` from music21's chord identification.
"""

from __future__ import annotations

import logging

import music21 as m21

from ..model.score import NOTE_NAMES, Note, Score
from ..model.slice import Slice

logger = logging.getLogger(__name__)

EPS = 1e-6


def _all_notes(score: Score) -> list[Note]:
    out: list[Note] = []
    for part in score.parts:
        out.extend(part.notes)
    return out


def _onsets(notes: list[Note]) -> list[float]:
    """Return sorted unique start/end beat positions across all notes."""
    points: set[float] = set()
    for n in notes:
        points.add(round(n.start_beat, 6))
        points.add(round(n.start_beat + n.duration, 6))
    return sorted(points)


def _bar_and_beat(
    start_beat: float, bar_starts: list[float], beats_per_bar: float
) -> tuple[int, float]:
    """Compute (bar, beat_in_bar) from an absolute beat position.

    Uses the measure-offset table from the score when available, so meter
    changes mid-piece work correctly. Falls back to a constant time
    signature if `bar_starts` is empty (legacy / handcrafted Score objects).
    """
    if not bar_starts:
        bar = int(start_beat // beats_per_bar) + 1
        return (bar, (start_beat % beats_per_bar) + 1.0)

    # Find the rightmost bar whose start <= start_beat (binary search).
    lo, hi = 0, len(bar_starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if bar_starts[mid] <= start_beat + EPS:
            lo = mid + 1
        else:
            hi = mid
    idx = max(0, lo - 1)
    bar = idx + 1  # 1-indexed
    beat_in_bar = start_beat - bar_starts[idx] + 1.0
    return (bar, beat_in_bar)


def _detect_chord_name(notes_at: list[Note]) -> str | None:
    """Best-effort chord name from a set of sounding notes."""
    if not notes_at:
        return None
    try:
        ch = m21.chord.Chord([n.pitch for n in notes_at])
        return ch.pitchedCommonName
    except Exception as e:
        logger.debug("chord name failed: %s", e)
        return None


def _beats_per_bar(score: Score) -> float:
    """Parse top number of metadata.time_signature; default to 4."""
    ts = score.metadata.time_signature
    if not ts or "/" not in ts:
        return 4.0
    try:
        return float(ts.split("/")[0])
    except ValueError:
        return 4.0


def extract_slices(score: Score) -> list[Slice]:
    """Build a list of Slices spanning the whole Score.

    Empty intervals (no notes sounding) are skipped. Slices that contain
    notes from only one part are still emitted — downstream rules can choose
    to ignore them.
    """
    notes = _all_notes(score)
    if not notes:
        return []

    beats_per_bar = _beats_per_bar(score)
    bar_starts = score.metadata.bar_starts
    onsets = _onsets(notes)
    slices: list[Slice] = []

    for i in range(len(onsets) - 1):
        seg_start = onsets[i]
        seg_end = onsets[i + 1]
        if seg_end - seg_start < EPS:
            continue
        midpoint = (seg_start + seg_end) / 2.0

        sounding = [
            n for n in notes
            if n.start_beat - EPS <= midpoint < n.start_beat + n.duration - EPS
        ]
        if not sounding:
            continue

        bar, beat_in_bar = _bar_and_beat(seg_start, bar_starts, beats_per_bar)
        pitch_classes = sorted({NOTE_NAMES[n.pitch % 12] for n in sounding})
        bass = min(sounding, key=lambda n: n.pitch)

        slices.append(
            Slice(
                bar=bar,
                beat_in_bar=beat_in_bar,
                start_beat=seg_start,
                duration=seg_end - seg_start,
                notes=sounding,
                pitch_classes=pitch_classes,
                bass_note=bass.pitch_name,
                detected_chord=_detect_chord_name(sounding),
            )
        )

    logger.info("Extracted %d slices", len(slices))
    return slices
