"""Detect chords by chordifying a Score and walking each vertical slice."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import music21 as m21

logger = logging.getLogger(__name__)


@dataclass
class ChordHit:
    """A single chord detected at a specific bar/beat position."""

    bar: int
    beat: float          # 1-indexed beat-in-bar (music21 convention)
    chord_name: str      # e.g. "C major triad", "G7"
    pitches: list[str]   # e.g. ["C4", "E4", "G4"]
    degree: Optional[str] = None  # filled by degree_assigner


def detect_chords(score: m21.stream.Score) -> list[ChordHit]:
    """Run music21's chordify() and collect each vertical chord.

    Rests and empty verticals are skipped. The result preserves source order.

    Args:
        score: A music21 Score (typically the merged output of load_midi_files).

    Returns:
        A list of ChordHit objects, one per chordified vertical slice.
    """
    chordified = score.chordify()
    hits: list[ChordHit] = []

    for c in chordified.recurse().getElementsByClass(m21.chord.Chord):
        if not c.pitches:
            continue
        bar = c.measureNumber if c.measureNumber is not None else 0
        beat = float(c.beat) if c.beat is not None else 0.0
        try:
            name = c.pitchedCommonName
        except Exception:
            name = c.commonName or "unknown"

        hits.append(
            ChordHit(
                bar=bar,
                beat=beat,
                chord_name=name,
                pitches=[str(p) for p in c.pitches],
            )
        )

    logger.info("Detected %d chord slices", len(hits))
    return hits
