"""Slice (verticality) — the set of notes sounding at one moment."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .score import Note


class Slice(BaseModel):
    """A vertical cross-section of the score at one bar/beat position."""

    bar: int
    beat_in_bar: float = Field(..., description="1-indexed beat-in-bar")
    start_beat: float = Field(..., description="Absolute beat from song start")
    duration: float = Field(..., description="How long this slice lasts in beats")

    notes: list[Note] = Field(default_factory=list)
    pitch_classes: list[str] = Field(default_factory=list)
    bass_note: str | None = None         # Studio One pitch name of lowest note
    detected_chord: str | None = None    # e.g. "Cmaj7", "Caug/F#"
    detected_chord_degree: str | None = None  # e.g. "V7", "♭VII7"
