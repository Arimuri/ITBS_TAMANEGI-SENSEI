"""Fixture that intentionally triggers bass_below and range_check.

- "bass" plays G3 (high for a bass)
- "piano" plays C2 (below the bass) — bass_below
- "trumpet" plays C2 (way below trumpet's practical range) — range_check
"""

from pathlib import Path

import music21 as m21

OUT_DIR = Path(__file__).parent


def part(name: str, pitches: list[str]) -> m21.stream.Part:
    p = m21.stream.Part()
    p.partName = name
    for n in pitches:
        p.append(m21.note.Note(n, quarterLength=4.0))
    return p


def main() -> None:
    bass = part("bass", ["G3", "G3"])
    piano = part("piano", ["C2", "C2"])
    trumpet = part("trumpet", ["C2", "C2"])
    bass.write("midi", fp=OUT_DIR / "fix_bass.mid")
    piano.write("midi", fp=OUT_DIR / "fix_piano.mid")
    trumpet.write("midi", fp=OUT_DIR / "fix_trumpet.mid")
    print("wrote fix-target fixtures to", OUT_DIR)


if __name__ == "__main__":
    main()
