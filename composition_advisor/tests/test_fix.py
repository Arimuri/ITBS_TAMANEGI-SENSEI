"""Tests for fix proposal + applier."""

from __future__ import annotations

import music21 as m21

from composition_advisor.critique.runner import run_all
from composition_advisor.fix.applier import apply_fixes_to_midi, write_diff_report
from composition_advisor.fix.rule_based import propose as propose_rule
from composition_advisor.io.normalize import normalize_score
from composition_advisor.model.issue import AnalysisResult


def _build_m21(parts: dict[str, list[str]]) -> m21.stream.Score:
    score = m21.stream.Score()
    for name, pitches in parts.items():
        p = m21.stream.Part()
        p.partName = name
        for pn in pitches:
            p.append(m21.note.Note(pn, quarterLength=4.0))
        score.insert(0, p)
    return score


def test_rule_based_fix_bass_below(tmp_path, slice_fn):
    m21_score = _build_m21({
        "bass": ["G3", "G3"],
        "piano": ["C2", "C2"],
    })
    internal = normalize_score(m21_score, key=m21.key.Key("C"))
    slices = slice_fn(internal)
    issues = run_all(internal, slices)
    result = AnalysisResult(metadata=internal.metadata, slices=slices, issues=issues)
    assert any(i.rule_id == "bass_below" for i in result.issues)

    fixes = propose_rule(internal, result)
    assert any(f.rule_id == "bass_below" and f.action == "transpose" for f in fixes)
    bass_fix = next(f for f in fixes if f.rule_id == "bass_below")
    assert bass_fix.new_pitch is not None
    # MIDI 36 (C2) lifted by an octave -> 48 (C3) at minimum.
    assert bass_fix.new_pitch >= 48


def test_apply_fixes_writes_files(tmp_path, slice_fn):
    m21_score = _build_m21({"trumpet": ["C2", "C2"]})  # below practical range
    internal = normalize_score(m21_score, key=m21.key.Key("C"))
    slices = slice_fn(internal)
    issues = run_all(internal, slices)
    result = AnalysisResult(metadata=internal.metadata, slices=slices, issues=issues)
    fixes = propose_rule(internal, result)
    assert fixes, "expected at least one range_check fix"

    written = apply_fixes_to_midi(m21_score, fixes, tmp_path)
    assert written, "no MIDI files written"
    for path in written:
        assert path.exists() and path.stat().st_size > 0

    report = tmp_path / "fixes.txt"
    write_diff_report(fixes, report)
    text = report.read_text()
    assert "range_check" in text
    assert "C1" in text  # C2 in scientific = C1 in Studio One


def test_apply_fixes_actually_transposes(tmp_path, slice_fn):
    """Verify the written MIDI's first note is transposed up an octave."""
    m21_score = _build_m21({"trumpet": ["C2"]})
    internal = normalize_score(m21_score, key=m21.key.Key("C"))
    slices = slice_fn(internal)
    issues = run_all(internal, slices)
    result = AnalysisResult(metadata=internal.metadata, slices=slices, issues=issues)
    fixes = propose_rule(internal, result)
    written = apply_fixes_to_midi(m21_score, fixes, tmp_path)
    assert len(written) == 1

    # Re-read and confirm pitch was lifted into the practical range.
    reloaded = m21.converter.parse(str(written[0]))
    notes = list(reloaded.flatten().notes)
    assert notes
    first_pitch = notes[0].pitch.midi
    assert first_pitch >= 54  # F#3 = trumpet practical low
