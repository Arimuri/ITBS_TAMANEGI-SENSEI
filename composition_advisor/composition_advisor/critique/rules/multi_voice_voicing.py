"""Voicing rules for 3-voice (sinfonia) and 4-voice (chorale) writing.

Two related rule modules live here:

three_voice_voicing
    - 各拍の3声部について、上声-中声 / 中声-下声 のインターバルが
      12度(オクターブ+5度 = 19半音)以内に収まっているか
    - 一定割合以上の拍で3声が同時に動いているとホモフォニー化
      (3声インベンションの趣旨に反する)

four_voice_voicing
    - ソプラノ-アルト・アルト-テノール間はオクターブ以内
    - テノール-バス間は12度まで
    - 全声部のリズムが完全に一致していると「コラール風」だが、
      ここでは情報として info を出すに留める

four_voice_doubling
    - 各和音について、リーディングトーン(導音、scale degree 7)が
      ダブっていないかを軽くチェックする
    - 完全な和声機能解析は行わない(複雑すぎ)、単純に「最頻 pitch class
      がスケール7度なら警告」程度
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import music21 as m21

from ...model.issue import Issue
from ...model.score import Score
from ...model.slice import Slice

THREE_RULE_ID = "three_voice_voicing"
THREE_INDEPENDENCE_ID = "three_voice_independence"
FOUR_VOICING_RULE_ID = "four_voice_voicing"
FOUR_DOUBLING_RULE_ID = "four_voice_doubling"


def _highest_in_part(sl: Slice, part: str):
    notes = [n for n in sl.notes if n.part == part]
    return max(notes, key=lambda n: n.pitch) if notes else None


def three_voice_voicing(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    """Check upper-middle and middle-lower distances stay within an octave + 5th."""
    if len(score.parts) < 3:
        return []
    parts = [p.name for p in score.parts[:3]]
    issues: list[Issue] = []
    for sl in slices:
        notes = [_highest_in_part(sl, p) for p in parts]
        if not all(notes):
            continue
        notes_sorted = sorted(notes, key=lambda n: n.pitch, reverse=True)  # high → low
        gap_top = notes_sorted[0].pitch - notes_sorted[1].pitch
        gap_bot = notes_sorted[1].pitch - notes_sorted[2].pitch
        if gap_top > 19:
            issues.append(_voicing_issue(sl, notes_sorted[:2], "上声-中声", gap_top, THREE_RULE_ID))
        if gap_bot > 19:
            issues.append(_voicing_issue(sl, notes_sorted[1:], "中声-下声", gap_bot, THREE_RULE_ID))
    return issues


def three_voice_independence(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    """Detect long stretches where all 3 voices move on the same beats."""
    if len(score.parts) < 3:
        return []
    parts = [p.name for p in score.parts[:3]]
    onset_sets = []
    for sl in slices:
        onset_parts = {n.part for n in sl.notes if n.start_beat <= sl.start_beat + 1e-3}
        onset_sets.append(onset_parts)

    # Count how many slices have all 3 parts onset together.
    same_count = sum(1 for s in onset_sets if all(p in s for p in parts))
    if not onset_sets:
        return []
    ratio = same_count / len(onset_sets)
    issues: list[Issue] = []
    if ratio > 0.6 and len(onset_sets) >= 4:
        issues.append(
            Issue(
                bar=1,
                beat_in_bar=1.0,
                severity="info",
                rule_id=THREE_INDEPENDENCE_ID,
                description=(
                    f"3声が同時に発音している拍が全体の {ratio:.0%} を占めています。"
                    "3声インベンションでは各声部の独立したリズムが重要です。"
                ),
                affected_notes=[],
                affected_parts=parts,
                context={"ratio": ratio},
            )
        )
    return issues


def four_voice_voicing(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    """SATB voicing: SA / AT within an octave, TB within a 12th."""
    if len(score.parts) < 4:
        return []
    parts = [p.name for p in score.parts[:4]]  # 順序: S, A, T, B を想定
    issues: list[Issue] = []
    for sl in slices:
        s = _highest_in_part(sl, parts[0])
        a = _highest_in_part(sl, parts[1])
        t = _highest_in_part(sl, parts[2])
        b = _highest_in_part(sl, parts[3])
        if not all((s, a, t, b)):
            continue
        gap_sa = s.pitch - a.pitch
        gap_at = a.pitch - t.pitch
        gap_tb = t.pitch - b.pitch
        if gap_sa > 12:
            issues.append(_voicing_issue(sl, [s, a], "ソプラノ-アルト", gap_sa, FOUR_VOICING_RULE_ID))
        if gap_at > 12:
            issues.append(_voicing_issue(sl, [a, t], "アルト-テノール", gap_at, FOUR_VOICING_RULE_ID))
        if gap_tb > 19:
            issues.append(_voicing_issue(sl, [t, b], "テノール-バス", gap_tb, FOUR_VOICING_RULE_ID))
    return issues


def four_voice_doubling(
    score: Score, slices: list[Slice], params: dict[str, Any] | None = None
) -> list[Issue]:
    """Heuristic: warn when a slice's most frequent pitch class is the leading tone (7th of the key)."""
    if len(score.parts) < 4:
        return []
    key_name = score.metadata.key
    if not key_name:
        return []
    try:
        key = m21.key.Key(key_name.split()[0]) if " " in key_name else m21.key.Key(key_name)
        tonic_pc = key.tonic.pitchClass
    except Exception:
        return []
    leading_pc = (tonic_pc + 11) % 12  # major key: leading tone = tonic - 1

    issues: list[Issue] = []
    for sl in slices:
        if len(sl.notes) < 4:
            continue
        pcs = [n.pitch % 12 for n in sl.notes]
        counts = Counter(pcs)
        most_pc, most_n = counts.most_common(1)[0]
        if most_n >= 2 and most_pc == leading_pc:
            issues.append(
                Issue(
                    bar=sl.bar,
                    beat_in_bar=sl.beat_in_bar,
                    severity="warning",
                    rule_id=FOUR_DOUBLING_RULE_ID,
                    description=(
                        "リーディングトーン(導音)が重複しています。"
                        "コラール和声では導音は重複せず、必ず主音に解決させます。"
                    ),
                    affected_notes=[n for n in sl.notes if n.pitch % 12 == most_pc],
                    affected_parts=sorted({n.part for n in sl.notes if n.pitch % 12 == most_pc}),
                    context={"pc": most_pc, "kind": "leading_tone_doubling"},
                )
            )
    return issues


def _voicing_issue(sl: Slice, notes_pair: list, label: str, gap: int, rule_id: str) -> Issue:
    return Issue(
        bar=sl.bar,
        beat_in_bar=sl.beat_in_bar,
        severity="warning",
        rule_id=rule_id,
        description=(
            f"{label}間が{gap}半音空いています。"
            f"声部間隔を狭めるか中声を補うことを検討してください。"
        ),
        affected_notes=notes_pair,
        affected_parts=sorted({n.part for n in notes_pair}),
        context={"gap_semitones": gap, "label": label},
    )
