"""Generate two MIDI files for species 1 testing.

- counterpoint_good.mid: a textbook 1st-species line over the C-major short
  cantus from tutor/cantus_firmus.py.
- counterpoint_bad.mid: deliberately violates rules (parallel fifths,
  dissonance, melodic tritone) so the rules fire.
"""

from pathlib import Path

import music21 as m21

OUT_DIR = Path(__file__).parent

# Cantus firmus (matches PRESETS["c_major_short"]):
#   C2 D2 E2 G2 F2 E2 D2 C2  -> in scientific that's C3 D3 E3 G3 F3 E3 D3 C3
CF = ["C3", "D3", "E3", "G3", "F3", "E3", "D3", "C3"]


def part(name: str, pitches: list[str]) -> m21.stream.Part:
    p = m21.stream.Part()
    p.partName = name
    for n in pitches:
        p.append(m21.note.Note(n, quarterLength=4.0))
    return p


def main() -> None:
    cf_part = part("cantus_firmus", CF)
    cf_part.write("midi", fp=OUT_DIR / "species1_cf.mid")

    # Good: starts on octave, mostly stepwise, ends on unison
    good = part("counterpoint", ["C4", "A3", "G3", "E4", "F4", "G4", "F4", "C4"])
    good.write("midi", fp=OUT_DIR / "species1_good.mid")

    # Bad: parallel fifths C-G, D-A, E-B; melodic tritone F4->B3; ends on M2
    bad = part("counterpoint", ["G3", "A3", "B3", "F4", "B3", "F4", "G4", "D4"])
    bad.write("midi", fp=OUT_DIR / "species1_bad.mid")
    print("wrote species1 fixtures to", OUT_DIR)


if __name__ == "__main__":
    main()
