"""Spelled, integer-time notes for the tutor; independent of lossy MIDI models."""

from __future__ import annotations

from functools import cached_property
from typing import Literal

from music21 import interval, pitch
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpelledPitch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    step: Literal["C", "D", "E", "F", "G", "A", "B"]
    alter: int = Field(ge=-1, le=1)
    octave: int = Field(ge=-1, le=9)

    @cached_property
    def music21(self) -> pitch.Pitch:
        return pitch.Pitch(step=self.step, accidental=self.alter, octave=self.octave)

    @property
    def midi(self) -> int:
        # music21.midi folds out-of-range octaves; ps retains the actual pitch.
        return int(self.music21.ps)

    @property
    def label(self) -> str:
        return f"{self.step}{ {-1: '♭', 0: '', 1: '♯'}[self.alter]}{self.octave}"

    @model_validator(mode="after")
    def midi_range(self) -> SpelledPitch:
        if not 0 <= self.midi <= 127:
            raise ValueError("pitch must be in the MIDI 0–127 range")
        return self


class Note(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str = Field(min_length=1, max_length=100)
    voiceId: Literal["cf", "cp"]
    startTick: int = Field(ge=0)
    durationTicks: int = Field(gt=0)
    pitch: SpelledPitch


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    exerciseId: str = Field(min_length=1, max_length=100)
    notes: list[Note] = Field(max_length=64)
    cantus: list[Note] = Field(max_length=64)
    ruleProfileId: str
    ruleProfileVersion: str


def pitch_from_name(name: str) -> SpelledPitch:
    p = pitch.Pitch(name)
    return SpelledPitch(step=p.step, alter=int(p.accidental.alter) if p.accidental else 0,
                        octave=p.octave)


def between(a: SpelledPitch, b: SpelledPitch) -> interval.Interval:
    """Retain interval quality and written generic size, including compounds."""
    return interval.Interval(a.music21, b.music21)


def consonant(a: SpelledPitch, b: SpelledPitch) -> bool:
    return between(a, b).simpleName in {"P1", "P5", "m3", "M3", "m6", "M6"}


def perfect_family(a: SpelledPitch, b: SpelledPitch) -> str | None:
    name = between(a, b).simpleName
    return "octave" if name == "P1" else "fifth" if name == "P5" else None


def stepwise(a: SpelledPitch, b: SpelledPitch) -> bool:
    return between(a, b).name in {"m2", "M2"}
