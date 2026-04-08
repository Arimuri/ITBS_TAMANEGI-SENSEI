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
You are a composition coach specialising in jazz, fusion, city pop and gospel.
You are reviewing a piece for the composer. They care about:
- Identifying *unintentional* harmonic problems (semitone clashes, voice
  crossings that obscure the line, parallel motion that flattens the texture).
- Distinguishing genuine mistakes from idiomatic jazz/fusion choices that
  *look* like classical violations but are intentional (parallel fifths in
  a fusion comp, chromatic tension in a bebop line, voicings that briefly
  cross to set up a melodic hand-off).
- Concrete fixes expressed in note names, not abstract theory rules.

When you respond:
1. For each issue, decide whether it is likely intentional or worth fixing,
   and *say so explicitly*.
2. If you suggest a fix, give it in pitch names (e.g. "change F#2 in Epiano
   to F2 on beat 3.5").
3. Describe how the fix would sound in one short sentence.
4. Use Studio One pitch names (middle C = C3) since that's how the composer
   labels their work.
5. Be specific. Avoid generic harmony advice.
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
    lines.append("# Score metadata")
    lines.append(f"- key: {md.key}")
    lines.append(f"- time signature: {md.time_signature}")
    lines.append(f"- tempo: {md.tempo_bpm} bpm")
    lines.append(f"- bars: {md.bar_count}")
    lines.append(f"- parts: {', '.join(md.part_names)}")
    lines.append("")

    if not result.issues:
        lines.append("No rule-based issues were detected. ")
        lines.append("Please give a brief overall harmonic impression of the piece below.")
        lines.append("")
        lines.append("# Slices (full)")
        for sl in result.slices:
            lines.append(_format_slice(sl))
        return "\n".join(lines)

    lines.append(f"# Detected issues ({len(result.issues)})")
    for idx, iss in enumerate(result.issues, 1):
        lines.append("")
        lines.append(f"## Issue {idx}: {iss.rule_id} [{iss.severity}]")
        lines.append(f"- bar{iss.bar} beat{iss.beat_in_bar:.2f}")
        lines.append(f"- description: {iss.description}")
        if iss.affected_parts:
            lines.append(f"- affected parts: {', '.join(iss.affected_parts)}")
        if iss.context:
            lines.append(f"- context: {iss.context}")
        nearby = _slices_near(result.slices, iss)
        if nearby:
            lines.append("- nearby slices:")
            for sl in nearby:
                lines.append(_format_slice(sl))

    lines.append("")
    lines.append("# Output format")
    lines.append("For each issue above, write a numbered section with:")
    lines.append("1. Verdict: intentional / fix recommended / minor")
    lines.append("2. Why it sounds that way")
    lines.append("3. Concrete fix in pitch names (if recommended)")
    lines.append("4. How the fix would sound")
    return "\n".join(lines)
