"""Generate a tiny intentionally-broken MIDI to exercise critique rules.

Two parts (whole notes), four bars:
- bar1->bar2: parallel fifth (treble C5->D5, lower F4->G4)
- bar3:       semitone clash (treble E5, lower F5)
- bar4:       voice crossing (treble drops to D5, lower rises to G5)
"""

from pathlib import Path

import music21 as m21

OUT_DIR = Path(__file__).parent


def make_part(name: str, notes: list[str]) -> m21.stream.Part:
    p = m21.stream.Part()
    p.partName = name
    for n in notes:
        p.append(m21.note.Note(n, quarterLength=4.0))
    return p


def main() -> None:
    treble = make_part("treble", ["C5", "D5", "E5", "D5"])
    lower = make_part("lower", ["F4", "G4", "F5", "G5"])
    treble.write("midi", fp=OUT_DIR / "clash_treble.mid")
    lower.write("midi", fp=OUT_DIR / "clash_lower.mid")
    print("wrote clash fixture MIDI files to", OUT_DIR)


if __name__ == "__main__":
    main()
