"""Shared pytest fixtures.

Builds an in-memory internal Score with two parts so individual rule tests
can stay tiny and self-contained without spinning up music21 each time.
"""

from __future__ import annotations

import pytest

from composition_advisor.analyze.voice_extractor import extract_slices
from composition_advisor.model.score import (
    Note,
    Part,
    Score,
    ScoreMetadata,
    midi_to_scientific,
    midi_to_studio_one,
)


def make_note(midi: int, part: str, start: float, dur: float = 4.0, bar: int = 1, beat: float = 1.0) -> Note:
    return Note(
        pitch=midi,
        pitch_name=midi_to_studio_one(midi),
        pitch_name_scientific=midi_to_scientific(midi),
        start_beat=start,
        bar=bar,
        beat_in_bar=beat,
        duration=dur,
        part=part,
        velocity=90,
    )


def build_score(parts: dict[str, list[Note]], time_signature: str = "4/4") -> Score:
    return Score(
        metadata=ScoreMetadata(
            key="C major",
            time_signature=time_signature,
            tempo_bpm=120.0,
            bar_count=max((max((n.bar for n in notes), default=0) for notes in parts.values()), default=0),
            part_names=list(parts.keys()),
        ),
        parts=[Part(name=name, notes=notes) for name, notes in parts.items()],
    )


@pytest.fixture
def make_note_fn():
    return make_note


@pytest.fixture
def build_score_fn():
    return build_score


@pytest.fixture
def slice_fn():
    return extract_slices
