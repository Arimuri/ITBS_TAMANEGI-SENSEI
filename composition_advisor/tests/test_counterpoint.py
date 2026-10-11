"""Theory cases, stable IDs, input integrity and hidden exercise witnesses."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from composition_advisor.counterpoint import get_exercise, grade, list_exercises, profile
from composition_advisor.counterpoint.exercises import make_notes, reference_submission
from composition_advisor.counterpoint.grading import Findings, assess_music
from composition_advisor.counterpoint.models import Note, SpelledPitch, between, consonant, pitch_from_name


def assess(cf, cp, position="above", key="C", missing=()):
    """Small theory fragments independent of the fixed exercise bank."""
    ex = get_exercise("species1-c-above")
    ex.update(id="case", position=position, keySignature=key, tonic=key,
              cantus=make_notes("case", cf.split(), "cf"), range={"min": 24, "max": 108})
    alters = {"G": {"F": 1}, "F": {"B": -1}}.get(key, {})
    ex["allowedPitches"] = [{"step": s, "alter": alters.get(s, 0), "octave": 4} for s in "CDEFGAB"]
    notes = {i: Note.model_validate(n) for i, n in enumerate(make_notes("case", cp.split())) if i not in missing}
    findings = Findings()
    assess_music(ex, notes, findings)
    return findings.result("case", "complete" if not missing else "incomplete")


def rule(result, name):
    return [i for i in result["issues"] if i["ruleId"] == name]


@pytest.mark.parametrize("ex", list_exercises(), ids=lambda e: e["id"])
def test_original_exercises_have_clean_complete_private_witnesses(ex):
    assert 8 <= len(ex["cantus"]) <= 12
    result = grade(reference_submission(ex["id"]))
    assert result["assessmentStatus"] == "complete"
    assert result["passed"] and result["hardViolationCount"] == result["warningCount"] == 0
    assert not result["issues"]
    assert {"solution", "answer", "reference", "notes"}.isdisjoint(ex)


@pytest.mark.parametrize("identifier,expected", [
    ("species1-c-above", ["P8", "M6", "M6", "m6", "M3", "M3", "M6", "P8"]),
    ("species1-g-above", ["P5", "m3", "M3", "P5", "m3", "P5", "m6", "M3", "M6", "P8"]),
    ("species1-f-below", ["P1", "M6", "M6", "m10", "m10", "M6", "M6", "P8"]),
])
def test_reference_harmonies_match_independent_written_audit(identifier, expected):
    """Expected intervals are manually derived, also recorded in theory docs."""
    payload = reference_submission(identifier)
    names = [between(Note.model_validate(a).pitch, Note.model_validate(b).pitch).name
             for a, b in zip(payload["cantus"], payload["notes"])]
    assert names == expected


@pytest.mark.parametrize("ex", list_exercises(), ids=lambda e: e["id"])
def test_original_cantus_has_bounded_singable_shape_and_tonic_cadence(ex):
    pitches = [Note.model_validate(n).pitch for n in ex["cantus"]]
    assert pitches[0].step == pitches[-1].step == ex["tonic"]
    assert between(pitches[-2], pitches[-1]).name in {"m2", "M2"}
    assert all(between(a, b).name in {"m2", "M2", "m3", "M3", "P4", "P5"}
               for a, b in zip(pitches, pitches[1:]))
    low, high = min(pitches, key=lambda p: p.midi), max(pitches, key=lambda p: p.midi)
    assert between(low, high).generic.undirected <= 10
    assert sum(p.midi == high.midi for p in pitches) == 1


def test_public_catalog_is_isolated_and_contains_both_positions():
    catalog = list_exercises()
    assert {x["position"] for x in catalog} == {"above", "below"}
    catalog[0]["cantus"][0]["pitch"]["step"] = "A"
    assert get_exercise(catalog[0]["id"])["cantus"][0]["pitch"]["step"] == "C"
    p = profile()
    p["rules"].clear()
    assert profile()["rules"]


def test_pitch60_is_scientific_c4_without_octave_or_midi_duplicate():
    c = pitch_from_name("C4")
    assert c.midi == 60 and c.label == "C4"
    assert c.model_dump() == {"step": "C", "alter": 0, "octave": 4}
    with pytest.raises(ValidationError):
        SpelledPitch(step="C", alter=0, octave=4, midi=48)


@pytest.mark.parametrize("fields", [
    {"step": "C", "alter": -1, "octave": -1},
    {"step": "G", "alter": 1, "octave": 9},
    {"step": "C", "alter": 0, "octave": 10},
])
def test_outside_midi_bounds_rejected_without_octave_folding(fields):
    with pytest.raises(ValidationError):
        SpelledPitch(**fields)


@pytest.mark.parametrize("left,right,expected", [
    ("C4", "E4", True), ("C4", "F-4", False),  # same 64 MIDI, different spelling
    ("C4", "G4", True), ("C4", "F##4", False),
    ("C4", "E5", True), ("C4", "G5", True), ("C4", "C6", True),
    ("C4", "F4", False), ("C4", "B4", False), ("B3", "F4", False),
])
def test_spelling_and_compound_vertical_intervals(left, right, expected):
    # Double-sharps are outside input vocabulary: test through music21 only
    # by using an equivalent singly altered augmented-sixth case below.
    if right == "F##4":
        with pytest.raises(ValidationError):
            pitch_from_name(right)
        return
    assert consonant(pitch_from_name(left), pitch_from_name(right)) is expected


@pytest.mark.parametrize("cf,cp,kind", [
    ("C3 D3", "G3 A3", "parallel_fifth"),
    ("C3 D3", "G4 A4", "parallel_fifth"),
    ("C3 D3", "C4 D4", "parallel_octave"),
    ("C3 D3", "C5 D5", "parallel_octave"),
    ("C3 D3", "C3 D3", "parallel_octave"),
    ("C3 D3", "G3 A4", "parallel_fifth"),
])
def test_parallel_perfect_families_include_compounds(cf, cp, kind):
    result = assess(cf, cp)
    assert len(rule(result, kind)) == 1
    issue = rule(result, kind)[0]
    assert issue["noteIds"] == ["case-cf-0", "case-cp-0", "case-cf-1", "case-cp-1"]
    assert issue["locations"] == [{"measure": 1, "beat": 1}, {"measure": 2, "beat": 1}]
    assert not rule(result, "direct_perfect") and not rule(result, "direct_step_perfect")


@pytest.mark.parametrize("cf,cp", [("C3 C3", "G3 G3"), ("C3 D3", "G3 G3"), ("C3 G3", "G4 D4")])
def test_static_oblique_and_contrary_are_not_mislabeled_parallel(cf, cp):
    result = assess(cf, cp)
    assert not rule(result, "parallel_fifth") and not rule(result, "parallel_octave")


def test_contrary_same_perfect_family_is_separate_warning():
    result = assess("C3 G3", "G4 D4")
    issue, = rule(result, "contrary_perfect")
    assert issue["severity"] == "warning" and len(issue["noteIds"]) == 4


@pytest.mark.parametrize("cf,cp,position,expected", [
    ("C3 D3", "E3 A3", "above", "direct_perfect"),
    ("C3 E3", "A3 B3", "above", "direct_step_perfect"),
    ("C4 D4", "E3 G3", "below", "direct_step_perfect"),
    ("C4 G4", "E3 C4", "below", "direct_perfect"),
])
def test_direct_perfect_uses_the_actual_upper_voice_and_step_exception(cf, cp, position, expected):
    result = assess(cf, cp, position)
    assert len(rule(result, expected)) == 1
    assert not rule(result, "direct_step_perfect" if expected == "direct_perfect" else "direct_perfect")


@pytest.mark.parametrize("cf,cp", [("C3 D3", "A3 A3"), ("C3 D3", "B3 A3")])
def test_direct_rule_excludes_oblique_and_contrary(cf, cp):
    result = assess(cf, cp)
    assert not rule(result, "direct_perfect") and not rule(result, "direct_step_perfect")


def test_chromatic_unison_is_not_mislabeled_as_upper_leap_or_diatonic_step():
    result = assess("C4 D4", "A-4 A4")
    assert rule(result, "diatonic_pitch") and rule(result, "melodic_interval")
    assert not rule(result, "direct_perfect") and not rule(result, "direct_step_perfect")


def test_crossing_and_overlap_are_different_relations():
    crossing = assess("C4 E4", "E4 D4")
    assert len(rule(crossing, "voice_crossing")) == 1
    assert not rule(crossing, "voice_overlap")
    overlap = assess("C4 F4", "E4 A4")
    assert not rule(overlap, "voice_crossing")
    assert len(rule(overlap, "voice_overlap")) == 1
    assert len(rule(overlap, "voice_overlap")[0]["noteIds"]) == 4


def test_touching_previous_other_voice_is_allowed_overlap_boundary():
    assert not rule(assess("C4 E4", "E4 G4"), "voice_overlap")
    assert not rule(assess("C4 F4", "E4 A4", "below"), "voice_overlap")  # crossed pairs handled separately


def test_lower_counterpoint_overlap_and_touching_boundary():
    overlap = assess("G4 C5", "E4 A4", "below")
    assert len(rule(overlap, "voice_overlap")) == 1
    assert not rule(overlap, "voice_crossing")
    assert not rule(assess("G4 C5", "E4 G4", "below"), "voice_overlap")


def test_internal_unison_but_not_internal_octave_or_endpoint_unison():
    assert len(rule(assess("C4 D4 C4", "C4 D4 C4"), "interior_unison")) == 1
    assert not rule(assess("C4 D4 C4", "C4 D5 C4"), "interior_unison")


@pytest.mark.parametrize("position,cp,valid", [
    ("above", "C4", True), ("above", "G4", True), ("above", "C5", True),
    ("above", "G5", False), ("above", "E4", False),
    ("below", "C4", True), ("below", "C3", True), ("below", "F3", False),
])
def test_opening_limits_real_interval_and_upper_lower_conditions(position, cp, valid):
    result = assess("C4", cp, position)
    assert bool(rule(result, "opening")) is not valid


@pytest.mark.parametrize("cf,cp,position,key", [
    ("D4 C4", "B4 C5", "above", "C"),
    ("A3 G3", "F#4 G4", "above", "G"),
    ("E4 F4", "G3 F3", "below", "F"),
    ("D4 C4", "B3 C4", "below", "C"),
])
def test_major_cadence_transposition_and_final_unison(cf, cp, position, key):
    result = assess(cf, cp, position, key)
    assert not rule(result, "ending") and not rule(result, "cadence")


@pytest.mark.parametrize("cp", ["A4 C5", "D5 C5", "B4 G4", "B4 C6"])
def test_cadence_rejects_leap_similar_motion_non_tonic_or_double_octave(cp):
    result = assess("D4 C4", cp)
    assert rule(result, "ending") or rule(result, "cadence")


@pytest.mark.parametrize("cp,valid", [
    ("C4 D4", True), ("C4 E-4", True), ("C4 E4", True), ("C4 F4", True),
    ("C4 G4", True), ("C4 A-4", True), ("C4 C5", True),
    ("C5 C4", True), ("A-4 C4", False), ("C4 A4", False),
    ("C4 B4", False), ("C4 D5", False), ("F4 G#4", False), ("C4 F-4", False),
])
def test_melodic_quality_direction_and_size(cp, valid):
    result = assess("C3 C3", cp)
    assert bool(rule(result, "melodic_interval")) is not valid


@pytest.mark.parametrize("cp,warn", [("C4 G4 F4", False), ("C4 G4 A4", True), ("C4 G4 E4", True), ("C4 E4 F4", False)])
def test_leap_recovery_warning_boundary(cp, warn):
    assert bool(rule(assess("C3 C3 C3", cp), "leap_recovery")) is warn


def test_recommendations_are_not_hard_errors():
    leap = rule(assess("C3 C3 C3", "C4 E4 G4"), "successive_leaps")
    repeat = rule(assess("C3 C3", "G4 G4"), "repeated_pitch")
    climax = rule(assess("C3 C3 C3", "G4 E4 G4"), "climax")
    spacing = rule(assess("C3", "G4"), "voice_spacing")
    melodic_range = rule(assess("C3 C3", "C4 G5"), "melodic_range")
    assert all(issues and all(i["severity"] == "warning" for i in issues)
               for issues in [leap, repeat, climax, spacing, melodic_range])
    assert not rule(assess("C3", "E4"), "voice_spacing")  # exact tenth
    assert not rule(assess("C3 C3", "C4 E5"), "melodic_range")


def test_range_and_diatonic_spelling_are_separate_from_consonance():
    payload = reference_submission("species1-c-above")
    payload["notes"][2]["pitch"] = pitch_from_name("B5").model_dump()
    assert rule(grade(payload), "pitch_range")
    payload["notes"][2]["pitch"] = pitch_from_name("F#4").model_dump()
    assert rule(grade(payload), "diatonic_pitch")


@pytest.mark.parametrize("name,within", [("C4", True), ("A5", True), ("B3", False), ("B5", False)])
def test_exercise_pitch_range_includes_both_exact_bounds(name, within):
    payload = reference_submission("species1-c-above")
    payload["notes"][0]["pitch"] = pitch_from_name(name).model_dump()
    assert bool(rule(grade(payload), "pitch_range")) is not within


def test_missing_is_incomplete_and_empty_submission_cannot_pass():
    p = reference_submission("species1-c-above")
    p["notes"] = []
    result = grade(p)
    assert result["assessmentStatus"] == "incomplete" and not result["passed"]
    assert result["hardViolationCount"] == 8
    assert rule(result, "missing_note")[0]["noteIds"] == ["species1-c-above-cf-0", "species1-c-above-cp-0"]
    assert not rule(result, "climax")


def test_partial_input_does_not_bridge_missing_measure():
    result = assess("C3 E3 D3", "G3 B3 A3", missing=(1,))
    assert not rule(result, "parallel_fifth")


@pytest.mark.parametrize("mutation", [
    lambda p: p["notes"].append(deepcopy(p["notes"][0])),
    lambda p: p["notes"][0].update(durationTicks=960),
    lambda p: p["notes"][0].update(startTick=1),
    lambda p: p["notes"][0].update(startTick=1920 * 8),
    lambda p: p["notes"][0].update(id="untrusted"),
    lambda p: p["notes"][0].update(voiceId="cf"),
    lambda p: p["notes"][0].update(startTick=0.0),
    lambda p: p["notes"][0].update(startTick=-1),
    lambda p: p["notes"][0].update(durationTicks=0),
    lambda p: p["notes"][0]["pitch"].update(alter=True),
    lambda p: p["notes"][0]["pitch"].update(step="H"),
    lambda p: p["notes"][0]["pitch"].update(midi=60),
    lambda p: p.update(ruleProfileVersion="0"),
    lambda p: p.update(ruleProfileId="jazz"),
    lambda p: p.pop("cantus"),
])
def test_invalid_structure_is_never_musically_assessed(mutation):
    payload = reference_submission("species1-c-above")
    mutation(payload)
    result = grade(payload)
    assert result["assessmentStatus"] == "invalid" and not result["passed"]
    assert set(result["ruleCounts"]) == {"input_format"}


@pytest.mark.parametrize("mutation", [
    lambda cf: cf[0]["pitch"].update(step="D"),
    lambda cf: cf[0].update(durationTicks=960),
    lambda cf: cf[0].update(id="changed-cf"),
    lambda cf: cf.pop(),
    lambda cf: cf.reverse(),
])
def test_cantus_original_is_authoritative(mutation):
    payload = reference_submission("species1-c-above")
    mutation(payload["cantus"])
    result = grade(payload)
    assert result["assessmentStatus"] == "invalid" and not result["passed"]
    assert set(result["ruleCounts"]) == {"cantus_integrity"}


def test_deterministic_ordering_input_immutability_and_profile_versions():
    payload = reference_submission("species1-c-above")
    payload["notes"][1]["pitch"] = pitch_from_name("D5").model_dump()
    original = deepcopy(payload)
    first, second = grade(payload), grade(payload)
    assert first == second and payload == original
    payload["notes"].reverse()
    assert grade(payload) == first
    assert len({i["id"] for i in first["issues"]}) == len(first["issues"])
    assert first["ruleProfileId"] == profile("1")["id"]
    assert first["ruleProfileVersion"] == profile("1")["version"]
    assert first["engineVersion"]


def test_alternative_solution_is_graded_by_rules_not_reference_equality():
    p = reference_submission("species1-c-above")
    p["notes"] = make_notes(p["exerciseId"], "G4 F4 A4 G4 B4 A4 B4 C5".split())
    assert grade(p)["passed"]


def test_unknown_exercise_cannot_select_an_arbitrary_profile():
    with pytest.raises(KeyError):
        grade({"exerciseId": "unknown"})
