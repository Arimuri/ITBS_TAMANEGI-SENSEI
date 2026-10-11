export type Pitch = { step: 'C' | 'D' | 'E' | 'F' | 'G' | 'A' | 'B'; alter: -1 | 0 | 1; octave: number };
export type Note = { id: string; voiceId: 'cf' | 'cp'; startTick: number; durationTicks: number; pitch: Pitch };
export type NoteSlot = { startTick: number; durationTicks: number };
export type ExerciseBrief = { summary: string; rhythm: string; rules: string[] };
export type Exercise = { id: string; title: string; objective: string; difficulty: string; species: number; keySignature: 'C' | 'G' | 'F'; mode: string; tonic: string; position: 'above' | 'below'; timeSignature: string; ppq: number; tempo: number; range: { min: number; max: number }; allowedPitches: Pitch[]; noteSlots?: NoteSlot[]; brief?: ExerciseBrief; cantus: Note[]; ruleProfileId: string; ruleProfileVersion: string };
export type Issue = { id: string; ruleId: string; severity: 'error' | 'warning' | 'info'; noteIds: string[]; locations: { measure: number; beat: number }[]; message: string; explanation: string; hint: string };
export type Grade = { exerciseId: string; ruleProfileId: string; ruleProfileVersion: string; engineVersion: string; assessmentStatus: 'complete' | 'incomplete' | 'invalid'; passed: boolean; hardViolationCount: number; warningCount: number; issues: Issue[]; ruleCounts: Record<string, number> };
export type Profile = { id: string; version: string; title: string; description: string; rules: { id: string; title: string; severity: string; description: string }[]; sources: { title: string; url: string }[] };
const semitones = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
export const midi = (p: Pitch) => (p.octave + 1) * 12 + semitones[p.step] + p.alter;
export const frequency = (p: Pitch) => 440 * 2 ** ((midi(p) - 69) / 12);
export const pitchName = (p: Pitch, studioOne = false) => `${p.step}${p.alter === 1 ? '♯' : p.alter === -1 ? '♭' : ''}${p.octave - (studioOne ? 1 : 0)}`;
export function midiLabel(value: number, studioOne = false) { return `${['C', 'C♯', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'B'][value % 12]}${Math.floor(value / 12) - 1 - (studioOne ? 1 : 0)}`; }
export const noteSlots = (e: Exercise): NoteSlot[] => e.noteSlots ?? e.cantus;
export const slotAtTick = (e: Exercise, tick: number) => noteSlots(e).findIndex(slot => tick >= slot.startTick && tick < slot.startTick + slot.durationTicks);
export const positionLabel = (tick: number, ppq: number) => `${Math.floor(tick / (ppq * 4)) + 1}小節 ${tick % (ppq * 4) / ppq + 1}拍`;
export const noteId = (e: Exercise, index: number) => `${e.id}-cp-${index}`;
export function putNote(e: Exercise, notes: Note[], index: number, pitch: Pitch): Note[] {
  const slot = noteSlots(e)[index];
  if (!slot || !e.allowedPitches.some(p => p.step === pitch.step && p.alter === pitch.alter && p.octave === pitch.octave)) return notes;
  const note: Note = { id: noteId(e, index), voiceId: 'cp', startTick: slot.startTick, durationTicks: slot.durationTicks, pitch: { ...pitch } };
  return [...notes.filter(n => n.startTick !== slot.startTick), note].sort((a, b) => a.startTick - b.startTick);
}
export const fingerprint = (notes: Note[]) => JSON.stringify([...notes].sort((a, b) => a.startTick - b.startTick));
export type Editor = { notes: Note[]; past: Note[][]; future: Note[][] };
export type EditorAction = { type: 'set'; notes: Note[] } | { type: 'undo' | 'redo' };
export function edit(state: Editor, action: EditorAction): Editor {
  if (action.type === 'set') return fingerprint(state.notes) === fingerprint(action.notes) ? state : { notes: action.notes, past: [...state.past.slice(-99), state.notes], future: [] };
  if (action.type === 'undo' && state.past.length) return { notes: state.past.at(-1)!, past: state.past.slice(0, -1), future: [state.notes, ...state.future] };
  if (action.type === 'redo' && state.future.length) return { notes: state.future[0], past: [...state.past, state.notes], future: state.future.slice(1) };
  return state;
}
export type SubmissionRecord = { id: string; attemptId: string; submittedAt: string; notes: Note[]; result: Grade; hints: Record<string, number> };
export type SavedAttempt = { id: string; createdAt: string; notes: Note[] };
export type Draft = { savedAttempts?: SavedAttempt[]; notes: Note[]; attemptId: string; createdAt: string; submissions: SubmissionRecord[] };
export type Store = { version: 1; selectedExerciseId?: string; drafts: Record<string, Draft> };
export const STORAGE_KEY = 'tamanegi-counterpoint-v1';
export const freshDraft = (): Draft => ({ notes: [], attemptId: crypto.randomUUID(), createdAt: new Date().toISOString(), submissions: [] });
export function parseStore(raw: string | null): Store {
  const empty: Store = { version: 1, drafts: {} };
  if (!raw) return empty;
  try {
    const value = JSON.parse(raw);
    if (value.version !== 1 || !value.drafts || typeof value.drafts !== 'object') return empty;
    const drafts: Record<string, Draft> = {};
    for (const [id, draft] of Object.entries(value.drafts)) {
      const d = draft as Draft;
      if (typeof d.attemptId === 'string' && Array.isArray(d.notes) && d.notes.every(validNote) && Array.isArray(d.submissions) && d.submissions.every(s => typeof s.id === 'string' && typeof s.attemptId === 'string' && Array.isArray(s.notes) && s.notes.every(validNote) && !!s.result && Array.isArray(s.result.issues) && s.result.issues.every(i => Array.isArray(i.noteIds) && Array.isArray(i.locations)))) drafts[id] = { ...d, ...(d.savedAttempts !== undefined ? { savedAttempts: Array.isArray(d.savedAttempts) ? d.savedAttempts.filter(a => a && typeof a.id === 'string' && typeof a.createdAt === 'string' && Array.isArray(a.notes) && a.notes.every(validNote)) : [] } : {}) };
    }
    return { version: 1, selectedExerciseId: typeof value.selectedExerciseId === 'string' ? value.selectedExerciseId : undefined, drafts };
  } catch { return empty; }
}
function validNote(n: Note) { return n && typeof n.id === 'string' && n.voiceId === 'cp' && Number.isInteger(n.startTick) && Number.isInteger(n.durationTicks) && n.pitch && n.pitch.step in semitones && [-1, 0, 1].includes(n.pitch.alter) && Number.isInteger(n.pitch.octave); }
export const latestSubmission = (draft: Draft) => draft.submissions.filter(s => s.attemptId === draft.attemptId).at(-1);
export const isStale = (notes: Note[], submission: SubmissionRecord | undefined) => !!submission && fingerprint(notes) !== fingerprint(submission.notes);
function preserveCurrentAttempt(draft: Draft): SavedAttempt[] {
  const saved = draft.savedAttempts ?? [];
  if (!draft.notes.length) return saved;
  return [...saved.filter(attempt => attempt.id !== draft.attemptId), { id: draft.attemptId, createdAt: draft.createdAt, notes: structuredClone(draft.notes) }];
}
export function newAttempt(draft: Draft): Draft { return { ...freshDraft(), submissions: draft.submissions, savedAttempts: preserveCurrentAttempt(draft) }; }
export function restoreAttempt(draft: Draft, notes: Note[]): Draft { return { ...newAttempt(draft), notes: structuredClone(notes) }; }
