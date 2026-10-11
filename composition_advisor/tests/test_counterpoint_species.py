"""Independent rhythmic fragments and immutable-input boundaries for v2."""

from copy import deepcopy

import pytest

from composition_advisor.counterpoint import get_exercise, grade, list_exercises, profile
from composition_advisor.counterpoint.exercises import make_notes, reference_submission
from composition_advisor.counterpoint.grading_species import SpeciesFindings, assess_species_music
from composition_advisor.counterpoint.models import Note, between, pitch_from_name


NEW_IDS = [f"species{s}-c-above" for s in range(2, 6)]


def fragment(species, cf, events, *, position="above", missing=()):
    """Small theory examples do not select or compare to a reference answer."""
    ex = get_exercise(f"species{species}-c-above")
    ex.update(id="fragment", position=position, range={"min": 24, "max": 108},
              cantus=make_notes("fragment", cf.split(), "cf"),
              noteSlots=[{"startTick": t, "durationTicks": d} for t, d, _ in events])
    ex["allowedPitches"] = [{"step": s, "alter": 0, "octave": 4} for s in "CDEFGAB"]
    cp = {i: Note(id=f"fragment-cp-{i}", voiceId="cp", startTick=t, durationTicks=d,
                  pitch=pitch_from_name(p)) for i, (t, d, p) in enumerate(events) if i not in missing}
    findings = SpeciesFindings(ex)
    assess_species_music(ex, cp, findings)
    return findings.result("complete" if not missing else "incomplete")


def issues(result, rule):
    return [x for x in result["issues"] if x["ruleId"] == rule]


@pytest.mark.parametrize("identifier", NEW_IDS)
def test_each_new_species_has_a_clean_private_witness(identifier):
    payload = reference_submission(identifier)
    result = grade(payload)
    assert result["passed"] and result["assessmentStatus"] == "complete"
    assert result["hardViolationCount"] == result["warningCount"] == 0
    assert result["ruleProfileVersion"] == "2" and result["engineVersion"] == "2.0.0"


def test_profiles_are_versioned_and_first_species_policy_stays_v1():
    assert profile()["version"] == "2"
    assert profile("1")["version"] == "1"
    assert "strong_consonance" not in {r["id"] for r in profile("1")["rules"]}
    assert "suspension_resolution" in {r["id"] for r in profile()["rules"]}
    assert grade(reference_submission("species1-c-above"))["engineVersion"] == "1.0.0"
    with pytest.raises(KeyError):
        profile("unpublished")
    changed = profile("2")
    changed["rules"].clear()
    assert profile("2")["rules"]


@pytest.mark.parametrize("identifier,count,start", [(NEW_IDS[0], 15, 0), (NEW_IDS[1], 29, 0), (NEW_IDS[2], 8, 960), (NEW_IDS[3], 16, 0)])
def test_fixed_slots_cover_the_piece_and_only_fourth_species_has_initial_rest(identifier, count, start):
    ex = get_exercise(identifier)
    slots = ex["noteSlots"]
    assert len(slots) == count and slots[0]["startTick"] == start
    assert all(a["startTick"] + a["durationTicks"] == b["startTick"] for a, b in zip(slots, slots[1:]))
    assert slots[-1] == {"startTick": 13440, "durationTicks": 1920}
    assert set(ex["brief"]) == {"summary", "rhythm", "rules"}
    assert all(ex["brief"].values())
    assert {"solution", "answer", "reference", "notes"}.isdisjoint(ex)
    witness = reference_submission(identifier)
    assert [n["id"] for n in witness["notes"]] == [f"{identifier}-cp-{i}" for i in range(count)]


@pytest.mark.parametrize("identifier", NEW_IDS)
@pytest.mark.parametrize("mutation", ["cantus", "version", "duration", "onset", "id", "voice", "duplicate"])
def test_submission_cannot_change_server_rhythm_voice_profile_or_cantus(identifier, mutation):
    payload = reference_submission(identifier)
    if mutation == "cantus":
        payload["cantus"][0]["pitch"]["step"] = "D"
    elif mutation == "version":
        payload["ruleProfileVersion"] = "1"
    elif mutation == "duplicate":
        payload["notes"].append(deepcopy(payload["notes"][0]))
    else:
        field, value = {"duration": ("durationTicks", 480), "onset": ("startTick", 1), "id": ("id", "invented"), "voice": ("voiceId", "cf")}[mutation]
        if mutation == "duration":
            value = payload["notes"][0][field] + 480
        payload["notes"][0][field] = value
    result = grade(payload)
    assert result["assessmentStatus"] == "invalid" and not result["passed"]
    assert {i["ruleId"] for i in result["issues"]} <= {"input_format", "cantus_integrity"}


