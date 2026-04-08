"""Smoke tests for Species 1 counterpoint rules."""

from __future__ import annotations

from composition_advisor.critique.rules.species import (
    climax_range,
    dissonance,
    melodic_leap,
    species2,
    species3,
    species4,
    species5,
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


# ----- species 2 (2:1) -----------------------------------------------------

def _build_two_voice(make_note_fn, build_score_fn, cf, cp_pairs):
    """Build CF + CP where CP has 2 notes per CF note (species 2)."""
    cf_notes = [
        make_note_fn(p, "cantus_firmus", start=i * 4.0, dur=4.0,
                    bar=i + 1, beat=1.0)
        for i, p in enumerate(cf)
    ]
    cp_notes = []
    for i, (a, b) in enumerate(cp_pairs):
        cp_notes.append(make_note_fn(a, "counterpoint", start=i * 4.0, dur=2.0,
                                     bar=i + 1, beat=1.0))
        cp_notes.append(make_note_fn(b, "counterpoint", start=i * 4.0 + 2.0, dur=2.0,
                                     bar=i + 1, beat=3.0))
    return build_score_fn({"cantus_firmus": cf_notes, "counterpoint": cp_notes})


def test_species2_passes_passing_tone(make_note_fn, build_score_fn, slice_fn):
    # cf: C2 D2 E2  (36 38 40)
    # cp downbeats are consonant; upbeats are stepwise passing tones.
    #   bar1 downbeat: G3 (43, P5 above C2)  upbeat: A3 (45)
    #   bar2 downbeat: B3 (47, M6 above D2)  upbeat: A3 (45)
    #   bar3 downbeat: G3 (43, m3 above E2)  upbeat: G3 (43, repeat is fine harmonically)
    # bar1 upbeat A3 over C2 = M6 (consonant), so no dissonance at all here.
    score = _build_two_voice(
        make_note_fn, build_score_fn,
        cf=[36, 38, 40],
        cp_pairs=[(43, 45), (47, 45), (43, 43)],
    )
    issues = species2.check(score, slice_fn(score), params=PARAMS)
    bad = [i for i in issues if i.context.get("position") == "upbeat"]
    assert bad == []


def test_species2_flags_unprepared_dissonant_upbeat(make_note_fn, build_score_fn, slice_fn):
    # CP upbeat is dissonant AND not stepwise -> should flag
    score = _build_two_voice(
        make_note_fn, build_score_fn,
        cf=[36, 38],
        cp_pairs=[(48, 41), (50, 50)],
    )
    issues = species2.check(score, slice_fn(score), params=PARAMS)
    assert any(i.rule_id == "species2_upbeat_dissonance" for i in issues)


def test_species2_flags_downbeat_dissonance(make_note_fn, build_score_fn, slice_fn):
    score = _build_two_voice(
        make_note_fn, build_score_fn,
        cf=[36, 38],
        cp_pairs=[(37, 50), (50, 50)],   # m2 on downbeat
    )
    issues = species2.check(score, slice_fn(score), params=PARAMS)
    assert any(i.rule_id == "species2_downbeat_dissonance" for i in issues)


# ----- species 3 (4:1) -----------------------------------------------------

def _build_four_voice(make_note_fn, build_score_fn, cf, cp_quads):
    cf_notes = [
        make_note_fn(p, "cantus_firmus", start=i * 4.0, dur=4.0,
                    bar=i + 1, beat=1.0)
        for i, p in enumerate(cf)
    ]
    cp_notes = []
    for i, quad in enumerate(cp_quads):
        for j, p in enumerate(quad):
            cp_notes.append(make_note_fn(
                p, "counterpoint",
                start=i * 4.0 + j * 1.0, dur=1.0,
                bar=i + 1, beat=1.0 + j,
            ))
    return build_score_fn({"cantus_firmus": cf_notes, "counterpoint": cp_notes})


def test_species3_flags_downbeat_dissonance(make_note_fn, build_score_fn, slice_fn):
    score = _build_four_voice(
        make_note_fn, build_score_fn,
        cf=[36, 38],
        cp_quads=[(37, 48, 47, 48), (50, 50, 50, 50)],   # downbeat m2
    )
    issues = species3.check(score, slice_fn(score), params=PARAMS)
    assert any(i.rule_id == "species3_downbeat_dissonance" for i in issues)


def test_species3_allows_passing_tone_on_weak_beat(make_note_fn, build_score_fn, slice_fn):
    # cf bar1 C2 (36); bar2 D2 (38).
    # cp bar1: C3(48) D3(50, dissonant 14st = M2) E3(52) D3(50) — 50 on beat2 is a
    #          stepwise passing tone (48->50->52).
    # cp bar2: F3(53, M3 over D) G3(55) F3(53) E3(52) — all consonant or stepwise.
    score = _build_four_voice(
        make_note_fn, build_score_fn,
        cf=[36, 38],
        cp_quads=[(48, 50, 52, 50), (53, 55, 53, 52)],
    )
    issues = species3.check(score, slice_fn(score), params=PARAMS)
    weak_issues = [
        i for i in issues
        if i.rule_id == "species3_weak_beat_dissonance" and i.context["position"] == 2
    ]
    assert weak_issues == []


# ----- species 4 (suspension) ---------------------------------------------

def test_species4_detects_unresolved_suspension(make_note_fn, build_score_fn, slice_fn):
    # cf bar1 D2(38), bar2 E2(40)
    # cp bar1 first half = A3(57)  — P5 above D, prepared as a consonance.
    # cp tied note 2..6 = A3(57)   — clashes 4th above E (5 semitones)? actually
    #     A3 over E2 is a 6th (15st = m7? let's compute precisely):
    #     A3 = MIDI 57, E2 = MIDI 40 -> 17 semitones -> mod12 = 5 = P4 -> dissonant ✓
    # cp resolves UP to B3 (59) instead of down — should be flagged unresolved.
    cf_notes = [
        make_note_fn(38, "cantus_firmus", start=0.0, dur=4.0, bar=1, beat=1.0),
        make_note_fn(40, "cantus_firmus", start=4.0, dur=4.0, bar=2, beat=1.0),
    ]
    cp_notes = [
        make_note_fn(57, "counterpoint", start=0.0, dur=2.0, bar=1, beat=1.0),
        make_note_fn(57, "counterpoint", start=2.0, dur=4.0, bar=1, beat=3.0),  # tied
        make_note_fn(59, "counterpoint", start=6.0, dur=2.0, bar=2, beat=3.0),  # jumps up
    ]
    score = build_score_fn({"cantus_firmus": cf_notes, "counterpoint": cp_notes})
    issues = species4.check(score, slice_fn(score), params=PARAMS)
    assert any(i.rule_id == "species4_unresolved_suspension" for i in issues)


def test_species4_clean_suspension_passes(make_note_fn, build_score_fn, slice_fn):
    # Properly prepared 7-6 suspension over E.
    cf_notes = [
        make_note_fn(38, "cantus_firmus", start=0.0, dur=4.0, bar=1, beat=1.0),
        make_note_fn(40, "cantus_firmus", start=4.0, dur=4.0, bar=2, beat=1.0),
    ]
    cp_notes = [
        make_note_fn(57, "counterpoint", start=0.0, dur=2.0, bar=1, beat=1.0),  # A3 (5 over D)
        make_note_fn(59, "counterpoint", start=2.0, dur=4.0, bar=1, beat=3.0),  # B3 tied (clashes 7 over E)
        make_note_fn(57, "counterpoint", start=6.0, dur=2.0, bar=2, beat=3.0),  # A3 (resolution down)
    ]
    score = build_score_fn({"cantus_firmus": cf_notes, "counterpoint": cp_notes})
    issues = species4.check(score, slice_fn(score), params=PARAMS)
    assert all(i.rule_id != "species4_unresolved_suspension" for i in issues)


# ----- species 5 (florid) -------------------------------------------------

def test_species5_flags_repeated_rhythm(make_note_fn, build_score_fn, slice_fn):
    # All quarter notes -> 4-in-a-row rhythm streak
    cf_notes = [
        make_note_fn(36, "cantus_firmus", start=0.0, dur=4.0, bar=1, beat=1.0),
    ]
    cp_notes = [
        make_note_fn(48 + i, "counterpoint", start=i * 1.0, dur=1.0, bar=1, beat=1.0 + i)
        for i in range(4)
    ]
    score = build_score_fn({"cantus_firmus": cf_notes, "counterpoint": cp_notes})
    issues = species5.check(score, slice_fn(score), params=PARAMS)
    assert any(i.rule_id == "species5_repeated_rhythm" for i in issues)


def test_species5_flags_no_long_note(make_note_fn, build_score_fn, slice_fn):
    cf_notes = [
        make_note_fn(36, "cantus_firmus", start=0.0, dur=4.0, bar=1, beat=1.0),
    ]
    # Three eighth-notes — never longer than 0.5 beats
    cp_notes = [
        make_note_fn(48, "counterpoint", start=0.0, dur=0.5, bar=1, beat=1.0),
        make_note_fn(50, "counterpoint", start=0.5, dur=0.5, bar=1, beat=1.5),
        make_note_fn(52, "counterpoint", start=1.0, dur=0.5, bar=1, beat=2.0),
    ]
    score = build_score_fn({"cantus_firmus": cf_notes, "counterpoint": cp_notes})
    issues = species5.check(score, slice_fn(score), params=PARAMS)
    assert any(i.rule_id == "species5_no_long_note" for i in issues)


# ----- runner dispatches per species -------------------------------------

def test_species_runner_dispatches_species2(make_note_fn, build_score_fn, slice_fn):
    score = _build_two_voice(
        make_note_fn, build_score_fn,
        cf=[36, 38],
        cp_pairs=[(37, 50), (50, 50)],
    )
    issues = run_species(score, slice_fn(score), species=2, params=PARAMS)
    assert any(i.rule_id == "species2_downbeat_dissonance" for i in issues)


def test_studio_one_to_midi_round_trip():
    # Studio One: middle C = C3 = MIDI 60.
    # B2 sits a semitone below C3 (= MIDI 59), so Bb2 = 58.
    assert studio_one_to_midi("C3") == 60
    assert studio_one_to_midi("F#3") == 66
    assert studio_one_to_midi("B2") == 59
    assert studio_one_to_midi("Bb2") == 58
    assert studio_one_to_midi("C2") == 48
