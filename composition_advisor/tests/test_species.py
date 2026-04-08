"""Smoke tests for Species 1 counterpoint rules."""

from __future__ import annotations

from composition_advisor.critique.rules.species import (
    climax_range,
    dissonance,
    melodic_leap,
    start_end,
)
from composition_advisor.critique.species_runner import run_species
from composition_advisor.tutor.cantus_firmus import (
    PRESETS,
    get,
    studio_one_to_midi,
)


PARAMS = {"cantus_firmus_part": "cantus_firmus", "counterpoint_part": "counterpoint"}


def _build(make_note_fn, build_score_fn, cf: list[int], cp: list[int]):
    """Build a Score with two parts named cantus_firmus / counterpoint."""
    cf_notes = [
        make_note_fn(p, "cantus_firmus", start=i * 4.0, dur=4.0,
                    bar=i + 1, beat=1.0)
        for i, p in enumerate(cf)
    ]
    cp_notes = [
        make_note_fn(p, "counterpoint", start=i * 4.0, dur=4.0,
                    bar=i + 1, beat=1.0)
        for i, p in enumerate(cp)
    ]
    return build_score_fn({"cantus_firmus": cf_notes, "counterpoint": cp_notes})


# ----- start_end -----------------------------------------------------------

def test_start_end_perfect_passes_on_good_open_close(make_note_fn, build_score_fn, slice_fn):
    # Open on octave (C2->C3 = 12 semitones), close on unison (C2->C2 = 0).
    score = _build(make_note_fn, build_score_fn,
                   cf=[36, 38, 36], cp=[48, 47, 36])
    issues = start_end.check(score, slice_fn(score), params=PARAMS)
    assert issues == []


def test_start_end_perfect_flags_dissonant_close(make_note_fn, build_score_fn, slice_fn):
    score = _build(make_note_fn, build_score_fn,
                   cf=[36, 38, 36], cp=[48, 47, 38])  # ends on M2
    issues = start_end.check(score, slice_fn(score), params=PARAMS)
    assert any("closing" in i.context.get("position", "") for i in issues)


# ----- dissonance ----------------------------------------------------------

def test_dissonance_passes_consonant_pair(make_note_fn, build_score_fn, slice_fn):
    # C2 + E3 = M10 (16 semitones, mod 12 = M3) consonant
    score = _build(make_note_fn, build_score_fn, cf=[36], cp=[52])
    assert dissonance.check(score, slice_fn(score), params=PARAMS) == []


def test_dissonance_flags_minor_second(make_note_fn, build_score_fn, slice_fn):
    # C2 + Db2 = m2
    score = _build(make_note_fn, build_score_fn, cf=[36], cp=[37])
    issues = dissonance.check(score, slice_fn(score), params=PARAMS)
    assert len(issues) == 1
    assert issues[0].context["interval_semitones"] == 1


# ----- melodic_leap --------------------------------------------------------

def test_melodic_leap_flags_tritone(make_note_fn, build_score_fn, slice_fn):
    # F3 -> B3 = tritone in counterpoint
    score = _build(make_note_fn, build_score_fn,
                   cf=[36, 38], cp=[53, 59])
    issues = melodic_leap.check(score, slice_fn(score), params=PARAMS)
    assert any(i.context.get("kind") == "tritone" for i in issues)


def test_melodic_leap_flags_too_large(make_note_fn, build_score_fn, slice_fn):
    # 13 semitones leap = > octave
    score = _build(make_note_fn, build_score_fn,
                   cf=[36, 38], cp=[48, 61])
    issues = melodic_leap.check(score, slice_fn(score), params=PARAMS)
    assert any(i.context.get("kind") == "too_large" for i in issues)


# ----- climax_range --------------------------------------------------------

def test_climax_range_flags_repeated_pitch(make_note_fn, build_score_fn, slice_fn):
    score = _build(make_note_fn, build_score_fn,
                   cf=[36, 38, 36], cp=[48, 48, 36])  # C4 -> C4 immediate repeat
    issues = climax_range.check(score, slice_fn(score), params=PARAMS)
    assert any(i.context.get("kind") == "repeated_pitch" for i in issues)


def test_climax_range_flags_wide_span(make_note_fn, build_score_fn, slice_fn):
    score = _build(
        make_note_fn, build_score_fn,
        cf=[36, 38, 36],
        cp=[48, 65, 36],  # C4 -> F5 = 17 semitones, exceeds tenth (16)
    )
    issues = climax_range.check(score, slice_fn(score), params=PARAMS)
    assert any(i.context.get("kind") == "range_too_wide" for i in issues)


# ----- species_runner ------------------------------------------------------

def test_species_runner_smoke(make_note_fn, build_score_fn, slice_fn):
    # Deliberately bad: parallel fifths C2-G2 -> D2-A2
    score = _build(make_note_fn, build_score_fn,
                   cf=[36, 38, 36], cp=[43, 45, 36])
    issues = run_species(score, slice_fn(score), species=1, params=PARAMS)
    assert any(i.rule_id == "parallel_motion" for i in issues)


# ----- cantus firmus presets ----------------------------------------------

def test_cantus_firmus_presets_loadable():
    assert "fux_d_dorian" in PRESETS
    cf = get("fux_d_dorian")
    assert cf.notes
    assert cf.key == "D dorian"


def test_studio_one_to_midi_round_trip():
    # Studio One: middle C = C3 = MIDI 60.
    # B2 sits a semitone below C3 (= MIDI 59), so Bb2 = 58.
    assert studio_one_to_midi("C3") == 60
    assert studio_one_to_midi("F#3") == 66
    assert studio_one_to_midi("B2") == 59
    assert studio_one_to_midi("Bb2") == 58
    assert studio_one_to_midi("C2") == 48
