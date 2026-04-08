"""Issue + AnalysisResult — the output of rule-based critique."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .score import Note, ScoreMetadata
from .slice import Slice

Severity = Literal["info", "warning", "error"]


class Issue(BaseModel):
    """A single problem detected by a rule."""

    bar: int
    beat_in_bar: float
    severity: Severity = "warning"
    rule_id: str
    description: str
    affected_notes: list[Note] = Field(default_factory=list)
    affected_parts: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Top-level analysis output: metadata + slices + issues."""

    metadata: ScoreMetadata
    slices: list[Slice] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
