"""Account-scoped, append-only learning history with idempotent offline uploads."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .counterpoint.models import Note


class HistoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Location(HistoryModel):
    measure: int = Field(ge=1)
    beat: int | float = Field(ge=1, le=4)


class Issue(HistoryModel):
    id: str = Field(max_length=300)
    ruleId: str = Field(max_length=100)
    severity: Literal["error", "warning", "info"]
    noteIds: list[str] = Field(max_length=128)
    locations: list[Location] = Field(max_length=128)
    message: str = Field(max_length=4000)
    explanation: str = Field(max_length=8000)
    hint: str = Field(max_length=4000)


class HistoricalGrade(HistoryModel):
    exerciseId: str = Field(min_length=1, max_length=100)
    ruleProfileId: str = Field(max_length=100)
    ruleProfileVersion: str = Field(max_length=30)
    engineVersion: str = Field(max_length=30)
    assessmentStatus: Literal["complete", "incomplete", "invalid"]
    passed: bool
    hardViolationCount: int = Field(ge=0)
    warningCount: int = Field(ge=0)
    issues: list[Issue] = Field(max_length=512)
    ruleCounts: dict[str, int]


class HistoryRecord(HistoryModel):
    id: str = Field(min_length=1, max_length=100)
    attemptId: str = Field(min_length=1, max_length=100)
    submittedAt: str = Field(max_length=50)
    notes: list[Note] = Field(max_length=64)
    result: HistoricalGrade
    hints: dict[str, int] = Field(max_length=512)

    @field_validator("submittedAt")
    @classmethod
    def valid_time(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @field_validator("notes")
    @classmethod
    def counterpoint_only(cls, value: list[Note]) -> list[Note]:
        if any(note.voiceId != "cp" for note in value):
            raise ValueError("history contains only counterpoint notes")
        return value

    @field_validator("hints")
    @classmethod
    def hint_levels(cls, value: dict[str, int]) -> dict[str, int]:
        if any(len(key) > 300 or level not in range(4) for key, level in value.items()):
            raise ValueError("invalid hint level")
        return value


class SyncRequest(HistoryModel):
    records: list[HistoryRecord] = Field(default_factory=list, max_length=100)
    after: int = Field(default=0, ge=0)


class HistoryConflict(ValueError):
    """A UUID was reused with a different immutable snapshot."""


def _encode(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class HistoryDatabase:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS history (
                account TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                revision INTEGER NOT NULL UNIQUE, PRIMARY KEY(account, id))""")
            db.execute("CREATE INDEX IF NOT EXISTS history_account_revision ON history(account, revision)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def sync(self, account: str, request: SyncRequest) -> dict:
        # One transaction prevents a retry/concurrent device from losing a record
        # or overwriting the immutable answer. Hint disclosure only ever increases.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            revision = db.execute("SELECT COALESCE(MAX(revision), 0) FROM history").fetchone()[0]
            for item in request.records:
                incoming = item.model_dump()
                old_row = db.execute("SELECT body FROM history WHERE account=? AND id=?", (account, item.id)).fetchone()
                if old_row:
                    old = json.loads(old_row[0])
                    old_core = {k: v for k, v in old.items() if k != "hints"}
                    new_core = {k: v for k, v in incoming.items() if k != "hints"}
                    if old_core != new_core:
                        raise HistoryConflict("同じ履歴IDに異なる回答があります。端末の履歴は保持されています。")
                    incoming["hints"] = {key: max(old["hints"].get(key, 0), incoming["hints"].get(key, 0))
                                         for key in old["hints"].keys() | incoming["hints"].keys()}
                    if incoming == old:
                        continue
                revision += 1
                db.execute("""INSERT INTO history(account,id,body,revision) VALUES(?,?,?,?)
                    ON CONFLICT(account,id) DO UPDATE SET body=excluded.body,revision=excluded.revision""",
                           (account, item.id, _encode(incoming), revision))
            rows = db.execute("SELECT body,revision FROM history WHERE account=? AND revision>? ORDER BY revision LIMIT 201",
                              (account, request.after)).fetchall()
            page = rows[:200]
            return {"enabled": True, "records": [json.loads(row[0]) for row in page],
                    "cursor": page[-1][1] if page else request.after, "hasMore": len(rows) > 200}
