"""Smoke tests for each critique rule."""

from __future__ import annotations

import pytest

from composition_advisor.cli import _parse_bar_range
from composition_advisor.critique.config import CritiqueConfig, RuleConfig
from composition_advisor.critique.rules import (
    bass_below,
    chord_tone_check,
    parallel_motion,
    range_check,
    semitone_clash,
    voice_crossing,
)
from composition_advisor.critique.runner import run_all


# ----- semitone_clash -----------------------------------------------------

def test_semitone_clash_detects_minor_second(make_note_fn, build_score_fn, slice_fn):
    # Treble E5 (76), lower F5 (77) — 1 semitone apart, different parts.
    score = build_score_fn({
        "treble": [make_note_fn(76, "treble", start=0.0)],
        "lower": [make_note_fn(77, "lower", start=0.0)],
    })
    issues = semitone_clash.check(score, slice_fn(score))
    assert len(issues) == 1
    assert issues[0].rule_id == "semitone_clash"
    assert sorted(issues[0].affected_parts) == ["lower", "treble"]


def test_semitone_clash_ignores_same_part(make_note_fn, build_score_fn, slice_fn):
    score = build_score_fn({
        "melody": [
            make_note_fn(76, "melody", start=0.0),
            make_note_fn(77, "melody", start=0.0),  # rare, but treat as one part
        ],
    })
    assert semitone_clash.check(score, slice_fn(score)) == []


def test_semitone_clash_ignores_consonant_intervals(make_note_fn, build_score_fn, slice_fn):
    # Perfect fifth — 7 semitones, should not fire.
    score = build_score_fn({
        "treble": [make_note_fn(72, "treble", start=0.0)],
        "lower": [make_note_fn(67, "lower", start=0.0)],
    })
    assert semitone_clash.check(score, slice_fn(score)) == []


# ----- voice_crossing -----------------------------------------------------

def test_voice_crossing(make_note_fn, build_score_fn, slice_fn):
    # bar1: treble D5(74) above lower G4(67)
    # bar2: treble C5(72) below lower A5(81) — crossed
    score = build_score_fn({
        "treble": [
            make_note_fn(74, "treble", start=0.0),
            make_note_fn(72, "treble", start=4.0, bar=2),
        ],
        "lower": [
            make_note_fn(67, "lower", start=0.0),
            make_note_fn(81, "lower", start=4.0, bar=2),
        ],
    })
    issues = voice_crossing.check(score, slice_fn(score))
    assert any(i.rule_id == "voice_crossing" for i in issues)


# ----- bass_below ---------------------------------------------------------

def test_bass_below(make_note_fn, build_score_fn, slice_fn):
    # bass plays G2 (43); piano (treble part) plays C2 (36) below — wrong.
    score = build_score_fn({
        "piano": [make_note_fn(36, "piano", start=0.0)],
        "bass": [make_note_fn(43, "bass", start=0.0)],
    })
    issues = bass_below.check(score, slice_fn(score))
    assert len(issues) == 1
    assert "piano" in issues[0].affected_parts


def test_bass_below_no_bass_part(make_note_fn, build_score_fn, slice_fn):
    # No part named "bass" -> rule must stay silent.
    score = build_score_fn({
        "lead": [make_note_fn(36, "lead", start=0.0)],
        "pad": [make_note_fn(72, "pad", start=0.0)],
    })
    assert bass_below.check(score, slice_fn(score)) == []


# ----- parallel_motion ----------------------------------------------------

def test_parallel_fifth(make_note_fn, build_score_fn, slice_fn):
    # treble: C5(72)->D5(74), lower: F4(65)->G4(67)
    # both moves up a whole step; both intervals = perfect 5th (7 semitones).
    score = build_score_fn({
        "treble": [
            make_note_fn(72, "treble", start=0.0),
            make_note_fn(74, "treble", start=4.0, bar=2),
        ],
        "lower": [
            make_note_fn(65, "lower", start=0.0),
            make_note_fn(67, "lower", start=4.0, bar=2),
        ],
    })
    issues = parallel_motion.check(score, slice_fn(score))
    assert any(i.context.get("kind") == "fifth" for i in issues)


# ----- range_check --------------------------------------------------------

def test_range_check_trumpet_too_low(make_note_fn, build_score_fn, slice_fn):
    # trumpet practical low is MIDI 54 (F#3); MIDI 36 is way below.
    score = build_score_fn({
        "trumpet": [make_note_fn(36, "trumpet", start=0.0)],
    })
    issues = range_check.check(score, slice_fn(score))
    assert len(issues) >= 1
    assert any(i.rule_id == "range_check" for i in issues)


# ----- runner + config ----------------------------------------------------

