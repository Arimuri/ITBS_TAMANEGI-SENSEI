"""Assign Roman numeral degrees to detected chords given a key."""

from __future__ import annotations

import logging

import music21 as m21

from .chord_detector import ChordHit

logger = logging.getLogger(__name__)


def assign_degrees(chords: list[ChordHit], key: m21.key.Key) -> list[ChordHit]:
    """Add a Roman numeral `degree` field to each ChordHit, in place.

    Args:
        chords: List of ChordHit (output of detect_chords).
        key: music21 Key the chords should be analyzed in.

    Returns:
        The same list, with `degree` populated where possible.
    """
    for hit in chords:
        try:
            chord_obj = m21.chord.Chord(hit.pitches)
            rn = m21.roman.romanNumeralFromChord(chord_obj, key)
            hit.degree = rn.romanNumeral
        except Exception as e:
            logger.debug("degree assign failed at bar%s beat%s: %s",
                         hit.bar, hit.beat, e)
            hit.degree = None
    return chords
