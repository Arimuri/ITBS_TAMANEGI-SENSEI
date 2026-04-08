"""Rule-based fix proposal generator.

For each Issue we know how to handle deterministically, emit one Fix.
Issues whose musical resolution requires judgement (semitone_clash on a
voicing, chord_tone_check on a melody line) are skipped here — let the LLM
fixer handle them.

Heuristics
----------
- range_check:  transpose the offending note up/down by octaves until it
  fits inside the part's practical range.
- bass_below:   move the offender up by an octave (often enough to clear
  the bass) — repeat in caller if still below after applying.
- voice_crossing: move the lower voice's second note down by an octave so
  the upper voice stays on top. Conservative — may not always be musical.
"""

from __future__ import annotations

import logging

from ..critique.rules.range_check import INSTRUMENT_RANGES
from ..model.fix import Fix
from ..model.issue import AnalysisResult
from ..model.score import Score, midi_to_studio_one

logger = logging.getLogger(__name__)


def _range_for(part_name: str) -> tuple[int, int] | None:
    name = part_name.lower()
    for key, rng in INSTRUMENT_RANGES.items():
        if key in name:
            return rng
    return None


def propose(score: Score, result: AnalysisResult) -> list[Fix]:
    """Generate one Fix per resolvable Issue. Returns a flat list."""
    fixes: list[Fix] = []
    for idx, issue in enumerate(result.issues):
        if issue.rule_id == "range_check":
            fixes.extend(_fix_range(idx, issue))
        elif issue.rule_id == "bass_below":
            fixes.extend(_fix_bass_below(idx, issue))
        elif issue.rule_id == "voice_crossing":
            fixes.extend(_fix_voice_crossing(idx, issue))
        # semitone_clash, parallel_motion, chord_tone_check left to LLM
    return fixes


def _fix_range(idx: int, issue) -> list[Fix]:
    if not issue.affected_notes:
        return []
    note = issue.affected_notes[0]
    rng = _range_for(note.part)
    if rng is None:
        return []
    low, high = rng
    new_pitch = note.pitch
    # Octave-shift toward the range.
    while new_pitch < low:
        new_pitch += 12
    while new_pitch > high:
        new_pitch -= 12
    if new_pitch == note.pitch or not (low <= new_pitch <= high):
        return []
    direction = "up" if new_pitch > note.pitch else "down"
    return [
        Fix(
            rule_id=issue.rule_id,
            issue_index=idx,
            action="transpose",
            target=note,
            new_pitch=new_pitch,
            new_pitch_name=midi_to_studio_one(new_pitch),
            rationale=(
                f"Transpose {note.pitch_name} {direction} an octave to fit "
                f"{note.part}'s practical range ({midi_to_studio_one(low)}-"
                f"{midi_to_studio_one(high)})."
            ),
        )
    ]


def _fix_bass_below(idx: int, issue) -> list[Fix]:
    """Move the offending non-bass note up an octave."""
    if not issue.affected_notes:
        return []
    # affected_notes order: [offender, bass_low_note]
    offender = issue.affected_notes[0]
    bass_low = issue.affected_notes[1] if len(issue.affected_notes) > 1 else None
    new_pitch = offender.pitch
    # Lift octaves until we're above the bass low note (if known).
    target_floor = bass_low.pitch + 1 if bass_low else offender.pitch + 12
    while new_pitch < target_floor:
        new_pitch += 12
    if new_pitch == offender.pitch:
        return []
    return [
        Fix(
            rule_id=issue.rule_id,
            issue_index=idx,
            action="transpose",
            target=offender,
            new_pitch=new_pitch,
            new_pitch_name=midi_to_studio_one(new_pitch),
            rationale=(
                f"Move {offender.part} {offender.pitch_name} up an octave to "
                f"{midi_to_studio_one(new_pitch)} so it sits above the bass."
            ),
        )
    ]


def _fix_voice_crossing(idx: int, issue) -> list[Fix]:
    """Push the lower voice's *second* note down an octave to undo the cross."""
    # affected_notes layout (from voice_crossing rule): [n1u, n2u, n1l, n2l]
    if len(issue.affected_notes) < 4:
        return []
    n2l = issue.affected_notes[3]
    new_pitch = n2l.pitch - 12
    if new_pitch < 0:
        return []
    return [
        Fix(
            rule_id=issue.rule_id,
            issue_index=idx,
            action="transpose",
            target=n2l,
            new_pitch=new_pitch,
            new_pitch_name=midi_to_studio_one(new_pitch),
            rationale=(
                f"Drop {n2l.part} {n2l.pitch_name} an octave to "
                f"{midi_to_studio_one(new_pitch)} so the upper voice stays on top."
            ),
        )
    ]
