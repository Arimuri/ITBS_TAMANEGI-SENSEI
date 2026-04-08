"""Convert a music21 Score into the internal pydantic Score model."""

from __future__ import annotations

import logging

import music21 as m21

from ..model.score import (
    Note,
    Part,
    Score,
    ScoreMetadata,
    midi_to_scientific,
    midi_to_studio_one,
)

logger = logging.getLogger(__name__)


def normalize_score(m21_score: m21.stream.Score, key: m21.key.Key | None = None) -> Score:
    """Convert a music21 Score into the internal Score model.

    Each music21 Part becomes one internal Part. Chords are flattened into
    their constituent notes (each note carries the same start/duration).

    Args:
        m21_score: The music21 Score (typically from `load_midi_files`).
        key: Optional already-detected Key, included in metadata.

    Returns:
        Internal Score with metadata + parts populated.
    """
    parts: list[Part] = []
    part_names: list[str] = []
    max_bar = 0

    # Tempo / time signature: take the first found in the score.
    ts = next(iter(m21_score.recurse().getElementsByClass(m21.meter.TimeSignature)), None)
    mm = next(iter(m21_score.recurse().getElementsByClass(m21.tempo.MetronomeMark)), None)

    for idx, m21_part in enumerate(m21_score.parts):
        part_name = m21_part.partName or f"part{idx}"
        part_names.append(part_name)
        notes: list[Note] = []

        flat = m21_part.flatten()
        for elem in flat.notes:
            # `elem` is either Note or Chord
            bar = elem.measureNumber if elem.measureNumber is not None else 0
            max_bar = max(max_bar, bar)
            beat_in_bar = float(elem.beat) if elem.beat is not None else 0.0
            # offset on the flattened stream is absolute within the part.
            # Parts are inserted at score offset 0, so this equals song offset.
            start_beat = float(elem.offset)
            duration = float(elem.duration.quarterLength)
            velocity = (
                elem.volume.velocity
                if elem.volume and elem.volume.velocity is not None
                else 64
            )

            pitches = elem.pitches if hasattr(elem, "pitches") else [elem.pitch]
            for p in pitches:
                midi = int(p.midi)
                notes.append(
                    Note(
                        pitch=midi,
                        pitch_name=midi_to_studio_one(midi),
                        pitch_name_scientific=midi_to_scientific(midi),
                        start_beat=start_beat,
                        bar=bar,
                        beat_in_bar=beat_in_bar,
                        duration=duration,
                        part=part_name,
                        velocity=int(velocity),
                    )
                )

        notes.sort(key=lambda n: (n.start_beat, n.pitch))
        parts.append(Part(name=part_name, notes=notes))

    # Build bar_starts from any part's measures (they all share the same
    # measure boundaries in a chordified MIDI input).
    bar_starts: list[float] = []
    for m21_part in m21_score.parts:
        measures = list(m21_part.getElementsByClass(m21.stream.Measure))
        if measures:
            bar_starts = [float(m.offset) for m in measures]
            break

    metadata = ScoreMetadata(
        key=str(key) if key else None,
        time_signature=ts.ratioString if ts else None,
        tempo_bpm=float(mm.number) if mm and mm.number else None,
        bar_count=max_bar,
        part_names=part_names,
        bar_starts=bar_starts,
    )
    logger.info("Normalized score: %d parts, %d bars", len(parts), max_bar)
    return Score(metadata=metadata, parts=parts)
