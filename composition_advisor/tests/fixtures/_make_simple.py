"""Generate a tiny C major I-V-vi-IV chord progression MIDI for smoke testing."""

from pathlib import Path

import music21 as m21

OUT_DIR = Path(__file__).parent


def make_chord_track() -> m21.stream.Part:
    part = m21.stream.Part()
    part.partName = "chord"
    progression = [
        ("C4 E4 G4", "C"),
        ("B3 D4 G4", "G"),
        ("A3 C4 E4", "Am"),
        ("F3 A3 C4", "F"),
    ]
    for pitches, _ in progression:
        ch = m21.chord.Chord(pitches.split(), quarterLength=4.0)
        part.append(ch)
    return part


def make_melody_track() -> m21.stream.Part:
    part = m21.stream.Part()
    part.partName = "melody"
    notes = ["E5", "G5", "F5", "A5", "E5", "C5", "F5", "A5"]
    for n in notes:
        part.append(m21.note.Note(n, quarterLength=2.0))
    return part


def make_bass_track() -> m21.stream.Part:
    part = m21.stream.Part()
    part.partName = "bass"
    roots = ["C2", "G2", "A2", "F2"]
    for r in roots:
        part.append(m21.note.Note(r, quarterLength=4.0))
    return part


def main() -> None:
    chord = make_chord_track()
    melody = make_melody_track()
    bass = make_bass_track()

    chord.write("midi", fp=OUT_DIR / "simple_chord.mid")
    melody.write("midi", fp=OUT_DIR / "simple_melody.mid")
    bass.write("midi", fp=OUT_DIR / "simple_bass.mid")
    print("wrote 3 fixture MIDI files to", OUT_DIR)


if __name__ == "__main__":
    main()
