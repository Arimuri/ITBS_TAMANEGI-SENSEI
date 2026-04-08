"""Built-in Cantus Firmus presets, mostly transcribed from Fux's
Gradus ad Parnassum (1725) so the tutor has known-good melodies for
exercises.

Each preset stores Studio One pitch names. Use `to_part(name)` to get a
music21 Part object that can be written to MIDI / MusicXML.
"""

from __future__ import annotations

from dataclasses import dataclass

import music21 as m21

# Studio One: middle C = C3, music21 internal: middle C = C4. Convert when
# we instantiate the music21 Note.
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def studio_one_to_midi(name: str) -> int:
    """Parse 'C3', 'F#3', 'Bb2' (Studio One labelling) into a MIDI number."""
    name = name.strip().replace("♯", "#").replace("♭", "b")
    letter = name[0].upper()
    rest = name[1:]
    accidental = 0
    if rest.startswith("#"):
        accidental = 1
        rest = rest[1:]
    elif rest.startswith("b"):
        accidental = -1
        rest = rest[1:]
    octave = int(rest)
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[letter]
    # Studio One: C3 == MIDI 60. → midi = base + (octave + 2) * 12
    return base + accidental + (octave + 2) * 12


@dataclass
class CantusFirmusPreset:
    name: str
    key: str           # e.g. "D dorian", "C major"
    notes: list[str]   # Studio One pitch names
    description: str = ""

    def to_part(self, part_name: str = "cantus_firmus", quarter_length: float = 4.0) -> m21.stream.Part:
        part = m21.stream.Part()
        part.partName = part_name
        for n in self.notes:
            midi = studio_one_to_midi(n)
            part.append(m21.note.Note(midi, quarterLength=quarter_length))
        return part


# Selected from Fux's Gradus ad Parnassum, plus a couple of common modal
# study melodies. Pitch names are in Studio One labelling (middle C = C3).
PRESETS: dict[str, CantusFirmusPreset] = {
    "fux_d_dorian": CantusFirmusPreset(
        name="fux_d_dorian",
        key="D dorian",
        notes=["D2", "F2", "E2", "D2", "G2", "F2", "A2", "G2", "F2", "E2", "D2"],
        description="Fux's first cantus firmus example, in D Dorian.",
    ),
    "fux_e_phrygian": CantusFirmusPreset(
        name="fux_e_phrygian",
        key="E phrygian",
        notes=["E2", "C2", "D2", "C2", "A1", "A2", "G2", "E2", "F2", "E2"],
        description="Fux Phrygian cantus.",
    ),
    "fux_f_lydian": CantusFirmusPreset(
        name="fux_f_lydian",
        key="F lydian",
        notes=["F2", "G2", "A2", "F2", "D2", "E2", "F2", "C3", "A2", "F2", "G2", "F2"],
        description="Fux Lydian cantus.",
    ),
    "fux_g_mixolydian": CantusFirmusPreset(
        name="fux_g_mixolydian",
        key="G mixolydian",
        notes=["G2", "C3", "B2", "G2", "C3", "E3", "D3", "G3", "E3", "C3", "D3", "B2", "A2", "G2"],
        description="Fux Mixolydian cantus.",
    ),
    "fux_a_aeolian": CantusFirmusPreset(
        name="fux_a_aeolian",
        key="A minor",
        notes=["A2", "C3", "B2", "D3", "C3", "E3", "F3", "E3", "D3", "C3", "B2", "A2"],
        description="Fux Aeolian (natural minor) cantus.",
    ),
    "c_major_short": CantusFirmusPreset(
        name="c_major_short",
        key="C major",
        notes=["C2", "D2", "E2", "G2", "F2", "E2", "D2", "C2"],
        description="Short C major cantus for quick smoke tests.",
    ),
}


def get(name: str) -> CantusFirmusPreset:
    if name not in PRESETS:
        raise KeyError(
            f"Unknown cantus firmus preset {name!r}. Available: {sorted(PRESETS)}"
        )
    return PRESETS[name]
