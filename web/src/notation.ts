import { noteId, noteSlots } from './model';
import type { Exercise, Note } from './model';

export type ScoreSegment = { id?: string; note?: Note; startTick: number; durationTicks: number; duration: string; dotted: boolean; tieFrom: boolean; tieTo: boolean; required: boolean };
/** Rendering fragments are derived from one timed note; ties never create playback events. */
export function scoreSegments(exercise: Exercise, notes: Note[], voice: 'cf' | 'cp', measure: number): ScoreSegment[] {
  const ppq = exercise.ppq;
  const start = measure * ppq * 4, end = start + ppq * 4;
  const slots = voice === 'cf' ? exercise.cantus : noteSlots(exercise);
  const fragments: ScoreSegment[] = [];
  const lengths = [[ppq * 4, 'w', false], [ppq * 3, 'h', true], [ppq * 2, 'h', false], [ppq, 'q', false], [ppq / 2, '8', false]] as const;
  const add = (from: number, to: number, id?: string, note?: Note, sourceStart = from, sourceEnd = to) => {
    let cursor = from;
    while (cursor < to) {
      const duration = lengths.find(([ticks]) => ticks <= to - cursor);
      if (!duration) throw new Error('表示に対応していない音価です');
      fragments.push({ id, note, startTick: cursor, durationTicks: duration[0], duration: duration[1], dotted: duration[2], tieFrom: !!note && cursor > sourceStart, tieTo: !!note && cursor + duration[0] < sourceEnd, required: !!id });
      cursor += duration[0];
    }
  };
  let cursor = start;
  slots.forEach((slot, index) => {
    const from = Math.max(start, slot.startTick), to = Math.min(end, slot.startTick + slot.durationTicks);
    if (from >= to) return;
    if (from > cursor) add(cursor, from);
    const id = voice === 'cf' ? exercise.cantus[index].id : noteId(exercise, index);
    const actual = voice === 'cf' ? exercise.cantus[index] : notes.find(n => n.id === id);
    add(from, to, id, actual, slot.startTick, slot.startTick + slot.durationTicks);
    cursor = to;
  });
  if (cursor < end) add(cursor, end);
  return fragments;
}
