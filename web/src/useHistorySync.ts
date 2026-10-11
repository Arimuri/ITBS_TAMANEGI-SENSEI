import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { Store, SubmissionRecord } from './model';
import { canonical, historyRecords, historyRequest, mergeHistory, mergeRecord } from './sync';
import type { SyncPage } from './sync';

type Status = 'checking' | 'syncing' | 'synced' | 'offline' | 'error' | 'disabled';
export function useHistorySync(store: Store, setStore: Dispatch<SetStateAction<Store>>) {
  const current = useRef(store); current.current = store;
  const alive = useRef(true);
  const running = useRef(false);
  const pending = useRef(false);
  const acknowledged = useRef(new Map<string, string>());
  const [state, setState] = useState<{ status: Status; message: string }>({ status: 'checking', message: '履歴の同期を確認中…' });
  const signature = useMemo(() => canonical(historyRecords(store)), [store]);
  const sync = useCallback(async () => {
    if (running.current) { pending.current = true; return; }
    if (!navigator.onLine) { setState({ status: 'offline', message: 'オフライン：履歴は端末に保存され、接続後に同期します。' }); return; }
    running.current = true;
    pending.current = false;
    try {
      const config = await historyRequest<{ enabled: boolean; message: string }>('status');
      if (!alive.current) return;
      if (!config.enabled) { setState({ status: 'disabled', message: config.message }); return; }
      setState({ status: 'syncing', message: '提出履歴を同期中…' });
      const snapshot = historyRecords(current.current);
      const uploads = snapshot.filter(r => acknowledged.current.get(r.id) !== canonical(r));
      // Upload small batches and download all pages. Full pulls recover even if
      // local storage was restored from an older backup; no cursor can skip data.
      const received = new Map<string, SubmissionRecord>();
      let cursor = 0;
      let more = true;
      let offset = 0;
      while (more || offset < uploads.length) {
        const batch = uploads.slice(offset, offset + 25);
        const page = await historyRequest<SyncPage>('sync', { records: batch, after: cursor });
        if (!alive.current) return;
        offset += batch.length;
        cursor = page.cursor;
        more = page.hasMore;
        for (const record of page.records) {
          const old = received.get(record.id);
          received.set(record.id, old ? mergeRecord(old, record) : record);
        }
      }
      const remote = [...received.values()];
      // Validate before invoking React's deferred updater so a conflict becomes
      // a visible sync error, never an exception that destroys the editor.
      mergeHistory(current.current, remote);
      for (const record of snapshot) acknowledged.current.set(record.id, canonical(record));
      for (const record of remote) acknowledged.current.set(record.id, canonical(record));
      setStore(s => mergeHistory(s, remote));
      setState({ status: 'synced', message: '提出履歴は同期済み。入力中の回答はこの端末に保存します。' });
    } catch (error) {
      if (alive.current) setState({ status: navigator.onLine ? 'error' : 'offline', message: `${error instanceof Error ? error.message : '履歴を同期できませんでした。'} 端末の履歴は保持し、再接続時に再試行します。` });
    } finally {
      running.current = false;
      if (pending.current && alive.current) { pending.current = false; void sync(); }
    }
  }, [setStore]);
  useEffect(() => {
    alive.current = true;
    void sync();
    const refresh = () => { if (!document.hidden) void sync(); };
    const offline = () => setState({ status: 'offline', message: 'オフライン：履歴は端末に保存され、接続後に同期します。' });
    window.addEventListener('online', refresh); window.addEventListener('focus', refresh); window.addEventListener('offline', offline);
    document.addEventListener('visibilitychange', refresh);
    const interval = window.setInterval(refresh, 60000);
    return () => { alive.current = false; window.clearInterval(interval); window.removeEventListener('online', refresh); window.removeEventListener('focus', refresh); window.removeEventListener('offline', offline); document.removeEventListener('visibilitychange', refresh); };
  }, [sync]);
  useEffect(() => {
    if (historyRecords(current.current).every(r => acknowledged.current.get(r.id) === canonical(r))) return;
    const timer = window.setTimeout(() => { void sync(); }, 700);
    return () => window.clearTimeout(timer);
  }, [signature, sync]);
  return { ...state, sync: () => { void sync(); } };
}
