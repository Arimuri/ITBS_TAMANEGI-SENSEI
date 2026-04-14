"""Build a Claude prompt from an AnalysisResult.

The prompt has two layers:
- A system prompt that frames Claude as a jazz/fusion-aware composition coach.
- A user prompt that summarises score metadata, the slices around each issue,
  and the issues themselves.

We deliberately avoid dumping every Slice — only the slices that contain or
neighbor an Issue are included, to keep token usage bounded for long pieces.
"""

from __future__ import annotations

from ..model.issue import AnalysisResult, Issue
from ..model.slice import Slice

SYSTEM_PROMPT = """\
あなたはジャズ、フュージョン、シティポップ、ゴスペルを専門とする
作曲コーチです。作曲家の楽曲をレビューしています。彼らが気にしているのは:
- 意図しない和声上の問題(半音衝突、旋律線を濁す声部交叉、テクスチャを
  平板にする平行進行など)を見つけること。
- 本物のミスと、ジャズ/フュージョン文脈で意図的に使われるイディオム
  (フュージョンのコンピングでの平行5度、ビバップラインのクロマティック
  テンション、メロディの受け渡しのために一瞬だけ交叉するボイシング等)を
  きちんと区別すること。
- 抽象的な理論用語ではなく、音名レベルでの具体的な修正案を出すこと。

返答するときは:
1. 各問題について「意図的に見える / 直したほうが良い / 軽微」を *明示的に* 述べる。
2. 修正案は音名で書く(例: 「Epiano の F#2 を beat 3.5 で F2 に変える」)。
3. その修正でどう響きが変わるかを1文で添える。
4. 音名は Studio One 表記(中央 C = C3)を使う。
5. 具体的に。一般論の和声アドバイスは避ける。

**必ず日本語で返答してください。**
"""


def _format_slice(sl: Slice) -> str:
    notes_str = ", ".join(
        f"{n.pitch_name} ({n.part})" for n in sorted(sl.notes, key=lambda x: x.pitch)
    )
    chord = sl.detected_chord or "?"
    deg = sl.detected_chord_degree or "?"
    return (
        f"  bar{sl.bar} beat{sl.beat_in_bar:.2f} dur{sl.duration:.2f} "
        f"[{chord} / {deg}] bass={sl.bass_note} notes=[{notes_str}]"
    )


def _slices_near(slices: list[Slice], issue: Issue, window: int = 1) -> list[Slice]:
    """Return slices in the same bar as the issue, plus `window` surrounding."""
    indices = [
        i for i, s in enumerate(slices)
        if s.bar == issue.bar and abs(s.beat_in_bar - issue.beat_in_bar) < 4
    ]
    if not indices:
        return []
    lo = max(0, min(indices) - window)
    hi = min(len(slices), max(indices) + window + 1)
    return slices[lo:hi]


def build_user_prompt(result: AnalysisResult) -> str:
    """Render an AnalysisResult into a single user-prompt string."""
    md = result.metadata
    lines: list[str] = []
    lines.append("# 楽曲メタデータ")
    lines.append(f"- キー: {md.key}")
    lines.append(f"- 拍子: {md.time_signature}")
    lines.append(f"- テンポ: {md.tempo_bpm} bpm")
    lines.append(f"- 小節数: {md.bar_count}")
    lines.append(f"- パート: {', '.join(md.part_names)}")
    lines.append("")

    # ---- プロンプトサイズ上限 ----
    # 大きい MIDI だと Slice 数が数千に膨れ上がり、Claude の入力上限を
    # 超えてしまう。Slice の全件ダンプは避け、Issue 周辺だけを含める。
    # Issue がゼロの場合も先頭の数十 Slice だけサンプルする。
    MAX_SLICES_NO_ISSUES = 40
    MAX_ISSUES_IN_PROMPT = 30

    if not result.issues:
        lines.append("ルールベースでは問題が検出されませんでした。")
        lines.append("以下のスライス情報(先頭抜粋)を見て、曲全体の和声的な印象を簡潔に書いてください。")
        lines.append("")
        sample = result.slices[:MAX_SLICES_NO_ISSUES]
        lines.append(f"# Slices(先頭 {len(sample)} 件 / 全 {len(result.slices)} 件)")
        for sl in sample:
            lines.append(_format_slice(sl))
        return "\n".join(lines)

    issues_to_show = result.issues[:MAX_ISSUES_IN_PROMPT]
    lines.append(f"# 検出された問題 ({len(result.issues)} 件中 {len(issues_to_show)} 件を表示)")
    for idx, iss in enumerate(issues_to_show, 1):
        lines.append("")
        lines.append(f"## 問題 {idx}: {iss.rule_id} [{iss.severity}]")
        lines.append(f"- 位置: bar{iss.bar} beat{iss.beat_in_bar:.2f}")
        lines.append(f"- 説明: {iss.description}")
        if iss.affected_parts:
            lines.append(f"- 関係するパート: {', '.join(iss.affected_parts)}")
        if iss.context:
            lines.append(f"- 補足情報: {iss.context}")
        nearby = _slices_near(result.slices, iss)
        if nearby:
            lines.append("- 周辺の slices:")
            for sl in nearby:
                lines.append(_format_slice(sl))

    lines.append("")
    lines.append("# 出力フォーマット")
    lines.append("上記の各問題について、次の構成で番号付きセクションを書いてください:")
    lines.append("1. 判定: 意図的 / 修正推奨 / 軽微")
    lines.append("2. なぜそう響くかの説明")
    lines.append("3. 具体的な修正案(音名で)")
    lines.append("4. 修正後にどう響くか")
    lines.append("")
    lines.append("**必ず日本語で書いてください。**")
    return "\n".join(lines)
