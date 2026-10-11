import { describe, expect, it } from 'vitest';
import { freshDraft, parseStore } from './model';
import type { Store, SubmissionRecord } from './model';
import { canonical, historyRecords, mergeHistory } from './sync';

const record = (id: string): SubmissionRecord => ({ id, attemptId: `attempt-${id}`, submittedAt: '2026-10-10T01:00:00.000Z', notes: [{ id: 'x-cp-0', voiceId: 'cp', startTick: 0, durationTicks: 1920, pitch: { step: 'C', alter: 0, octave: 5 } }], hints: {}, result: { exerciseId: 'x', ruleProfileId: 'fux_inspired_two_voice_v1', ruleProfileVersion: '1', engineVersion: '1.0.0', assessmentStatus: 'complete', passed: true, hardViolationCount: 0, warningCount: 0, issues: [], ruleCounts: {} } });

describe('device history reconciliation', () => {
  it('migrates old local history additively without replacing the current answer or attempt', () => {
    const first = record('local'), second = record('remote');
    const draft = { ...freshDraft(), notes: first.notes, submissions: [first], savedAttempts: [{ id: 'saved', createdAt: '2026-10-10T00:00:00Z', notes: first.notes }] };
    const old = parseStore(JSON.stringify({ version: 1, selectedExerciseId: 'x', drafts: { x: draft } }));
    const merged = mergeHistory(old, [second]);
    expect(merged.drafts.x.notes).toBe(old.drafts.x.notes);
    expect(merged.drafts.x.attemptId).toBe(draft.attemptId);
    expect(merged.drafts.x.savedAttempts).toBe(old.drafts.x.savedAttempts);
    expect(merged.selectedExerciseId).toBe('x');
    expect(merged.drafts.x.submissions).toEqual([first, second]);
    expect(old.drafts.x.submissions).toEqual([first]);
    expect(parseStore(JSON.stringify(merged))).toEqual(merged);
  });
  it('makes repeated server responses a no-op and merges hint usage monotonically', () => {
    const first = record('first'); first.hints = { a: 2 };
    const store: Store = { version: 1, drafts: { x: { ...freshDraft(), submissions: [first] } } };
    const remote = { ...first, hints: { a: 1, b: 2 } };
    const merged = mergeHistory(store, [remote]);
    expect(merged.drafts.x.submissions[0].hints).toEqual({ a: 2, b: 2 });
    expect(mergeHistory(merged, [remote])).toBe(merged);
    expect(mergeHistory(merged, [first])).toBe(merged);
  });
  it('receives a new exercise with an empty local draft and preserves every old exercise', () => {
    const old = { ...freshDraft(), submissions: [record('first')] };
    const store: Store = { version: 1, drafts: { x: old } };
    const remote = record('second'); remote.result.exerciseId = 'species4-c-above';
    const merged = mergeHistory(store, [remote]);
    expect(merged.drafts.x).toBe(old);
    expect(merged.drafts['species4-c-above'].notes).toEqual([]);
    expect(historyRecords(merged)).toHaveLength(2);
  });
  it('refuses conflicting immutable snapshots without changing local data', () => {
    const first = record('first');
    const store: Store = { version: 1, drafts: { x: { ...freshDraft(), submissions: [first] } } };
    const snapshot = structuredClone(store);
    expect(() => mergeHistory(store, [{ ...first, attemptId: 'different' }])).toThrow('端末の履歴は保持');
    expect(store).toEqual(snapshot);
  });
  it('compares Python-encoded and JavaScript-encoded object keys consistently', () => {
    expect(canonical({ id: 'a', notes: [{ start: 1, pitch: 60 }] })).toBe(canonical({ notes: [{ pitch: 60, start: 1 }], id: 'a' }));
  });
});
