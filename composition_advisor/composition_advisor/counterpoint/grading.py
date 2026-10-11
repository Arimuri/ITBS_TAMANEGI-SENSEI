"""Versioned, deterministic, spelling-aware two-voice first-species grading.

Structural errors stop musical assessment. Missing notes do not: only actually
adjacent, populated measures are compared, never notes across a hole. Each
phenomenon is emitted once; parallel perfects suppress the direct-motion rule.
"""

from __future__ import annotations

from collections import Counter

from pydantic import ValidationError

from .exercises import MEASURE_TICKS, get_exercise
from .models import Note, Submission, between, consonant, perfect_family, stepwise
from .profile import ENGINE_VERSION, PROFILE_ID, PROFILE_VERSION, RULE_BY_ID


class Findings:
    def __init__(self):
        self.issues: list[dict] = []

    def add(self, rule: str, notes: list[Note], message: str, hint: str,
            *, positions: list[int] | None = None, explanation: str | None = None,
            related_ids: list[str] | None = None):
        positions = sorted(set(positions if positions is not None else
                               [n.startTick // MEASURE_TICKS for n in notes]))
        ids = list(dict.fromkeys([n.id for n in notes] + (related_ids or [])))
        identifier = f"{rule}:{','.join(str(i + 1) for i in positions)}"
        if any(issue["id"] == identifier for issue in self.issues):
            return
        self.issues.append({
            "id": identifier, "ruleId": rule, "severity": RULE_BY_ID[rule]["severity"],
            "noteIds": ids, "locations": [{"measure": i + 1, "beat": 1} for i in positions],
            "message": message, "explanation": explanation or RULE_BY_ID[rule]["description"],
            "hint": hint,
        })

    def result(self, exercise_id: str, status: str) -> dict:
        issues = sorted(self.issues, key=lambda item: (
            item["locations"][0]["measure"] if item["locations"] else 0,
            item["ruleId"], item["id"]))
        hard = sum(i["severity"] == "error" for i in issues)
        return {
            "exerciseId": exercise_id, "ruleProfileId": PROFILE_ID,
            "ruleProfileVersion": PROFILE_VERSION, "engineVersion": ENGINE_VERSION,
            "assessmentStatus": status, "passed": status == "complete" and hard == 0,
            "hardViolationCount": hard,
            "warningCount": sum(i["severity"] == "warning" for i in issues),
            "issues": issues, "ruleCounts": dict(sorted(Counter(i["ruleId"] for i in issues).items())),
        }


def _motion(a: Note, b: Note) -> int:
    return b.pitch.midi - a.pitch.midi


def _voices(exercise: dict, cf: Note, cp: Note) -> tuple[Note, Note]:
    return (cp, cf) if exercise["position"] == "above" else (cf, cp)


def assess_music(exercise: dict, cp_by_index: dict[int, Note], findings: Findings) -> None:
    """Pure musical checks over validated note events; also used by rule fixtures."""
    cf = [Note.model_validate(n) for n in exercise["cantus"]]
    count = len(cf)
    allowed = {(p["step"], p["alter"]) for p in exercise["allowedPitches"]}
    for i, cp in sorted(cp_by_index.items()):
        fixed = cf[i]
        pair = [fixed, cp]
        upper, lower = _voices(exercise, fixed, cp)
        label = f"第{i + 1}小節：定旋律 {fixed.pitch.label}／対旋律 {cp.pitch.label}"
        harmonic = between(lower.pitch, upper.pitch)
        if not exercise["range"]["min"] <= cp.pitch.midi <= exercise["range"]["max"]:
            findings.add("pitch_range", [cp], f"第{i + 1}小節の {cp.pitch.label} が指定音域の外です。", "ピアノロールに示した入力音域内で配置を考えてください。")
        if (cp.pitch.step, cp.pitch.alter) not in allowed:
            findings.add("diatonic_pitch", [cp], f"第{i + 1}小節の {cp.pitch.label} は、この課題の調にない綴りです。", "調号と音名を確認してください。異名同音でも綴りによって音程の種類が変わります。")
        if not consonant(lower.pitch, upper.pitch):
            findings.add("vertical_consonance", pair, f"{label} は {harmonic.name}（不協和）です。", "同時に鳴る2音の綴りを見て、3度・6度などの協和音程を検討してください。")
        if upper.pitch.midi < lower.pitch.midi:
            findings.add("voice_crossing", pair, f"{label} で、指定の上声と下声が逆転しています。", "対旋律を指定された側へ置き直し、前後のつながりも確認してください。")
        if 0 < i < count - 1 and cp.pitch.midi == fixed.pitch.midi:
            findings.add("interior_unison", pair, f"{label} が曲の途中で同度になっています。", "途中の小節では2声が別の高さになる協和音程を検討してください。")
        if harmonic.generic.undirected > 10:
            findings.add("voice_spacing", pair, f"{label} は声部間が10度を超えています。", "各声を別々に聴いた後、2声のまとまりを確かめてください。")

    if 0 in cp_by_index:
        cp = cp_by_index[0]
        harmonic = between(cf[0].pitch, cp.pitch)
        permitted = {"P1", "P8", "P5"} if exercise["position"] == "above" else {"P1", "P8"}
        if harmonic.name not in permitted:
            findings.add("opening", [cf[0], cp], f"開始音程 {harmonic.name} は、この上下配置の開始条件に合いません。", "上声なら同度・5度・8度、下声なら同度・8度から始めます。")
    last = count - 1
    if last in cp_by_index:
        cp = cp_by_index[last]
        tonic = cf[-1].pitch
        if (between(tonic, cp.pitch).name not in {"P1", "P8"}
                or (cp.pitch.step, cp.pitch.alter) != (tonic.step, tonic.alter)):
            findings.add("ending", [cf[-1], cp], "最後の2音が、主音の完全同度または8度になっていません。", "課題の主音を確認し、終わりの垂直音程を見直してください。")
        if last - 1 in cp_by_index:
            prev = cp_by_index[last - 1]
            cf_motion, cp_motion = _motion(cf[-2], cf[-1]), _motion(prev, cp)
            if (not stepwise(cf[-2].pitch, cf[-1].pitch)
                    or not stepwise(prev.pitch, cp.pitch)
                    or sorted([cf_motion, cp_motion]) != [-2, 1]):
                findings.add("cadence", [cf[-2], prev, cf[-1], cp], "終止の2小節が、導音の半音上行と第2音の全音下行による反行になっていません。", "最後の音から逆に考え、各声がどちら側から主音に近づくか確認してください。")

    for i in range(1, count):
        if i - 1 not in cp_by_index or i not in cp_by_index:
            continue
        previous, current = cp_by_index[i - 1], cp_by_index[i]
        pcf, ccf = cf[i - 1], cf[i]
        quartet = [pcf, previous, ccf, current]
        cf_motion, cp_motion = _motion(pcf, ccf), _motion(previous, current)
        old_upper, old_lower = _voices(exercise, pcf, previous)
        new_upper, new_lower = _voices(exercise, ccf, current)
        ordered = old_upper.pitch.midi >= old_lower.pitch.midi and new_upper.pitch.midi >= new_lower.pitch.midi
        if ordered and (new_upper.pitch.midi < old_lower.pitch.midi or new_lower.pitch.midi > old_upper.pitch.midi):
            findings.add("voice_overlap", quartet, f"第{i}→{i + 1}小節で、一方の声部が直前の相手の音域を越えています。", "同時点の交差だけでなく、前の小節の相手の音との位置関係を確認してください。")
        before = perfect_family(pcf.pitch, previous.pitch)
        after = perfect_family(ccf.pitch, current.pitch)
        similar = cf_motion * cp_motion > 0
        if ordered and before and before == after and similar:
            rule = "parallel_fifth" if after == "fifth" else "parallel_octave"
            findings.add(rule, quartet, f"第{i}→{i + 1}小節で、両声が同方向に動き、完全{'5度系' if after == 'fifth' else '同度・8度系'}が連続しています。", "前後の4音を確認し、声部の進行方向または次の垂直音程を変える余地を探してください。")
        elif ordered and before and before == after and cf_motion * cp_motion < 0:
            findings.add("contrary_perfect", quartet, f"第{i}→{i + 1}小節で、反行による同じ完全音程族の連続があります。", "より厳格な種対位法では避ける進行です。間に不完全協和音程を置く方法も考えてください。")
        elif ordered and after and similar and between(old_upper.pitch, new_upper.pitch).generic.undirected >= 3:
            findings.add("direct_perfect", quartet, f"第{i}→{i + 1}小節で、上声の跳躍を伴う同方向進行が完全音程に到達しています。", "上声を順次進行にできるか、あるいは反行で入れるかを考えてください。")
        elif ordered and after and similar and stepwise(old_upper.pitch, new_upper.pitch):
            findings.add("direct_step_perfect", quartet, f"第{i}→{i + 1}小節で、上声の順次進行による直接進行が完全音程に到達しています。", "このプロファイルでは警告です。厳格な種対位法の練習として、反行・斜行で到達する案も考えてください。")

        melodic = between(previous.pitch, current.pitch)
        allowed_leap = melodic.name in {"P1", "m2", "M2", "m3", "M3", "P4", "P5", "P8"} or (melodic.name == "m6" and cp_motion > 0)
        if not allowed_leap:
            findings.add("melodic_interval", [previous, current], f"対旋律の第{i}→{i + 1}小節（{previous.pitch.label}→{current.pitch.label}）の {melodic.name} は許容する旋律音程ではありません。", "綴りと方向を確認し、順次進行や許容された跳躍でつなぐ方法を探してください。")
        if cp_motion == 0:
            findings.add("repeated_pitch", [previous, current], f"対旋律の第{i}→{i + 1}小節で同じ音が続いています。", "斜行は使えますが、この位置で対旋律を動かしたときの輪郭も聴いてみてください。")
        if i + 1 in cp_by_index:
            following = cp_by_index[i + 1]
            next_motion = _motion(current, following)
            if allowed_leap and melodic.generic.undirected >= 4 and not (cp_motion * next_motion < 0 and stepwise(current.pitch, following.pitch)):
                findings.add("leap_recovery", [previous, current, following], f"対旋律の第{i}→{i + 1}小節の跳躍後が、逆向きの順次進行ではありません。", "跳躍で開いた音域を、次の1音で戻す形を試聴して比べてください。")
            if melodic.generic.undirected >= 3 and between(current.pitch, following.pitch).generic.undirected >= 3 and cp_motion * next_motion > 0:
                findings.add("successive_leaps", [previous, current, following], f"対旋律の第{i}〜{i + 2}小節に、同方向の連続跳躍があります。", "旋律を歌って確かめ、途中を順次進行にした輪郭と聴き比べてください。")

    if len(cp_by_index) == count:
        notes = [cp_by_index[i] for i in range(count)]
        low, high = min(notes, key=lambda n: n.pitch.midi), max(notes, key=lambda n: n.pitch.midi)
        if between(low.pitch, high.pitch).generic.undirected > 10:
            findings.add("melodic_range", [low, high], "対旋律全体の音域が10度を超えています。", "最高音と最低音の位置を見て、歌いやすい幅にまとめられるか確認してください。")
        peaks = [n for n in notes if n.pitch.midi == high.pitch.midi]
        if len(peaks) > 1:
            findings.add("climax", peaks, "対旋律の最高音が複数回現れています。", "どこを旋律の頂点として聴かせたいかを考えてください。")


def grade(payload: dict) -> dict:
    """Validate a submission against server-owned material, then apply policy.

    Unknown exercise IDs raise KeyError for the API's 404 response. All known
    exercise form errors return an explicit invalid assessment, never a pass.
    """
    exercise_id = payload.get("exerciseId") if isinstance(payload, dict) else None
    if not isinstance(exercise_id, str):
        exercise_id = ""
    exercise = get_exercise(exercise_id)
    if exercise["species"] != 1:
        from .grading_species import grade_species
        return grade_species(payload, exercise)
    findings = Findings()
    try:
        submission = Submission.model_validate(payload)
    except ValidationError:
        findings.add("input_format", [], "提出データの型・必須項目・音高・音符数を確認してください。", "課題を再読み込みし、整数tickと音名の綴りを持つ音符データで提出してください。")
        return findings.result(exercise_id, "invalid")
    if submission.ruleProfileId != PROFILE_ID or submission.ruleProfileVersion != PROFILE_VERSION:
        findings.add("input_format", [], "指定されたルールプロファイルまたはバージョンが課題と異なります。", "課題を再読み込みし、表示された規則で再提出してください。")
    if [n.model_dump() for n in submission.cantus] != exercise["cantus"]:
        changed = [Note.model_validate(n) for n in exercise["cantus"]]
        findings.add("cantus_integrity", changed, "提出された定旋律が、課題の原本と一致しません。", "定旋律の編集はできません。課題を再読み込みしてください。")
    cp_by_index = {}
    expected_count = len(exercise["cantus"])
    for note in submission.notes:
        index, remainder = divmod(note.startTick, MEASURE_TICKS)
        if (remainder or not 0 <= index < expected_count or note.durationTicks != MEASURE_TICKS
                or note.voiceId != "cp" or note.id != f"{exercise_id}-cp-{index}"
                or index in cp_by_index):
            findings.add("input_format", [note], "音符の重複、ID、声部、開始位置、または長さが第1種の入力形式に合いません。", "各小節の先頭に、固定長の対旋律を1音だけ置いてください。")
        else:
            cp_by_index[index] = note
    if findings.issues:
        return findings.result(exercise_id, "invalid")
    for index in range(expected_count):
        if index not in cp_by_index:
            fixed = Note.model_validate(exercise["cantus"][index])
            findings.add("missing_note", [fixed], f"第{index + 1}小節の対旋律が未入力です。", "この小節に全音符を1音入力してください。", related_ids=[f"{exercise_id}-cp-{index}"])
    assess_music(exercise, cp_by_index, findings)
    status = "complete" if len(cp_by_index) == expected_count else "incomplete"
    return findings.result(exercise_id, status)
