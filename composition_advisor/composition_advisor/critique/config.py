"""Genre / rule configuration loaded from a yaml file.

Format:

    genre: jazz
    key: C
    rules:
      semitone_clash:
        enabled: true
        severity: warning
      parallel_motion:
        enabled: false
      chord_tone_check:
        enabled: true
        severity: info

Per-rule fields:
    enabled  (bool, default true)   — skip the rule entirely if false
    severity (str, optional)        — override every Issue's severity

Anything else under a rule key is passed through as the `params` dict so
individual rules can read genre-specific knobs without needing to extend
this loader.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RuleConfig:
    enabled: bool = True
    severity: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class CritiqueConfig:
    genre: str | None = None
    key: str | None = None
    rules: dict[str, RuleConfig] = field(default_factory=dict)

    def for_rule(self, rule_id: str) -> RuleConfig:
        """Return the per-rule config, falling back to defaults."""
        return self.rules.get(rule_id, RuleConfig())


def load_config(path: str | Path) -> CritiqueConfig:
    """Load a yaml config file into a CritiqueConfig."""
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Config root must be a mapping: {path}")

    rules: dict[str, RuleConfig] = {}
    for name, body in (raw.get("rules") or {}).items():
        body = dict(body or {})
        rules[name] = RuleConfig(
            enabled=body.pop("enabled", True),
            severity=body.pop("severity", None),
            params=body,
        )
    return CritiqueConfig(
        genre=raw.get("genre"),
        key=raw.get("key"),
        rules=rules,
    )


DEFAULT_CONFIG = CritiqueConfig()
