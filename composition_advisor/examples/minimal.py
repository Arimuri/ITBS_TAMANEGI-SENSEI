"""Minimal end-to-end Phase 1 example.

Usage:
    uv run python examples/minimal.py path/to/melody.mid path/to/chord.mid ...
"""

from __future__ import annotations

import sys

from composition_advisor.analyze.chord_detector import detect_chords
from composition_advisor.analyze.degree_assigner import assign_degrees
from composition_advisor.analyze.key_detector import detect_key
from composition_advisor.io.midi_loader import load_midi_files


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: minimal.py file.mid [file.mid ...]", file=sys.stderr)
        sys.exit(1)

    score = load_midi_files(sys.argv[1:])
    key = detect_key(score)
    print(f"# Key: {key}")

    chords = detect_chords(score)
    chords = assign_degrees(chords, key)
    for c in chords:
        deg = c.degree or "?"
        print(f"bar{c.bar} beat{c.beat:.2f}: {c.chord_name} ({deg})")


if __name__ == "__main__":
    main()
