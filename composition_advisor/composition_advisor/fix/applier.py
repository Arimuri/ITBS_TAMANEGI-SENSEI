"""Apply a list of Fix objects to MIDI files and write fixed copies.

We rebuild the output MIDI from the original music21 Score so we keep
tempo, time-signature, and other meta information intact. Each Fix is
matched against music21 Note objects by (part, offset, pitch).
"""

from __future__ import annotations

import logging
from pathlib import Path

import music21 as m21

from ..model.fix import Fix
from ..model.score import Score, midi_to_studio_one

logger = logging.getLogger(__name__)

EPS = 0.05


def _fix_index(fixes: list[Fix]) -> dict[tuple[str, int, int], list[Fix]]:
    """Index fixes by (part, midi_pitch, integer_quarter_offset)."""
    idx: dict[tuple[str, int, int], list[Fix]] = {}
    for fx in fixes:
        key = (fx.target.part, fx.target.pitch, int(round(fx.target.start_beat * 4)))
        idx.setdefault(key, []).append(fx)
    return idx


def _match_fix(
    note: m21.note.Note,
    pitch_obj: m21.pitch.Pitch,
    part_name: str,
    abs_offset: float,
    fix_index: dict[tuple[str, int, int], list[Fix]],
) -> Fix | None:
    key = (part_name, int(pitch_obj.midi), int(round(abs_offset * 4)))
    candidates = fix_index.get(key, [])
    for fx in candidates:
        if abs(fx.target.start_beat - abs_offset) < EPS:
            return fx
    return None


def apply_fixes_to_midi(
    m21_score: m21.stream.Score,
    fixes: list[Fix],
    output_dir: Path,
    suffix: str = "_fixed",
) -> list[Path]:
    """Write one fixed .mid per Part. Returns the list of written paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    fix_idx = _fix_index(fixes)

    for m21_part in m21_score.parts:
        part_name = m21_part.partName or "part"
        new_part = m21.stream.Part()
        new_part.partName = part_name

        for elem in m21_part.flatten().notes:
            abs_offset = float(elem.offset)
            if isinstance(elem, m21.chord.Chord):
                # Build a fresh chord, applying any per-pitch transposes/deletes.
                new_pitches: list[m21.pitch.Pitch] = []
                for p in elem.pitches:
                    fx = _match_fix(elem, p, part_name, abs_offset, fix_idx)
                    if fx is None:
                        new_pitches.append(p)
                    elif fx.action == "delete":
                        continue
                    elif fx.action == "transpose" and fx.new_pitch is not None:
                        new_p = m21.pitch.Pitch(midi=fx.new_pitch)
                        new_pitches.append(new_p)
                    else:
                        new_pitches.append(p)
                if not new_pitches:
                    continue  # entire chord deleted
                new_elem = m21.chord.Chord(new_pitches, quarterLength=elem.duration.quarterLength)
                new_elem.offset = abs_offset
                new_part.insert(abs_offset, new_elem)
            else:  # Note
                fx = _match_fix(elem, elem.pitch, part_name, abs_offset, fix_idx)
                if fx is None:
                    new_note = m21.note.Note(elem.pitch.midi, quarterLength=elem.duration.quarterLength)
                elif fx.action == "delete":
                    continue
                elif fx.action == "transpose" and fx.new_pitch is not None:
                    new_note = m21.note.Note(fx.new_pitch, quarterLength=elem.duration.quarterLength)
                else:
                    new_note = m21.note.Note(elem.pitch.midi, quarterLength=elem.duration.quarterLength)
                new_part.insert(abs_offset, new_note)

        out_path = output_dir / f"{part_name}{suffix}.mid"
        new_part.write("midi", fp=out_path)
        written.append(out_path)
        logger.info("wrote fixed part: %s", out_path)
    return written


def write_diff_report(
    fixes: list[Fix], path: Path, internal_score: Score | None = None
) -> None:
    """Write a human-readable diff report listing every fix."""
    lines: list[str] = []
    lines.append(f"# Fix proposals ({len(fixes)})")
    lines.append("")
    for fx in fixes:
        target = fx.target
        if fx.action == "transpose" and fx.new_pitch is not None:
            change = f"{target.pitch_name} -> {midi_to_studio_one(fx.new_pitch)}"
        elif fx.action == "delete":
            change = f"{target.pitch_name} -> (deleted)"
        elif fx.action == "shorten" and fx.new_duration is not None:
            change = f"duration {target.duration:.2f} -> {fx.new_duration:.2f}"
        elif fx.action == "shift" and fx.new_start_beat is not None:
            change = f"start {target.start_beat:.2f} -> {fx.new_start_beat:.2f}"
        else:
            change = "(no-op)"
        lines.append(
            f"[{fx.source}] {fx.rule_id}  bar{target.bar} beat{target.beat_in_bar:.2f} "
            f"{target.part}: {change}"
        )
        if fx.rationale:
            lines.append(f"    {fx.rationale}")
        lines.append("")
    path.write_text("\n".join(lines))
    logger.info("wrote diff report: %s", path)
