import { freshDraft } from './model';
import type { Store, SubmissionRecord } from './model';

// Canonical object order keeps Python/JS JSON encoders interoperable.
export function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`).join(',')}}`;
  return JSON.stringify(value);
}
export const historyRecords = (store: Store): SubmissionRecord[] => Object.values(store.drafts).flatMap(d => d.submissions).sort((a, b) => a.submittedAt.localeCompare(b.submittedAt) || a.id.localeCompare(b.id));
export function mergeRecord(local: SubmissionRecord, remote: SubmissionRecord): SubmissionRecord {
  const { hints: localHints, ...localCore } = local;
  const { hints: remoteHints, ...remoteCore } = remote;
  if (canonical(localCore) !== canonical(remoteCore)) throw new Error('同じ履歴IDに異なる回答があります。端末の履歴は保持されています。');
  const hints = { ...localHints };
  for (const [key, level] of Object.entries(remoteHints)) hints[key] = Math.max(hints[key] ?? 0, level);
  return canonical(hints) === canonical(localHints) ? local : { ...local, hints };
}
export function mergeHistory(store: Store, records: SubmissionRecord[]): Store {
  let drafts = store.drafts;
  for (const record of records) {
    const exerciseId = record.result.exerciseId;
    const draft = drafts[exerciseId] ?? freshDraft();
    const existing = draft.submissions.find(s => s.id === record.id);
    const merged = existing ? mergeRecord(existing, record) : record;
    if (existing === merged) continue;
    const submissions = [...draft.submissions.filter(s => s.id !== record.id), merged]
      .sort((a, b) => a.submittedAt.localeCompare(b.submittedAt) || a.id.localeCompare(b.id));
    // The device's current answer, attempt and undo state are never replaced.
    drafts = { ...drafts, [exerciseId]: { ...draft, submissions } };
  }
  return drafts === store.drafts ? store : { ...store, drafts };
}

export type SyncPage = { enabled: boolean; records: SubmissionRecord[]; cursor: number; hasMore: boolean };
export async function historyRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}api/history/${path}`, {
    credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(20000),
    ...(body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : `履歴の同期に失敗しました (${response.status})`);
  }
  return response.json();
}
