"""Original, fixed exercises. Reference answers are private server-side fixtures."""

from copy import deepcopy

from .models import Note, SpelledPitch, pitch_from_name
from .profile import MULTI_SPECIES_VERSION, PROFILE_ID, PROFILE_VERSION

PPQ = 480
MEASURE_TICKS = PPQ * 4


def make_notes(exercise_id: str, names: list[str], voice: str = "cp") -> list[dict]:
    return [Note(id=f"{exercise_id}-{voice}-{i}", voiceId=voice,
                 startTick=i * MEASURE_TICKS, durationTicks=MEASURE_TICKS,
                 pitch=pitch_from_name(name)).model_dump()
            for i, name in enumerate(names)]


def _exercise(identifier, title, objective, difficulty, tonic, position, names, low, high):
    alterations = {"G": {"F": 1}, "F": {"B": -1}}.get(tonic, {})
    allowed = [SpelledPitch(step=step, alter=alterations.get(step, 0), octave=octave)
               for octave in range(1, 7) for step in "CDEFGAB"]
    return {
        "id": identifier, "title": title, "objective": objective,
        "difficulty": difficulty, "species": 1, "keySignature": tonic,
        "mode": "major", "tonic": tonic, "position": position,
        "timeSignature": "4/4", "ppq": PPQ, "tempo": 80,
        "range": {"min": low, "max": high},
        "allowedPitches": [p.model_dump() for p in allowed if low <= p.midi <= high],
        "cantus": make_notes(identifier, names.split(), "cf"),
        "noteSlots": [{"startTick": i * MEASURE_TICKS, "durationTicks": MEASURE_TICKS} for i in range(len(names.split()))],
        "brief": {"summary": "定旋律の1音に対して、協和する対旋律を1音書きます。",
                  "rhythm": "4/4・各小節に全音符1音。",
                  "rules": ["同時に鳴る2音は同度・3度・5度・6度・8度を使います（複音程も可）。", "連続5度・8度、声部交差を避けます。", "最後は2声が反行の順次進行で主音に終わります。"]},
        "ruleProfileId": PROFILE_ID, "ruleProfileVersion": PROFILE_VERSION,
    }


_EXERCISES = [
    _exercise("species1-c-above", "01 · C major / 上声の一歩", "3度・6度を使い、定旋律と逆向きに動く上声を考えます。最後は導音から主音へ進みます。", "入門", "C", "above",
              "C4 D4 F4 E4 G4 F4 D4 C4", 60, 81),
    _exercise("species1-g-above", "02 · G major / 長い輪郭", "10小節をひとつの旋律として組み立てます。F♯の綴りと完全音程への入り方を確認します。", "基礎", "G", "above",
              "G3 A3 C4 B3 E4 D4 B3 C4 A3 G3", 55, 79),
    _exercise("species1-f-below", "03 · F major / 下声から支える", "定旋律の下に対旋律を書き、交差と重なりを区別します。終止では下声が全音下行します。", "基礎", "F", "below",
              "F4 G4 A4 C5 B-4 G4 E4 F4", 41, 65),
]


def _rhythmic_exercise(species, names, slots, position="above", tonic="C"):
    identifier = f"species{species}-{tonic.lower()}-{position}"
    briefs = {
        2: ("2音を1組にして、協和音の間を経過音でつなぎます。", "各小節に二分音符2音。最後は全音符1音。", ["第1拍は必ず協和にします。", "第3拍の不協和は、前後の協和音を同方向の順次進行でつなぐ経過音だけです。", "第1拍どうしの連続5度・8度にも注意します。"]),
        3: ("4音の流れの中で、経過音と刺繍音を使い分けます。", "各小節に四分音符4音。最後は全音符1音。", ["第1拍は必ず協和にします。", "不協和の経過音は前後を協和音にし、同方向の2歩でつなぎます。", "第2・4拍では順次進行で隣の音へ行き、元の協和音へ戻る刺繍音も使えます。", "カンビアータ・二重刺繍はこの課題では扱いません。"]),
        4: ("弱拍で準備した音を次の強拍まで保持し、不協和を下へ解決します。", "冒頭は二分休符。第3拍から次小節の前半まで同じ音を保持します。終止前だけ二分音符、最後は全音符です。", ["保持を始める第3拍は協和にします。", "強拍の不協和な保持音は、第3拍へ下行の順次進行で解決します。", "7度から6度、4度から3度、9度から8度へ解決する上声の掛留を練習します。", "第3拍どうしの連続5度・8度にも注意します。"]),
        5: ("二分音符・四分音符・保持音を組み合わせる、固定リズムの花飾対位法です。", "表示された混合リズムに音高を入力します。小節を跨ぐ保持は1つの入力枠です。", ["新しく始める第1拍は協和にします。", "弱拍の経過音、第2・4拍の刺繍音、準備と下行解決を伴う掛留を使えます。", "不協和の前後は協和にします。掛留は直前の第3拍から準備します。", "自由なリズム作成・8分音符・先取音・装飾した掛留解決は対象外です。"]),
    }
    summary, rhythm, rules = briefs[species]
    ex = _exercise(identifier, f"0{species + 2} · 第{species}種 / {'上声' if position == 'above' else '下声'}", summary,
                   "応用" if species >= 4 else "基礎", tonic, position, names, 60 if position == "above" else 43, 84 if position == "above" else 67)
    ex.update(species=species, ruleProfileVersion=MULTI_SPECIES_VERSION,
              noteSlots=[{"startTick": start, "durationTicks": duration} for start, duration in slots],
              brief={"summary": summary, "rhythm": rhythm, "rules": rules})
    return ex


