"""Internal Score / Part / Note pydantic models.

These are the canonical, DAW-agnostic representation that all downstream
analyzers (chord/voice/issue) operate on. The music21 -> internal conversion
lives in `composition_advisor.io.normalize`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_studio_one(midi_num: int) -> str:
    """MIDI note number → Studio One pitch name (middle C = C3)."""
    return f"{NOTE_NAMES[midi_num % 12]}{midi_num // 12 - 2}"


def midi_to_scientific(midi_num: int) -> str:
    """MIDI note number → scientific pitch name (middle C = C4)."""
    return f"{NOTE_NAMES[midi_num % 12]}{midi_num // 12 - 1}"


class Note(BaseModel):
    """A single note from a single part."""

    pitch: int = Field(..., description="MIDI note number 0-127")
    pitch_name: str = Field(..., description="Studio One pitch name (middle C = C3)")
    pitch_name_scientific: str = Field(
        ..., description="Scientific pitch name (middle C = C4)"
    )
    start_beat: float = Field(..., description="Absolute beat position from song start")
    bar: int = Field(..., description="1-indexed bar number")
    beat_in_bar: float = Field(..., description="1-indexed beat-in-bar (music21 convention)")
    duration: float = Field(..., description="Duration in quarter-note beats")
    part: str = Field(..., description="Part / track name")
    velocity: int = Field(..., description="MIDI velocity 0-127")


class Part(BaseModel):
    """A named part containing a flat list of notes."""

    name: str
    notes: list[Note] = Field(default_factory=list)


class ScoreMetadata(BaseModel):
    """Top-level score metadata."""

    key: str | None = None              # e.g. "C major"
    time_signature: str | None = None    # e.g. "4/4"
    tempo_bpm: float | None = None
    bar_count: int = 0
    part_names: list[str] = Field(default_factory=list)


class Score(BaseModel):
    """A complete internal score: metadata + parts."""

    metadata: ScoreMetadata
    parts: list[Part] = Field(default_factory=list)
