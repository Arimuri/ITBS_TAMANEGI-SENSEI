"""Fix data structures.

A Fix is a single note-level edit that, when applied, should resolve (or
mitigate) one Issue. Fixes are pure data — applying them is a separate step
in `composition_advisor.fix.applier` so that ruleband, LLM, and any future
fix source can share the same write-out path.

Action types
------------
- transpose: change the pitch of a single note
- delete:    remove the note entirely
- shorten:   trim the note's duration (e.g. release earlier)
- shift:     move the note's start time
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .score import Note

FixAction = Literal["transpose", "delete", "shorten", "shift"]


class Fix(BaseModel):
    """A single proposed edit targeting one Note in one Part."""

    rule_id: str
    issue_index: int = -1               # back-pointer into AnalysisResult.issues
    action: FixAction
    target: Note                         # which note to change (matched by part+start+pitch)
    new_pitch: int | None = None         # for transpose
    new_pitch_name: str | None = None    # Studio One label of new pitch
    new_duration: float | None = None    # for shorten
    new_start_beat: float | None = None  # for shift
    rationale: str = Field(default="", description="Human-readable why")
    source: Literal["rule_based", "llm"] = "rule_based"


class FixSet(BaseModel):
    """A bag of fixes scoped to one analysis run."""

    fixes: list[Fix] = Field(default_factory=list)