_CF_MULTI = "C4 D4 F4 E4 G4 F4 D4 C4"
_CF_SYNCOPATED = "C4 D4 E4 F4 G4 E4 D4 C4"
_EXERCISES.extend([
    _rhythmic_exercise(2, _CF_SYNCOPATED, [(t, 960) for t in range(0, 7 * MEASURE_TICKS, 960)] + [(7 * MEASURE_TICKS, MEASURE_TICKS)]),
    _rhythmic_exercise(3, _CF_MULTI, [(t, 480) for t in range(0, 7 * MEASURE_TICKS, 480)] + [(7 * MEASURE_TICKS, MEASURE_TICKS)]),
    _rhythmic_exercise(4, _CF_SYNCOPATED, [(960 + i * MEASURE_TICKS, MEASURE_TICKS) for i in range(6)] + [(6 * MEASURE_TICKS + 960, 960), (7 * MEASURE_TICKS, MEASURE_TICKS)]),
    _rhythmic_exercise(5, _CF_SYNCOPATED, [(0, 960), (960, 480), (1440, 480), (1920, 960), (2880, 1920), (4800, 960), (5760, 480), (6240, 480), (6720, 960), (7680, 960), (8640, 1920), (10560, 480), (11040, 480), (11520, 960), (12480, 960), (13440, 1920)]),
])


def list_exercises() -> list[dict]:
    return deepcopy(_EXERCISES)


def get_exercise(exercise_id: str) -> dict:
    for exercise in _EXERCISES:
        if exercise["id"] == exercise_id:
            return deepcopy(exercise)
    raise KeyError(exercise_id)


# Filled with independently reviewed original answers, never returned by APIs.
_REFERENCE_ANSWERS = {
    "species1-c-above": "C5 B4 D5 C5 B4 A4 B4 C5",
    "species1-g-above": "D4 C4 E4 F#4 G4 A4 G4 E4 F#4 G4",
    "species1-f-below": "F4 B-3 C4 A3 G3 B-3 G3 F3",
    "species2-c-above": "G4 A4 B4 A4 C5 B4 D5 C5 E5 F5 G5 G4 A4 B4 C5",
    "species3-c-above": "G4 F4 E4 G4 F4 E4 F4 G4 A4 G4 A4 B4 C5 B4 C5 B4 E5 D5 C5 B4 C5 B4 A4 G4 F4 G4 A4 B4 C5",
    "species4-c-above": "C5 B4 G5 F5 E5 C5 B4 C5",
    "species5-c-above": "G4 F4 E4 F4 A4 G4 A4 G4 A4 B4 D5 C5 G4 A4 B4 C5",
}


def reference_submission(exercise_id: str) -> dict:
    """For automated verification only; intentionally absent from public API."""
    ex = get_exercise(exercise_id)
    names = _REFERENCE_ANSWERS[exercise_id].split()
    assert len(names) == len(ex["noteSlots"])
    notes = [Note(id=f"{exercise_id}-cp-{i}", voiceId="cp", pitch=pitch_from_name(name), **slot).model_dump()
             for i, (name, slot) in enumerate(zip(names, ex["noteSlots"]))]
    return {"exerciseId": exercise_id, "notes": notes,
            "cantus": ex["cantus"], "ruleProfileId": ex["ruleProfileId"], "ruleProfileVersion": ex["ruleProfileVersion"]}
