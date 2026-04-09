"""Learning track / lesson definitions.

A "Track" is a curriculum (例: 古典対位法 / ジャズ対位法 / シティポップ)
that contains a sequence of "Lesson"s. Each Lesson knows:
- 何を学ぶか(教科書ルール、Claude 添削の人格、課題の指示)
- どのルールで分析するか(rule_ids: composition_advisor.critique.rules.* と
  rules.species.* に対する参照)
- どのプロンプトで Claude に投げるか(system + user prompt template)

Tracks/Lessons are loaded from yaml files under tutor/lessons/ so that
adding a new lesson does not require Python code changes. The yaml schema
is intentionally small (see tutor/lessons/track_a.yaml as the canonical
example).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LessonDef(BaseModel):
    """One lesson within a track."""

    id: str
    title: str
    summary: str = ""
    intent: str = ""               # 何のための練習か(教師向けノート)
    rules: list[str] = Field(default_factory=list)
    rule_severity_overrides: dict[str, str] = Field(default_factory=dict)
    expected_parts: list[str] = Field(default_factory=list)  # 例: ["cantus_firmus", "counterpoint"]
    cantus_firmus_presets: list[str] = Field(default_factory=list)
    species_compat: int | None = None  # 既存の species ルーターと互換のある場合
    teacher_persona: str = ""           # Claude system prompt の概要
    output_instructions: str = ""       # Claude user prompt の指示部
    rule_card: list[dict[str, Any]] = Field(default_factory=list)  # UI に出す教科書ルール
    references: list[str] = Field(default_factory=list)  # 参考曲・教科書


class TrackDef(BaseModel):
    id: str
    title: str
    summary: str = ""
    lessons: list[LessonDef] = Field(default_factory=list)


class TrackRegistry(BaseModel):
    tracks: dict[str, TrackDef] = Field(default_factory=dict)

    def get_track(self, track_id: str) -> TrackDef | None:
        return self.tracks.get(track_id)

    def get_lesson(self, track_id: str, lesson_id: str) -> LessonDef | None:
        track = self.get_track(track_id)
        if track is None:
            return None
        for lesson in track.lessons:
            if lesson.id == lesson_id:
                return lesson
        return None


_LESSONS_DIR = Path(__file__).parent / "lessons"


def load_registry(lessons_dir: Path | None = None) -> TrackRegistry:
    """Load every yaml file under lessons/ into a single registry."""
    base = lessons_dir or _LESSONS_DIR
    registry = TrackRegistry()
    if not base.exists():
        return registry
    for yml in sorted(base.glob("*.yaml")):
        data = yaml.safe_load(yml.read_text())
        if not isinstance(data, dict):
            continue
        track = TrackDef.model_validate(data)
        registry.tracks[track.id] = track
    return registry


# Default singleton — services should call this once and reuse.
_REGISTRY: TrackRegistry | None = None


def get_registry() -> TrackRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = load_registry()
    return _REGISTRY
