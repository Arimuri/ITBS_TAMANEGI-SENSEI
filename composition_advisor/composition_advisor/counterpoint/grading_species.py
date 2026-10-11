"""Time-aware checks for the explicitly bounded, fixed-rhythm species 2–5.

The cantus and rhythm belong to the server. A tied pitch is one event spanning
a barline; sounding intervals are evaluated again whenever either voice changes.
Metric comparisons supplement adjacent-event comparisons, since syncopations
otherwise make every transition oblique and can conceal parallel perfects.
"""

from __future__ import annotations

from collections import Counter

from pydantic import ValidationError

from .exercises import MEASURE_TICKS, PPQ
from .models import Note, Submission, between, consonant, perfect_family, stepwise
from .profile import MULTI_SPECIES_ENGINE_VERSION, V2_RULE_BY_ID


class SpeciesFindings:
    def __init__(self, exercise: dict):
        self.exercise = exercise
        self.issues: list[dict] = []

    def add(self, rule: str, notes: list[Note], message: str, hint: str,
            *, ticks: list[int] | None = None, related_ids: list[str] | None = None):
        ticks = sorted(set(ticks if ticks is not None else [n.startTick for n in notes]))
        ids = list(dict.fromkeys([n.id for n in notes] + (related_ids or [])))
        identifier = f"{rule}:{','.join(map(str, ticks))}"
        if any(issue["id"] == identifier for issue in self.issues):
            return
        self.issues.append({
            "id": identifier, "ruleId": rule, "severity": V2_RULE_BY_ID[rule]["severity"],
            "noteIds": ids,
            "locations": [{"measure": t // MEASURE_TICKS + 1, "beat": (t % MEASURE_TICKS) / PPQ + 1} for t in ticks],
            "message": message, "explanation": V2_RULE_BY_ID[rule]["description"], "hint": hint,
        })

    def result(self, status: str) -> dict:
        issues = sorted(self.issues, key=lambda item: (
            tuple((p["measure"], p["beat"]) for p in item["locations"]), item["ruleId"], item["id"]))
        hard = sum(i["severity"] == "error" for i in issues)
        return {
            "exerciseId": self.exercise["id"], "ruleProfileId": self.exercise["ruleProfileId"],
            "ruleProfileVersion": self.exercise["ruleProfileVersion"], "engineVersion": MULTI_SPECIES_ENGINE_VERSION,
            "assessmentStatus": status, "passed": status == "complete" and hard == 0,
            "hardViolationCount": hard, "warningCount": sum(i["severity"] == "warning" for i in issues),
            "issues": issues, "ruleCounts": dict(sorted(Counter(i["ruleId"] for i in issues).items())),
        }


def assess_species_music(exercise: dict, cp_by_index: dict[int, Note], findings: SpeciesFindings) -> None:
    cf = [Note.model_validate(n) for n in exercise["cantus"]]
    notes = [n for _, n in sorted(cp_by_index.items())]
    species = exercise["species"]
    slots = exercise["noteSlots"]
    finish = len(cf) * MEASURE_TICKS
    allowed = {(p["step"], p["alter"]) for p in exercise["allowedPitches"]}

    def fixed_at(tick: int) -> Note:
        return cf[tick // MEASURE_TICKS]

    def sounding(tick: int) -> Note | None:
        return next((n for n in notes if n.startTick <= tick < n.startTick + n.durationTicks), None)

    def ordered(fixed: Note, cp: Note) -> tuple[Note, Note]:
        return (cp, fixed) if exercise["position"] == "above" else (fixed, cp)

    def is_consonant_at(note: Note, tick: int | None = None) -> bool:
        return consonant(fixed_at(note.startTick if tick is None else tick).pitch, note.pitch)

    def label(tick: int) -> str:
        return f"第{tick // MEASURE_TICKS + 1}小節・第{tick % MEASURE_TICKS // PPQ + 1}拍"

    for i, cp in sorted(cp_by_index.items()):
        if not exercise["range"]["min"] <= cp.pitch.midi <= exercise["range"]["max"]:
            findings.add("pitch_range", [cp], f"{label(cp.startTick)}の{cp.pitch.label}が指定音域外です。", "課題の入力音域を確認してください。")
        if (cp.pitch.step, cp.pitch.alter) not in allowed:
            findings.add("diatonic_pitch", [cp], f"{label(cp.startTick)}の音名は、この長調の調号に合いません。", "調号どおりの音名で入力してください。")
        previous, following = cp_by_index.get(i - 1), cp_by_index.get(i + 1)
        # A missing slot is a gap, never an opportunity to invent a passing tone
        # or recover a leap by joining the notes on either side of it.
        if previous is None:
            continue
        movement = cp.pitch.midi - previous.pitch.midi
        melodic = between(previous.pitch, cp.pitch)
        permitted = melodic.name in {"P1", "m2", "M2", "m3", "M3", "P4", "P5", "P8"} or (melodic.name == "m6" and movement > 0)
        if not permitted:
            findings.add("melodic_interval", [previous, cp], f"対旋律の{previous.pitch.label}→{cp.pitch.label}は許容しない旋律音程{melodic.name}です。", "綴りを確認し、順次進行や許容した跳躍を使ってください。")
        if movement == 0:
            findings.add("repeated_pitch", [previous, cp], "別の音符枠で同音が続いています。", "保持音は1音として表示されます。新しく始まる音の輪郭を確認してください。")
        if following is not None:
            next_motion = following.pitch.midi - cp.pitch.midi
            if permitted and melodic.generic.undirected >= 4 and not (movement * next_motion < 0 and stepwise(cp.pitch, following.pitch)):
                findings.add("leap_recovery", [previous, cp, following], "4度以上の跳躍の後が反対方向の順次進行ではありません。", "跳躍で開いた音域を次の音で戻す形も試してください。")
            if melodic.generic.undirected >= 3 and between(cp.pitch, following.pitch).generic.undirected >= 3 and movement * next_motion > 0:
                findings.add("successive_leaps", [previous, cp, following], "同方向の跳躍が続いています。", "旋律を歌い、順次進行を含む輪郭と比べてください。")

    events = sorted({n.startTick for n in cf} | {n.startTick for n in notes})
    slot_by_id = {f"{exercise['id']}-cp-{i}": i for i in range(len(slots))}
    for tick in events:
        cp = sounding(tick)
        if cp is None:
            continue
        fixed = fixed_at(tick)
        upper, lower = ordered(fixed, cp)
        pair = [fixed, cp]
        harmonic = between(lower.pitch, upper.pitch)
        if upper.pitch.midi < lower.pitch.midi:
            findings.add("voice_crossing", pair, f"{label(tick)}で上下の声部が交差しています。", "対旋律を指定された側へ置き直してください。", ticks=[tick])
        if slots[0]["startTick"] < tick < cf[-1].startTick and cp.pitch.midi == fixed.pitch.midi:
            findings.add("interior_unison", pair, f"{label(tick)}で途中の同度が生じています。", "途中では2声を別の高さへ分けてください。", ticks=[tick])
        if harmonic.generic.undirected > 10:
            findings.add("voice_spacing", pair, f"{label(tick)}の声部間隔が10度を超えています。", "2声を聴いてまとまりを確認してください。", ticks=[tick])
        if consonant(fixed.pitch, cp.pitch):
            continue
        strong = tick % MEASURE_TICKS == 0
        held = cp.startTick < tick
        index = slot_by_id[cp.id]
        if species in {4, 5} and strong and held:
            prepared = cp.startTick == tick - MEASURE_TICKS // 2 and is_consonant_at(cp)
            if not prepared:
                findings.add("suspension_preparation", [fixed_at(cp.startTick), cp, fixed], f"{label(tick)}の掛留に、直前の弱拍での協和な準備がありません。", "前小節の第3拍で協和音を置き、その同じ音を保持してください。", ticks=[cp.startTick, tick])
            resolution = cp_by_index.get(index + 1)
            resolves_at = tick + MEASURE_TICKS // 2
            resolved = (resolution is not None and resolution.startTick == resolves_at
                        and resolution.pitch.midi < cp.pitch.midi
                        and stepwise(cp.pitch, resolution.pitch)
                        and is_consonant_at(resolution))
            # Interval qualities are already checked by consonance. Written
            # generic families distinguish 9–8 from 2–3 and preserve compounds.
            if resolved:
                before_size = (between(fixed.pitch, cp.pitch).generic.undirected - 1) % 7 + 1
                after_size = (between(fixed.pitch, resolution.pitch).generic.undirected - 1) % 7 + 1
                types = {(7, 6), (4, 3), (2, 1)} if exercise["position"] == "above" else {(2, 3)}
                suspension_interval = between(fixed.pitch, cp.pitch)
                resolved = ((before_size, after_size) in types
                            and suspension_interval.simpleName in {"P4", "m7", "M7", "m2", "M2"}
                            and not (exercise["position"] == "above" and before_size == 2 and suspension_interval.generic.undirected < 9))
            if not resolved:
                findings.add("suspension_resolution", pair + ([resolution] if resolution else []), f"{label(tick)}の掛留が、次の第3拍に許容された形で下行解決していません。", "保持した音から1段下がり、上声7–6・4–3・9–8、下声2–3の協和な解決を確認してください。", ticks=[tick, resolves_at])
        elif strong:
            findings.add("strong_consonance", pair, f"{label(tick)}は不協和音程{harmonic.name}です。", "第1拍は協和にします。第4・5種では適切に準備された掛留だけを例外として使います。", ticks=[tick])
        else:
            previous, following = cp_by_index.get(index - 1), cp_by_index.get(index + 1)
            simple_ornament = False
            if previous is not None and following is not None and cp.startTick == tick:
                neighbors_consonant = is_consonant_at(previous, previous.startTick + previous.durationTicks - 1) and is_consonant_at(following)
                steps = stepwise(previous.pitch, cp.pitch) and stepwise(cp.pitch, following.pitch)
                into = cp.pitch.midi - previous.pitch.midi
                out = following.pitch.midi - cp.pitch.midi
                passing = into * out > 0
                neighbor = (previous.pitch == following.pitch and tick % MEASURE_TICKS in {PPQ, 3 * PPQ} and species in {3, 5})
                simple_ornament = neighbors_consonant and steps and (passing or neighbor)
            if species == 4 or not simple_ornament:
                findings.add("weak_dissonance", pair + ([previous] if previous else []) + ([following] if following else []), f"{label(tick)}の不協和音程{harmonic.name}は、この種で許容した経過音・刺繍音ではありません。", "前後を協和音にし、2歩の順次進行を確認してください。第2種は同方向の経過音だけを使います。", ticks=[tick])

    def compare(t0: int, t1: int, *, metric: bool = False) -> None:
        pcp, ccp = sounding(t0), sounding(t1)
        if pcp is None or ccp is None:
            return
        # Do not compare across an unfilled fixed slot, including a slot that
        # lies between consecutive metric checkpoints.
        if any(i not in cp_by_index and s["startTick"] < t1 and s["startTick"] + s["durationTicks"] > t0
               for i, s in enumerate(slots)):
            return
        pcf, ccf = fixed_at(t0), fixed_at(t1)
        pu, pl = ordered(pcf, pcp)
        cu, cl = ordered(ccf, ccp)
        if pu.pitch.midi < pl.pitch.midi or cu.pitch.midi < cl.pitch.midi:
            return
        quartet = [pcf, pcp, ccf, ccp]
        cf_motion, cp_motion = ccf.pitch.midi - pcf.pitch.midi, ccp.pitch.midi - pcp.pitch.midi
        if not metric and (cu.pitch.midi < pl.pitch.midi or cl.pitch.midi > pu.pitch.midi):
            findings.add("voice_overlap", quartet, "一方の声部が直前の相手の音域を越えています。", "同時点の交差と、前の相手の音との位置関係を区別してください。", ticks=[t0, t1])
        before, after = perfect_family(pcf.pitch, pcp.pitch), perfect_family(ccf.pitch, ccp.pitch)
        if before and before == after and cf_motion * cp_motion > 0:
            rule = "parallel_fifth" if after == "fifth" else "parallel_octave"
            findings.add(rule, quartet, f"{label(t0)}→{label(t1)}で同方向の完全音程が連続しています。", "途中の音だけでなく、同じ拍どうしの骨格も確認してください。", ticks=[t0, t1])
        elif before and before == after and cf_motion * cp_motion < 0:
            findings.add("contrary_perfect", quartet, "同じ完全音程族が反行で連続しています。", "厳格な種対位法では避ける進行です。間に不完全協和音程を検討してください。", ticks=[t0, t1])
        elif not metric and after and cf_motion * cp_motion > 0:
            if between(pu.pitch, cu.pitch).generic.undirected >= 3:
                findings.add("direct_perfect", quartet, "上声の跳躍を伴う同方向進行で完全音程に到達しています。", "上声の順次進行または反行を検討してください。", ticks=[t0, t1])
            elif stepwise(pu.pitch, cu.pitch):
                findings.add("direct_step_perfect", quartet, "上声の順次進行による直接進行で完全音程に到達しています。", "この学習方針では警告ですが、反行で到達する形も試してください。", ticks=[t0, t1])

    for t0, t1 in zip(events, events[1:]):
        compare(t0, t1)
    for offset in ([0, MEASURE_TICKS // 2] if species in {4, 5} else [0]):
        for t0 in range(offset, finish - MEASURE_TICKS, MEASURE_TICKS):
            compare(t0, t0 + MEASURE_TICKS, metric=True)

    first, last = cp_by_index.get(0), cp_by_index.get(len(slots) - 1)
    if first is not None:
        harmonic = between(cf[0].pitch, first.pitch).name
        permitted = {"P1", "P5", "P8"} if exercise["position"] == "above" else {"P1", "P8"}
        if harmonic not in permitted:
            findings.add("opening", [cf[0], first], "開始音程が指定された上下配置の条件に合いません。", "上声なら同度・5度・8度、下声なら同度・8度で始めます。", ticks=[first.startTick])
    if last is not None:
        tonic = cf[-1].pitch
        if between(tonic, last.pitch).name not in {"P1", "P8"} or (last.pitch.step, last.pitch.alter) != (tonic.step, tonic.alter):
            findings.add("ending", [cf[-1], last], "終止が主音の完全同度または8度になっていません。", "最後の主音と垂直音程を確認してください。")
        previous = cp_by_index.get(len(slots) - 2)
        # A one-measure fragment has no approach to the cadence to judge.
        if previous is not None and len(cf) >= 2:
            movements = [cf[-1].pitch.midi - cf[-2].pitch.midi, last.pitch.midi - previous.pitch.midi]
            suspended_tonic = sounding(cf[-2].startTick)
            fourth_cadence = (species != 4 or exercise["position"] != "above" or
                             (suspended_tonic is not None and suspended_tonic.startTick == cf[-2].startTick - MEASURE_TICKS // 2
                              and suspended_tonic.pitch == last.pitch and previous.startTick == cf[-2].startTick + MEASURE_TICKS // 2))
            if sorted(movements) != [-2, 1] or not stepwise(previous.pitch, last.pitch) or not stepwise(cf[-2].pitch, cf[-1].pitch) or not fourth_cadence:
                findings.add("cadence", [cf[-2], previous, cf[-1], last], "終止に導音の半音上行と第2音の全音下行の反行がありません。", "最後に新しく鳴る対旋律の音から主音へ、順次進行で近づいてください。")
    if len(notes) == len(slots):
        low, high = min(notes, key=lambda n: n.pitch.midi), max(notes, key=lambda n: n.pitch.midi)
        if between(low.pitch, high.pitch).generic.undirected > 10:
            findings.add("melodic_range", [low, high], "対旋律の全体の音域が10度を超えています。", "歌いやすい幅にまとめられるか確認してください。")
        peaks = [n for n in notes if n.pitch.midi == high.pitch.midi]
        if len(peaks) > 1:
            findings.add("climax", peaks, "対旋律の最高音が複数回現れています。", "どの音を旋律の頂点にするか考えてください。")


def grade_species(payload: dict, exercise: dict) -> dict:
    findings = SpeciesFindings(exercise)
    try:
        submission = Submission.model_validate(payload)
    except ValidationError:
        findings.add("input_format", [], "提出データの型・必須項目・音高・音符数が入力形式に合いません。", "課題を再読み込みし、指定された音符枠を使ってください。")
        return findings.result("invalid")
    if (submission.ruleProfileId, submission.ruleProfileVersion) != (exercise["ruleProfileId"], exercise["ruleProfileVersion"]):
        findings.add("input_format", [], "課題と提出のルールプロファイルが異なります。", "課題を再読み込みしてください。")
    if [n.model_dump() for n in submission.cantus] != exercise["cantus"]:
        findings.add("cantus_integrity", [Note.model_validate(n) for n in exercise["cantus"]], "定旋律が課題の原本と異なります。", "定旋律は編集できません。課題を再読み込みしてください。")
    expected = {f"{exercise['id']}-cp-{i}": (i, slot) for i, slot in enumerate(exercise["noteSlots"])}
    cp_by_index = {}
    for note in submission.notes:
        match = expected.get(note.id)
        if match is None:
            findings.add("input_format", [note], "音符IDが課題の入力枠にありません。", "課題の固定された音符枠を使ってください。")
            continue
        index, slot = match
        if note.voiceId != "cp" or (note.startTick, note.durationTicks) != (slot["startTick"], slot["durationTicks"]) or index in cp_by_index:
            findings.add("input_format", [note], "声部・開始位置・長さ・重複のいずれかが指定された音符枠と異なります。", "保持音は1つの長い音符です。課題の枠どおりに入力してください。")
        else:
            cp_by_index[index] = note
    if findings.issues:
        return findings.result("invalid")
    for index, slot in enumerate(exercise["noteSlots"]):
        if index not in cp_by_index:
            tick = slot["startTick"]
            findings.add("missing_note", [Note.model_validate(exercise["cantus"][tick // MEASURE_TICKS])], "指定された音符枠が未入力です。", "この枠に1音入力してください。冒頭の固定休符には入力不要です。", ticks=[tick], related_ids=[f"{exercise['id']}-cp-{index}"])
    assess_species_music(exercise, cp_by_index, findings)
    return findings.result("complete" if len(cp_by_index) == len(expected) else "incomplete")
