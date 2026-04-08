"""CLI entry point for composition_advisor."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import music21 as m21
import typer

from .analyze.chord_detector import detect_chords
from .analyze.degree_assigner import assign_degrees
from .analyze.key_detector import detect_key, parse_key
from .analyze.voice_extractor import extract_slices
from .critique.config import load_config
from .critique.runner import run_all as run_all_rules
from .io.midi_loader import load_midi_files
from .io.normalize import normalize_score
from .llm.claude_client import DEFAULT_MODEL, critique as llm_critique
from .llm.prompt_builder import build_user_prompt
from .model.issue import AnalysisResult
from .model.slice import Slice

app = typer.Typer(help="Compositional analysis tool for MIDI files.")


def _annotate_slice_degrees(slices: list[Slice], key: m21.key.Key) -> None:
    """Fill `detected_chord_degree` on each slice using music21's roman analysis."""
    for sl in slices:
        if not sl.notes:
            continue
        try:
            chord_obj = m21.chord.Chord([n.pitch for n in sl.notes])
            rn = m21.roman.romanNumeralFromChord(chord_obj, key)
            sl.detected_chord_degree = rn.romanNumeral
        except Exception:
            sl.detected_chord_degree = None


def _parse_bar_range(spec: str) -> tuple[int, int]:
    """Parse "4-8", "4", "4-", "-8" into an inclusive (lo, hi) bar pair."""
    spec = spec.strip()
    if "-" not in spec:
        n = int(spec)
        return (n, n)
    lo_s, hi_s = spec.split("-", 1)
    lo = int(lo_s) if lo_s else 1
    hi = int(hi_s) if hi_s else 10**9
    if lo > hi:
        raise ValueError(f"Invalid bar range '{spec}': lo > hi")
    return (lo, hi)


@app.command()
def analyze(
    files: list[Path] = typer.Argument(..., help="MIDI files to analyze."),
    key: Optional[str] = typer.Option(
        None, "--key", "-k",
        help='Key override (e.g. "C", "Am", "Bb"). If omitted, music21 estimates it.',
    ),
    output: str = typer.Option(
        "text", "--output", "-o",
        help="Output format: 'text' (default), 'json', or 'prompt' (show LLM prompt only).",
    ),
    llm: bool = typer.Option(
        False, "--llm",
        help="Send the analysis to Claude and print the natural-language critique.",
    ),
    model: str = typer.Option(
        DEFAULT_MODEL, "--model",
        help="Claude model id (used with --llm).",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to a yaml config that enables/disables individual rules.",
    ),
    bars: Optional[str] = typer.Option(
        None, "--bars",
        help="Restrict analysis to a bar range, e.g. '4-8', '4', '4-', '-8'.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Analyze MIDI files: detect chords/degrees and emit text or JSON."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    m21_score = load_midi_files(list(files))
    cfg = load_config(config) if config else None
    if cfg and cfg.key and not key:
        detected_key = parse_key(cfg.key)
    else:
        detected_key = parse_key(key) if key else detect_key(m21_score)

    bar_range = _parse_bar_range(bars) if bars else None

    # Anything beyond plain text output needs the full pipeline.
    if output in {"json", "prompt"} or llm:
        internal = normalize_score(m21_score, key=detected_key)
        slices = extract_slices(internal)
        if bar_range is not None:
            lo, hi = bar_range
            slices = [s for s in slices if lo <= s.bar <= hi]
        _annotate_slice_degrees(slices, detected_key)
        issues = run_all_rules(internal, slices, config=cfg)
        result = AnalysisResult(metadata=internal.metadata, slices=slices, issues=issues)

        if output == "json":
            typer.echo(result.model_dump_json(indent=2))
            return
        if output == "prompt":
            typer.echo(build_user_prompt(result))
            return
        if llm:
            critique_text = llm_critique(result, model=model)
            typer.echo(critique_text)
            return

    # Default text output: chords/degrees + a one-line summary per issue.
    typer.echo(f"# Key: {detected_key}")
    chords = detect_chords(m21_score)
    chords = assign_degrees(chords, detected_key)
    if bar_range is not None:
        lo, hi = bar_range
        chords = [c for c in chords if lo <= c.bar <= hi]
    for c in chords:
        deg = c.degree or "?"
        typer.echo(f"bar{c.bar} beat{c.beat:.2f}: {c.chord_name} ({deg})")

    internal = normalize_score(m21_score, key=detected_key)
    slices = extract_slices(internal)
    if bar_range is not None:
        lo, hi = bar_range
        slices = [s for s in slices if lo <= s.bar <= hi]
    issues = run_all_rules(internal, slices, config=cfg)
    if issues:
        typer.echo("")
        typer.echo(f"# Issues ({len(issues)})")
        for iss in issues:
            typer.echo(
                f"  [{iss.severity}] bar{iss.bar} beat{iss.beat_in_bar:.2f} "
                f"{iss.rule_id}: {iss.description}"
            )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