@pytest.mark.parametrize("identifier", NEW_IDS)
def test_shuffled_notes_are_deterministic_and_do_not_mutate_inputs(identifier):
    payload = reference_submission(identifier)
    original = deepcopy(payload)
    expected = grade(payload)
    assert payload == original
    payload["notes"].reverse()
    assert grade(payload) == expected


@pytest.mark.parametrize("identifier", NEW_IDS)
def test_missing_slot_is_incomplete_with_selectable_id_and_precise_beat(identifier):
    payload = reference_submission(identifier)
    deleted = payload["notes"].pop(1)
    result = grade(payload)
    assert result["assessmentStatus"] == "incomplete" and not result["passed"]
    issue, = issues(result, "missing_note")
    assert deleted["id"] in issue["noteIds"]
    assert issue["locations"] == [{"measure": deleted["startTick"] // 1920 + 1, "beat": deleted["startTick"] % 1920 / 480 + 1}]


def test_second_species_weak_passing_tone_is_allowed_but_neighbor_and_leaps_are_not():
    passing = fragment(2, "C4 C4", [(0, 960, "E4"), (960, 960, "F4"), (1920, 1920, "G4")])
    assert not issues(passing, "weak_dissonance")
    neighbor = fragment(2, "C4 C4", [(0, 960, "E4"), (960, 960, "F4"), (1920, 1920, "E4")])
    assert issues(neighbor, "weak_dissonance")[0]["locations"] == [{"measure": 1, "beat": 3}]
    leaping = fragment(2, "C4 C4", [(0, 960, "E4"), (960, 960, "F4"), (1920, 1920, "C5")])
    assert issues(leaping, "weak_dissonance")


@pytest.mark.parametrize("species", [2, 3, 5])
def test_new_attacked_dissonance_on_downbeat_is_never_a_passing_tone(species):
    result = fragment(species, "C4 C4 C4", [(960, 960, "E4"), (1920, 960, "F4"), (2880, 960, "G4"), (3840, 1920, "C5")])
    assert issues(result, "strong_consonance")[0]["locations"] == [{"measure": 2, "beat": 1}]


@pytest.mark.parametrize("species", [3, 5])
@pytest.mark.parametrize("middle,allowed", [(480, True), (960, False), (1440, True)])
def test_third_and_fifth_species_neighbors_only_on_beats_two_and_four(species, middle, allowed):
    result = fragment(species, "C4 C4", [(middle - 480, 480, "E4"), (middle, 480, "F4"), (middle + 480, 480, "E4")])
    assert bool(issues(result, "weak_dissonance")) is not allowed


@pytest.mark.parametrize("middle", [480, 960, 1440])
def test_third_species_all_weak_beats_allow_simple_passing_tones(middle):
    result = fragment(3, "C4 C4", [(middle - 480, 480, "E4"), (middle, 480, "F4"), (middle + 480, 480, "G4")])
    assert not issues(result, "weak_dissonance")


def test_ornaments_require_both_consonant_neighbors_and_do_not_bridge_missing_slots():
    events = [(0, 480, "E4"), (480, 480, "F4"), (960, 480, "G4"), (1440, 480, "A4")]
    result = fragment(3, "C4", events, missing=(0,))
    assert issues(result, "weak_dissonance")
    # E–F–G against changing C–D has dissonant G? Use an explicitly
    # dissonant D–E–F fragment: an adjacent dissonance cannot prepare a neighbor.
    result = fragment(3, "C4", [(0, 480, "D4"), (480, 480, "F4"), (960, 480, "G4")])
    assert issues(result, "weak_dissonance")


@pytest.mark.parametrize("cf,held,resolution", [
    ("C4 D4", "C5", "B4"),  # 7–6
    ("C4 E4", "A4", "G4"),  # 4–3
    ("E4 F4", "G5", "F5"),  # 9–8
    ("C3 E3", "A4", "G4"),  # compound 11–10
])
def test_prepared_suspension_types_and_compounds(cf, held, resolution):
    result = fragment(4, cf, [(960, 1920, held), (2880, 960, resolution)])
    assert not issues(result, "suspension_preparation")
    assert not issues(result, "suspension_resolution")
    assert not issues(result, "strong_consonance")


def test_lower_suspension_two_to_three_and_compound_are_direction_aware():
    for cf, held, resolution in [("G4 A4", "G4", "F4"), ("G4 A4", "G3", "F3")]:
        result = fragment(4, cf, [(960, 1920, held), (2880, 960, resolution)], position="below")
        assert not issues(result, "suspension_resolution")


@pytest.mark.parametrize("cf,held,resolution", [
    ("C4 D4", "C5", "D5"),  # upward resolution
    ("C4 D4", "C5", "A4"),  # downward third
    ("C4 D4", "C5", "G4"),  # consonant resolution, wrong motion
    ("D4 F4", "B4", "A4"),  # A4–M3 is not the normal P4 suspension
    ("D4 E4", "F4", "E4"),  # 2–1 is not upper 9–8
])
def test_suspension_rejects_wrong_direction_size_and_augmented_interval(cf, held, resolution):
    result = fragment(4, cf, [(960, 1920, held), (2880, 960, resolution)])
    assert issues(result, "suspension_resolution")


def test_suspension_requires_consonant_preparation_and_resolution_on_next_weak_beat():
    unprepared = fragment(4, "B3 D4", [(960, 1920, "C5"), (2880, 960, "B4")])
    assert issues(unprepared, "suspension_preparation")
    late = fragment(5, "C4 D4", [(960, 2400, "C5"), (3360, 480, "B4")])
    assert issues(late, "suspension_resolution")
    assert issues(late, "suspension_resolution")[0]["locations"] == [{"measure": 2, "beat": 1}, {"measure": 2, "beat": 3}]


def test_consonant_syncopation_needs_no_downward_resolution_and_rest_is_not_missing():
    result = fragment(4, "C4 E4", [(960, 1920, "C5"), (2880, 960, "E5")])
    assert not issues(result, "suspension_resolution")
    assert not issues(result, "suspension_preparation")
    result = grade(reference_submission("species4-c-above"))
    assert not issues(result, "missing_note")


def test_fourth_species_requires_tonic_suspension_at_the_cadence():
    payload = reference_submission("species4-c-above")
    payload["notes"][-3]["pitch"] = pitch_from_name("D5").model_dump()
    result = grade(payload)
    assert issues(result, "cadence")


@pytest.mark.parametrize("species,step", [(2, 960), (3, 480)])
def test_parallel_perfects_on_consecutive_downbeats_are_not_hidden_by_inner_notes(species, step):
    result = fragment(species, "C4 D4", [(0, step, "G4"), (step, 1920 - step, "E4"), (1920, 1920, "A4")])
    assert any(i["locations"] == [{"measure": 1, "beat": 1}, {"measure": 2, "beat": 1}] for i in issues(result, "parallel_fifth"))


def test_fourth_species_oblique_events_do_not_hide_parallel_weak_beats():
    result = fragment(4, "C4 D4 E4", [(960, 1920, "G4"), (2880, 1920, "A4"), (4800, 960, "G4")])
    matches = issues(result, "parallel_fifth")
    assert len(matches) == 1
    assert matches[0]["locations"] == [{"measure": 1, "beat": 3}, {"measure": 2, "beat": 3}]


def test_metric_check_does_not_invent_direct_motion_across_an_intervening_note():
    # E4→B4 above C4→E4 looks like a direct fifth by leap in the downbeat
    # reduction, but A4 intervenes: the real approach is the step A4→B4.
    # (G4 as the intervening note would instead be a genuine parallel fifth.)
    result = fragment(2, "C4 E4", [(0, 960, "E4"), (960, 960, "A4"), (1920, 1920, "B4")])
    assert not issues(result, "direct_perfect")
    assert not issues(result, "parallel_fifth")
    assert issues(result, "direct_step_perfect")[0]["locations"] == [{"measure": 1, "beat": 3}, {"measure": 2, "beat": 1}]


def test_held_crossing_is_checked_again_at_cantus_change():
    result = fragment(4, "C4 A4", [(960, 1920, "G4"), (2880, 960, "F4")])
    assert any(i["locations"] == [{"measure": 2, "beat": 1}] for i in issues(result, "voice_crossing"))


def test_separate_bad_beats_produce_distinct_ids_in_the_same_measure():
    # Beat 2 leaves the dissonance by leap; beat 4 arrives at it by leap.
    # (C5–D5–C5 on beats 3–4–1 would be a permitted upper neighbor.)
    result = fragment(3, "C4 C4", [(0, 480, "E4"), (480, 480, "F4"), (960, 480, "A4"), (1440, 480, "D5"), (1920, 1920, "C5")])
    found = issues(result, "weak_dissonance")
    assert len(found) == 2 and len({i["id"] for i in found}) == 2
    assert [i["locations"][0]["beat"] for i in found] == [2, 4]


def test_reference_dissonances_match_independent_written_audit():
    # These harmonies are hand-derived by a separate reviewer, not generated
    # from the grading rules. Held notes are included at the barline.
    expected = {
        "species2-c-above": [(8640, "m7")],
        "species4-c-above": [(1920, "m7"), (5760, "M9"), (7680, "m7"), (11520, "m7")],
        "species5-c-above": [(960, "P4"), (3840, "P4"), (6240, "M2"), (9600, "m7")],
    }
    for identifier, rows in expected.items():
        payload = reference_submission(identifier)
        cp = [Note.model_validate(n) for n in payload["notes"]]
        cf = [Note.model_validate(n) for n in payload["cantus"]]
        for tick, name in rows:
            held = next(n for n in cp if n.startTick <= tick < n.startTick + n.durationTicks)
            assert between(cf[tick // 1920].pitch, held.pitch).name == name
