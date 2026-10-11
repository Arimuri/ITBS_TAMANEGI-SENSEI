import { describe, expect, it } from 'vitest';
import { scoreSegments } from './notation';
import { putNote } from './model';
import type { Exercise, Pitch } from './model';
const c: Pitch = { step: 'C', alter: 0, octave: 4 };
const base: Exercise = { id: 'score', title: '', objective: '', difficulty: '', species: 1, keySignature: 'C', mode: 'major', tonic: 'C', position: 'above', timeSignature: '4/4', ppq: 480, tempo: 80, range: { min: 60, max: 72 }, allowedPitches: [c], cantus: [0, 1].map(i => ({ id: `score-cf-${i}`, voiceId: 'cf', startTick: i * 1920, durationTicks: 1920, pitch: c })), ruleProfileId: 'p', ruleProfileVersion: '2' };
describe('notation derives durations and ties without changing musical notes', () => {
  it('keeps first-species whole notes and explicit input rests compatible', () => {
    expect(scoreSegments(base, [], 'cp', 0)).toMatchObject([{ id: 'score-cp-0', duration: 'w', required: true, tieFrom: false, tieTo: false }]);
    expect(scoreSegments(base, [], 'cf', 0)[0].note).toEqual(base.cantus[0]);
  });
  it('draws the correct number of half notes and quarter notes within a bar', () => {
    for (const ticks of [960, 480]) {
      const exercise = { ...base, noteSlots: Array.from({ length: 3840 / ticks }, (_, i) => ({ startTick: i * ticks, durationTicks: ticks })) };
      const fragments = scoreSegments(exercise, [], 'cp', 1);
      expect(fragments).toHaveLength(1920 / ticks);
      expect(fragments.reduce((sum, note) => sum + note.durationTicks, 0)).toBe(1920);
      expect(fragments.every(note => !note.tieFrom && note.required)).toBe(true);
    }
  });
  it('splits one held note across two bars with a leading rest and a shared stable ID', () => {
    const exercise = { ...base, species: 4, noteSlots: [{ startTick: 960, durationTicks: 1920 }, { startTick: 2880, durationTicks: 960 }] };
    const notes = putNote(exercise, [], 0, c);
    const first = scoreSegments(exercise, notes, 'cp', 0), next = scoreSegments(exercise, notes, 'cp', 1);
    expect(first[0]).toMatchObject({ startTick: 0, durationTicks: 960, required: false });
    expect(first[1]).toMatchObject({ id: notes[0].id, duration: 'h', tieTo: true, tieFrom: false });
    expect(next[0]).toMatchObject({ id: notes[0].id, duration: 'h', tieFrom: true, tieTo: false });
    expect([first[1], next[0]].reduce((sum, note) => sum + note.durationTicks, 0)).toBe(notes[0].durationTicks);
    expect(notes).toHaveLength(1);
  });
  it('retains dotted durations and fills only intentional gaps', () => {
    const exercise = { ...base, species: 5, noteSlots: [{ startTick: 0, durationTicks: 1440 }, { startTick: 1440, durationTicks: 480 }] };
    const fragments = scoreSegments(exercise, putNote(exercise, [], 0, c), 'cp', 0);
    expect(fragments).toMatchObject([{ duration: 'h', dotted: true, durationTicks: 1440 }, { duration: 'q', dotted: false, durationTicks: 480 }]);
    expect(scoreSegments(exercise, [], 'cp', 1)).toMatchObject([{ required: false, duration: 'w' }]);
  });
});
