"""Species 5 (florid counterpoint) rules.

Fifth species combines the previous four. There are very few species-5
specific prohibitions; the main job is to reuse Species 1-4 voice-leading
checks while adding a few stylistic flags:

    species5_repeated_rhythm  — three or more identical durations in a row
                                (the line should not get monotonous).
    species5_no_long_note     — there should be at least one held note
                                (otherwise the line is just species 3).

Most of the heavy lifting (parallel/hidden motion, melodic leaps,
suspensions, dissonance treatment) is done by reusing the existing rule
modules from species_runner.
"""

from __future__ import annotations

from typing import Any

from ....model.issue import Issue
from ....model.score import Score
from ....model.slice import Slice
from ._helpers import cf_and_cp

RHYTHM_RULE_ID = "species5_repeated_rhythm"
NO_LONG_NOTE_RULE_ID = "species5_no_long_note"


def check(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    parts = cf_and_cp(score, params)
    if parts is None:
        return []
    _cf, cp = parts
    notes = sorted(cp.notes, key=lambda n: n.start_beat)
    if len(notes) < 3:
        return []

    issues: list[Issue] = []

    def _flush_streak(streak: int, end_idx: int) -> None:
        if streak < 4:
            return
        anchor = notes[end_idx]
        issues.append(
            Issue(
                bar=anchor.bar,
                beat_in_bar=anchor.beat_in_bar,
                severity="info",
                rule_id=RHYTHM_RULE_ID,
                description=(
                    f"Four or more notes in a row share the same rhythmic value "
                    f"({durations[end_idx]:.2f}). Florid counterpoint should mix "
                    f"durations to keep the line shapely."
                ),
                affected_notes=[anchor],
                affected_parts=[cp.name],
                context={"streak": streak, "duration": durations[end_idx]},
            )
        )

    durations = [round(n.duration, 3) for n in notes]
    streak = 1
    for i in range(1, len(durations)):
        if durations[i] == durations[i - 1]:
            streak += 1
        else:
            _flush_streak(streak, i - 1)
            streak = 1
    _flush_streak(streak, len(durations) - 1)

    longest = max(durations)
    if longest < 2.0:
        # never holds anything longer than a half-note in a typical 4/4
        anchor = notes[0]
        issues.append(
            Issue(
                bar=anchor.bar,
                beat_in_bar=anchor.beat_in_bar,
                severity="info",
                rule_id=NO_LONG_NOTE_RULE_ID,
                description=(
                    f"Counterpoint never sustains a note longer than {longest:.2f} beats. "
                    f"Fifth species typically incorporates at least one held note or "
                    f"suspension to vary the texture."
                ),
                affected_notes=[anchor],
                affected_parts=[cp.name],
                context={"longest_duration": longest},
            )
        )

    return issues