def test_runner_respects_disabled_rule(make_note_fn, build_score_fn, slice_fn):
    score = build_score_fn({
        "treble": [
            make_note_fn(72, "treble", start=0.0),
            make_note_fn(74, "treble", start=4.0, bar=2),
        ],
        "lower": [
            make_note_fn(65, "lower", start=0.0),
            make_note_fn(67, "lower", start=4.0, bar=2),
        ],
    })
    slices = slice_fn(score)
    cfg = CritiqueConfig(rules={"parallel_motion": RuleConfig(enabled=False)})
    issues = run_all(score, slices, config=cfg)
    assert not any(i.rule_id == "parallel_motion" for i in issues)


# ----- chord_tone_check ---------------------------------------------------

def test_chord_tone_check_classifies_diatonic_vs_chromatic(make_note_fn, build_score_fn, slice_fn):
    # Slice plays a C major triad (C/E/G) plus a melody note in the upper part.
    # We test two melody pitches in two different scores:
    #   D5 (74) — diatonic in C major, not in C triad → diatonic_tension/info
    #   Eb5 (75) — chromatic in C major, not in C triad → chromatic/warning
    diatonic_score = build_score_fn({
        "chord": [
            make_note_fn(60, "chord", start=0.0),  # C4
            make_note_fn(64, "chord", start=0.0),  # E4
            make_note_fn(67, "chord", start=0.0),  # G4
        ],
        "melody": [make_note_fn(74, "melody", start=0.0)],  # D5 (diatonic)
    })
    issues = chord_tone_check.check(diatonic_score, slice_fn(diatonic_score))
    assert len(issues) == 1
    assert issues[0].context["kind"] == "diatonic_tension"
    assert issues[0].severity == "info"

    chromatic_score = build_score_fn({
        "chord": [
            make_note_fn(60, "chord", start=0.0),
            make_note_fn(64, "chord", start=0.0),
            make_note_fn(67, "chord", start=0.0),
        ],
        "melody": [make_note_fn(75, "melody", start=0.0)],  # Eb5 (chromatic)
    })
    issues = chord_tone_check.check(chromatic_score, slice_fn(chromatic_score))
    assert len(issues) == 1
    assert issues[0].context["kind"] == "chromatic"
    assert issues[0].severity == "warning"


def test_chord_tone_check_skips_short_passing_notes(make_note_fn, build_score_fn, slice_fn):
    # Eighth-note passing tone (0.5 beats) — should be skipped at the
    # default ignore_durations_below=0.25 threshold? No: 0.5 > 0.25 → flagged.
    # Sixteenth note (0.125 beats) — should be skipped.
    score = build_score_fn({
        "chord": [
            make_note_fn(60, "chord", start=0.0, dur=4.0),
            make_note_fn(64, "chord", start=0.0, dur=4.0),
            make_note_fn(67, "chord", start=0.0, dur=4.0),
        ],
        "melody": [make_note_fn(75, "melody", start=0.0, dur=0.125)],  # Eb 16th
    })
    issues = chord_tone_check.check(score, slice_fn(score))
    assert issues == []


# ----- semitone_clash duration filter -------------------------------------

def test_semitone_clash_ignores_short_overlap(make_note_fn, build_score_fn, slice_fn):
    # Two notes only overlap for 0.05 beats (quantize jitter).
    score = build_score_fn({
        "treble": [make_note_fn(76, "treble", start=0.0, dur=1.0)],
        "lower": [make_note_fn(77, "lower", start=0.95, dur=1.0)],
    })
    slices = slice_fn(score)
    # Without filter: should fire on the brief overlap.
    assert any(
        i.rule_id == "semitone_clash"
        for i in semitone_clash.check(score, slices)
    )
    # With a 0.1-beat threshold: should be silent.
    issues = semitone_clash.check(score, slices, params={"ignore_durations_below": 0.1})
    assert issues == []


def test_runner_severity_override(make_note_fn, build_score_fn, slice_fn):
    score = build_score_fn({
        "treble": [make_note_fn(76, "treble", start=0.0)],
        "lower": [make_note_fn(77, "lower", start=0.0)],
    })
    slices = slice_fn(score)
    cfg = CritiqueConfig(rules={"semitone_clash": RuleConfig(severity="info")})
    issues = run_all(score, slices, config=cfg)
    clash_issues = [i for i in issues if i.rule_id == "semitone_clash"]
    assert clash_issues
    assert all(i.severity == "info" for i in clash_issues)


# ----- CLI bar range parser -----------------------------------------------

@pytest.mark.parametrize(
    "spec,expected",
    [
        ("4-8", (4, 8)),
        ("4", (4, 4)),
        ("4-", (4, 10**9)),
        ("-8", (1, 8)),
        ("  3-5 ", (3, 5)),
    ],
)
def test_parse_bar_range(spec, expected):
    assert _parse_bar_range(spec) == expected


def test_parse_bar_range_rejects_inverted():
    with pytest.raises(ValueError):
        _parse_bar_range("8-4")
