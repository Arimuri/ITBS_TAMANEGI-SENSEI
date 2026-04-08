"""Detect the musical key of a Score using music21."""

from __future__ import annotations

import logging

import music21 as m21

logger = logging.getLogger(__name__)


def detect_key(score: m21.stream.Score, algorithm: str = "key") -> m21.key.Key:
    """Estimate the key of a Score.

    Args:
        score: A music21 Score.
        algorithm: music21 analysis algorithm name. Common choices:
            "key" (default), "Krumhansl", "Aarden", "Bellman".

    Returns:
        A music21 Key object (e.g. <music21.key.Key of C major>).
    """
    key = score.analyze(algorithm)
    logger.info("Detected key (%s): %s", algorithm, key)
    return key


def parse_key(name: str) -> m21.key.Key:
    """Parse a user-provided key string like "C", "Am", "Bb", "f#" into a Key.

    Args:
        name: Key name. Uppercase first letter = major, lowercase = minor.
            Examples: "C", "c", "Bb", "f#", "C major", "A minor".

    Returns:
        A music21 Key object.
    """
    return m21.key.Key(name)
