import { describe, expect, it } from 'vitest';
import { edit, fingerprint, frequency, isStale, latestSubmission, midi, newAttempt, noteId, noteSlots, slotAtTick, restoreAttempt, parseStore, pitchName, putNote } from './model';
import type { Draft, Exercise, Grade, Pitch, SubmissionRecord } from './model';
const c: Pitch = { step: 'C', alter: 0, octave: 4 };
const d: Pitch = { step: 'D', alter: 0, octave: 4 };
const exercise: Exercise = { id: 'test', title: 'test', objective: '', difficulty: '', species: 1, keySignature: 'C', mode: 'major', tonic: 'C', position: 'above', timeSignature: '4/4', ppq: 480, tempo: 80, range: { min: 60, max: 62 }, allowedPitches: [c, d], cantus: [0, 1].map(i => ({ id: `test-cf-${i}`, voiceId: 'cf', startTick: i * 1920, durationTicks: 1920, pitch: c })), ruleProfileId: 'p', ruleProfileVersion: '1' };
const result: Grade = { exerciseId: 'test', ruleProfileId: 'p', ruleProfileVersion: '1', engineVersion: '1', assessmentStatus: 'incomplete', passed: false, hardViolationCount: 1, warningCount: 0, issues: [], ruleCounts: {} };
const notes = putNote(exercise, [], 0, c);
const record: SubmissionRecord = { id: 'submission', attemptId: 'attempt-1', submittedAt: '2026-01-01T00:00:00Z', notes, result, hints: { issue: 2 } };
const draft: Draft = { notes, attemptId: 'attempt-1', createdAt: '2026-01-01T00:00:00Z', submissions: [record] };
describe('shared musical representation', () => {
  it('uses scientific pitch C4 = MIDI60; Studio One changes only its label', () => { expect(midi(c)).toBe(60); expect(pitchName(c)).toBe('C4'); expect(pitchName(c, true)).toBe('C3'); expect(frequency(c)).toBeCloseTo(261.625565, 5); });
  it('replaces a slot with the same stable ID and preserves fixed cantus', () => { const before = structuredClone(exercise.cantus); const changed = putNote(exercise, notes, 0, d); expect(changed).toHaveLength(1); expect(changed[0].id).toBe(noteId(exercise, 0)); expect(changed[0].pitch).toEqual(d); expect(changed[0].durationTicks).toBe(1920); expect(exercise.cantus).toEqual(before); });
  it('rejects forbidden enharmonic spellings and nonexistent slots', () => { expect(putNote(exercise, notes, 0, { step: 'B', alter: 1, octave: 3 })).toBe(notes); expect(putNote(exercise, notes, 2, c)).toBe(notes); });
  it('derives time from cantus and returns ordered single-voice notes', () => { const secondFirst = putNote(exercise, [], 1, d); expect(putNote(exercise, secondFirst, 0, c).map(n => n.startTick)).toEqual([0, 1920]); });
  it('uses the exercise slots for half notes, quarter notes and cross-bar suspensions', () => {
    const rhythmic = { ...exercise, species: 4, noteSlots: [{ startTick: 960, durationTicks: 1920 }, { startTick: 2880, durationTicks: 960 }] };
    const entered = putNote(rhythmic, [], 0, d);
    expect(entered[0]).toMatchObject({ id: 'test-cp-0', startTick: 960, durationTicks: 1920 });
    expect(slotAtTick(rhythmic, 480)).toBe(-1);
    expect(slotAtTick(rhythmic, 2400)).toBe(0);
    expect(slotAtTick(rhythmic, 2880)).toBe(1);
    expect(noteSlots(exercise)).toEqual(exercise.cantus);
  });
  it('undoes and redoes replacement/deletion without changing IDs', () => { let editor = { notes, past: [] as typeof notes[], future: [] as typeof notes[] }; editor = edit(editor, { type: 'set', notes: putNote(exercise, notes, 0, d) }); editor = edit(editor, { type: 'set', notes: [] }); editor = edit(editor, { type: 'undo' }); expect(editor.notes[0].pitch).toEqual(d); editor = edit(editor, { type: 'undo' }); expect(editor.notes).toEqual(notes); editor = edit(editor, { type: 'redo' }); expect(editor.notes[0].id).toBe(notes[0].id); expect(editor.notes[0].pitch).toEqual(d); });
  it('does not add undo history for unchanged clicks', () => { const state = { notes, past: [], future: [] }; expect(edit(state, { type: 'set', notes: structuredClone(notes) })).toBe(state); });
});
describe('local learning records', () => {
  it('restores independent drafts, submission snapshots, hint levels and attempt IDs', () => { const stored = parseStore(JSON.stringify({ version: 1, selectedExerciseId: 'test', drafts: { test: draft, other: { ...draft, notes: [] } } })); expect(stored.drafts.test).toEqual(draft); expect(stored.drafts.other.notes).toEqual([]); expect(stored.selectedExerciseId).toBe('test'); });
  it('marks stale results after edit and reload, and recognizes exact undo', () => { const changed = putNote(exercise, notes, 0, d); const restored = parseStore(JSON.stringify({ version: 1, drafts: { test: { ...draft, notes: changed } } })); expect(isStale(restored.drafts.test.notes, latestSubmission(restored.drafts.test))).toBe(true); expect(isStale(notes, record)).toBe(false); expect(fingerprint(notes)).toBe(fingerprint(structuredClone(notes))); });
  it('keeps submitted answers when starting a separate attempt', () => { const next = newAttempt(draft); expect(next.attemptId).not.toBe(draft.attemptId); expect(next.notes).toEqual([]); expect(next.submissions[0]).toEqual(record); expect(latestSubmission(next)).toBeUndefined(); });
  it('restores a submitted answer into a new attempt and preserves every unsent edit locally', () => {
    const changed = putNote(exercise, notes, 0, d);
    const restored = restoreAttempt({ ...draft, notes: changed }, record.notes);
    expect(restored.attemptId).not.toBe(draft.attemptId);
    expect(restored.notes).toEqual(record.notes);
    expect(restored.savedAttempts?.[0].notes).toEqual(changed);
    expect(restored.submissions).toEqual(draft.submissions);
    expect(latestSubmission(restored)).toBeUndefined();
    const reloaded = parseStore(JSON.stringify({ version: 1, drafts: { test: restored } }));
    expect(reloaded.drafts.test.savedAttempts).toEqual(restored.savedAttempts);
    const original = restoreAttempt(reloaded.drafts.test, restored.savedAttempts![0].notes);
    expect(original.notes).toEqual(changed);
    expect(original.savedAttempts).toHaveLength(2);
  });
  it('recovers from corrupt/unsupported storage without rendering malformed notes', () => { expect(parseStore('invalid').drafts).toEqual({}); expect(parseStore('{"version":2,"drafts":{}}').drafts).toEqual({}); expect(parseStore(JSON.stringify({ version: 1, drafts: { broken: { notes: [{ id: 'oops' }], attemptId: 'a', submissions: [] } } })).drafts).toEqual({}); });
});
