"""Load one or more MIDI files into a single music21 Score."""

from __future__ import annotations

import logging
from pathlib import Path

import music21 as m21

logger = logging.getLogger(__name__)


def load_midi_files(paths: list[str | Path]) -> m21.stream.Score:
    """Load multiple MIDI files and merge into a single Score.

    Each input file is parsed as its own Part (or set of Parts) and inserted
    at offset 0 of the output Score so they play simultaneously. The original
    file stem is used as the part name to keep tracks identifiable downstream.

    Args:
        paths: Paths to .mid files. At least one is required.

    Returns:
        A music21 Score containing every part from every input file.

    Raises:
        FileNotFoundError: If any input path does not exist.
        ValueError: If `paths` is empty.
    """
    if not paths:
        raise ValueError("load_midi_files requires at least one path")

    score = m21.stream.Score()
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(f"MIDI file not found: {path}")
        logger.info("Parsing MIDI: %s", path)
        try:
            parsed = m21.converter.parse(str(path))
        except Exception as e:
            raise RuntimeError(f"Failed to parse {path}: {e}") from e

        # parsed may be a Score (with multiple Parts) or a single Part.
        if isinstance(parsed, m21.stream.Score):
            for part in parsed.parts:
                if not part.partName:
                    part.partName = path.stem
                score.insert(0, part)
        else:
            if hasattr(parsed, "partName") and not parsed.partName:
                parsed.partName = path.stem
            score.insert(0, parsed)

    return score
