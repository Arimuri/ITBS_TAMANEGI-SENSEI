import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { SetStateAction } from 'react';
import { ArrowLeft, ArrowRight, BookOpen, Check, ChevronDown, ChevronRight, CircleHelp, Headphones, History, Layers3, Music2, PanelLeftClose, Play, Redo2, Send, Settings2, ShieldCheck, Square, Trash2, Undo2, Volume2, VolumeX } from 'lucide-react';
import { Player } from './audio';
import PianoRoll from './PianoRoll';
import Score from './Score';
import { useHistorySync } from './useHistorySync';
import { historyRecords, mergeHistory } from './sync';
import { edit, freshDraft, isStale, latestSubmission, midi, midiLabel, newAttempt, noteSlots, parseStore, pitchName, positionLabel, putNote, restoreAttempt, STORAGE_KEY } from './model';
import type { Draft, Editor, EditorAction, Exercise, Grade, Note, Pitch, Profile, Store, SubmissionRecord } from './model';

type DraftUpdate = Draft | ((draft: Draft) => Draft);
function initialStore(): Store { try { return parseStore(localStorage.getItem(STORAGE_KEY)); } catch { return { version: 1, drafts: {} }; } }
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}api/${path}`, init);
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(typeof body.detail === 'string' ? body.detail : `API エラー (${response.status})`); }
  return response.json();
}
export default function App() {
  const [store, setStore] = useState(initialStore);
  const currentStore = useRef(store); currentStore.current = store;
  // Only this tab's own actions may replace the drafts saved in localStorage.
  // History arriving from other tabs or the server is added to the stored
  // snapshot without touching whichever tab's active answer is saved there.
  // Starting at 1 persists the loaded snapshot once on mount, so the key exists
  // (and old-format data is normalised) before any other tab or sync touches it.
  const localEdits = useRef(1);
  const persistedEdits = useRef(0);
  const change = useCallback((next: SetStateAction<Store>) => { localEdits.current += 1; setStore(next); }, []);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [profiles, setProfiles] = useState<Record<string, Profile>>({});
  const historySync = useHistorySync(store, setStore);
  const [error, setError] = useState('');
  const [saveError, setSaveError] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  useEffect(() => { let alive = true; api<Exercise[]>('exercises').then(list => {
    if (!alive) return;
    setExercises(list);
    setStore(s => { const selectedExerciseId = list.some(e => e.id === s.selectedExerciseId) ? s.selectedExerciseId! : list[0]?.id; return { ...s, selectedExerciseId, drafts: { ...s.drafts, ...Object.fromEntries(list.map(e => [e.id, s.drafts[e.id] ?? freshDraft()])) } }; });
  }).catch(err => { if (alive) setError(err.message); }); return () => { alive = false; }; }, []);
  useEffect(() => {
    try {
      const stored = parseStore(localStorage.getItem(STORAGE_KEY));
      if (localEdits.current !== persistedEdits.current) {
        // Another tab may have submitted since this tab last rendered. Merge its
        // immutable history before writing, without replacing this tab's draft.
        persistedEdits.current = localEdits.current;
        const incoming = historyRecords(stored);
        const merged = mergeHistory(store, incoming);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
        if (merged !== store) setStore(current => mergeHistory(current, incoming));
      } else {
        // Nothing was edited here: only add records that storage lacks.
        const repaired = mergeHistory(stored, historyRecords(store));
        if (repaired !== stored) localStorage.setItem(STORAGE_KEY, JSON.stringify(repaired));
      }
      setSaveError(false);
    } catch { setSaveError(true); }
  }, [store]);
  useEffect(() => {
    const receive = (event: StorageEvent) => {
      if (event.storageArea !== localStorage || event.key !== STORAGE_KEY || !event.newValue) return;
      try {
        const stored = parseStore(localStorage.getItem(STORAGE_KEY));
        // Include the event itself: another write may already have replaced it.
        const incoming = [...historyRecords(parseStore(event.newValue)), ...historyRecords(stored)];
        const merged = mergeHistory(currentStore.current, incoming);
        if (merged !== currentStore.current) setStore(current => mergeHistory(current, incoming));
        // Older app tabs can still write a snapshot lacking newer submissions.
        // Put them back without replacing that tab's active answer.
        const repaired = mergeHistory(stored, historyRecords(merged));
        if (repaired !== stored) localStorage.setItem(STORAGE_KEY, JSON.stringify(repaired));
        setSaveError(false);
      } catch { setSaveError(true); }
    };
    window.addEventListener('storage', receive);
    return () => window.removeEventListener('storage', receive);
  }, []);
  const selected = exercises.find(e => e.id === store.selectedExerciseId);
  const profileVersion = selected?.ruleProfileVersion;
  const profile = profileVersion ? profiles[profileVersion] : undefined;
  useEffect(() => {
    if (!profileVersion || profiles[profileVersion]) return;
    let alive = true;
    api<Profile>(`profile?version=${encodeURIComponent(profileVersion)}`).then(value => { if (alive) setProfiles(old => ({ ...old, [profileVersion]: value })); }).catch(err => { if (alive) setError(err.message); });
    return () => { alive = false; };
  }, [profileVersion, profiles]);
  const speciesLabels = ['1音 対 1音', '2音 対 1音', '4音 対 1音', '掛留と解決', '固定リズムの華麗対位法'];
  const totalSubmissions = Object.values(store.drafts).reduce((count, d) => count + d.submissions.length, 0);
  const completed = exercises.filter(e => store.drafts[e.id]?.submissions.some(s => s.result.passed)).length;
  return <div className={`app ${sidebarOpen ? '' : 'sidebar-hidden'}`}>
    <aside className="sidebar">
      <a className="brand" href="#"><span className="brand-mark"><Music2 size={20}/></span><span>たまねぎ先生<small>COMPOSITION WORKSPACE</small></span></a>
      <div className="workspace-name"><span className="avatar">itb</span><span>in the blue shirt<small>Personal workspace</small></span><ChevronDown size={14}/></div>
      <div className="nav-label">LEARN & PRACTICE</div>
      <div className="active-nav"><Layers3 size={16}/> 対位法トレーナー <span className="tiny-dot"/></div>
      <nav className="species-nav" aria-label="対位法の種類">{[1, 2, 3, 4, 5].map(species => <button key={species} className={selected?.species === species ? 'active' : ''} disabled={!exercises.some(e => e.species === species)} onClick={() => { const first = exercises.find(e => e.species === species); if (first) change(s => ({ ...s, selectedExerciseId: first.id })); }}>第{species}種</button>)}</nav>
      <div className="course-label">第{selected?.species ?? 1}種 <span>{speciesLabels[(selected?.species ?? 1) - 1]}</span></div>
      <div className="exercise-list">{exercises.filter(e => e.species === (selected?.species ?? 1)).map((exercise, i) => {
        const passed = store.drafts[exercise.id]?.submissions.some(s => s.result.passed);
        return <button className={`exercise-link ${selected?.id === exercise.id ? 'active' : ''}`} key={exercise.id} onClick={() => change(s => ({ ...s, selectedExerciseId: exercise.id }))}><span className={`exercise-number ${passed ? 'done' : ''}`}>{passed ? <Check size={14}/> : String(i + 1).padStart(2, '0')}</span><span>{exercise.title}<small>{exercise.tonic} · {exercise.position === 'above' ? '上声に書く' : '下声に書く'} · {exercise.cantus.length}小節</small></span>{selected?.id === exercise.id && <ChevronRight size={14}/>}</button>;
      })}</div>
      <div className="sidebar-bottom"><div className="practice-card"><div><span>積み重ねた練習</span><span className={`badge sync-${historySync.status}`}>{historySync.status === 'synced' ? 'SYNCED' : historySync.status === 'syncing' || historySync.status === 'checking' ? 'SYNCING' : 'LOCAL'}</span></div><strong>{totalSubmissions}<small> 回の提出</small></strong><div className="progress-track"><span style={{ width: `${exercises.length ? completed / exercises.length * 100 : 0}%` }}/></div><p>{completed} / {exercises.length} 課題で規則に適合</p></div><div className="sync-note sync-state" role="status"><ShieldCheck size={13}/><span>{historySync.message}</span></div><button className="sync-button" onClick={historySync.sync} disabled={historySync.status === 'syncing' || historySync.status === 'checking' || historySync.status === 'disabled'}>履歴を同期</button><p className="local-note">入力中の回答は、この端末に自動保存</p></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><button className="icon-button sidebar-toggle" aria-label="課題一覧の表示切替" onClick={() => setSidebarOpen(!sidebarOpen)}><PanelLeftClose size={17}/></button><span className="crumb">Workspace</span><ChevronRight size={13}/><span>対位法トレーナー</span></div><span className="learning-mode"><span/> 学習モード</span></header>
      {saveError && <div role="alert" className="global-error">ブラウザへの保存ができません。現在の回答はこの画面を閉じるまで保持されます。ストレージの空き容量・設定を確認してください。</div>}
      {error ? <div role="alert" className="load-state"><CircleHelp/><h1>サーバーに接続できませんでした</h1><p>{error}</p><p>README の手順で API を起動し、ページを再読み込みしてください。</p><button onClick={() => location.reload()}>再読み込み</button></div> : selected && store.drafts[selected.id] && profile ? <Workspace key={selected.id} exercise={selected} exerciseIndex={exercises.indexOf(selected)} exerciseCount={exercises.length} profile={profile} draft={store.drafts[selected.id]} onChange={next => change(s => ({ ...s, drafts: { ...s.drafts, [selected.id]: typeof next === 'function' ? next(s.drafts[selected.id]) : next } }))} onNext={() => { const next = exercises[exercises.indexOf(selected) + 1]; if (next) change(s => ({ ...s, selectedExerciseId: next.id })); }}/> : <div className="load-state"><span className="loading-dot"/> ワークスペースを準備しています…</div>}
    </main>
  </div>;
}
function Workspace({ exercise, exerciseIndex, exerciseCount, profile, draft, onChange, onNext }: { exercise: Exercise; exerciseIndex: number; exerciseCount: number; profile: Profile; draft: Draft; onChange: (next: DraftUpdate) => void; onNext: () => void }) {
  const [editor, setEditor] = useState<Editor>({ notes: draft.notes, past: [], future: [] });
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState<'both' | 'roll' | 'score'>('both');
  const [sideTab, setSideTab] = useState<'feedback' | 'history'>('feedback');
  const [rulesOpen, setRulesOpen] = useState(false);
  const [studioOne, setStudioOne] = useState(false);
  const [tempo, setTempo] = useState(exercise.tempo);
  const [tempoInput, setTempoInput] = useState(String(exercise.tempo));
  const [muted, setMuted] = useState({ cf: false, cp: false });
  const [playTick, setPlayTick] = useState<number | null>(null);
  const [grading, setGrading] = useState(false);
  const [error, setError] = useState('');
  const [activeIssue, setActiveIssue] = useState<string>();
  const player = useRef(new Player());
  const notes = editor.notes;
  const slots = noteSlots(exercise);
  const brief = exercise.brief ?? { summary: exercise.objective, rhythm: '1小節に全音符を1つ置きます。', rules: ['定旋律と協和する音を選ぶ。', '完全5度・8度の連続を避ける。', '旋律を順次進行中心に、最後は順次進行で閉じる。'] };
  const latest = latestSubmission(draft);
  const stale = isStale(notes, latest) || !!latest && (latest.result.ruleProfileId !== exercise.ruleProfileId || latest.result.ruleProfileVersion !== exercise.ruleProfileVersion);
  const result = latest?.result;
  const problematic = useMemo(() => new Set(stale ? [] : result?.issues.flatMap(i => i.noteIds) ?? []), [stale, result]);
  const stop = useCallback(() => { player.current.stop(); setPlayTick(null); }, []);
  useEffect(() => { const p = player.current; const hidden = () => { if (document.hidden) { p.stop(); setPlayTick(null); } }; document.addEventListener('visibilitychange', hidden); return () => { void p.dispose(); document.removeEventListener('visibilitychange', hidden); }; }, []);
  const editorRef = useRef(editor);
  editorRef.current = editor;
  const apply = useCallback((action: EditorAction) => { stop(); const next = edit(editorRef.current, action); editorRef.current = next; setEditor(next); onChange(d => ({ ...d, notes: next.notes })); setActiveIssue(undefined); }, [onChange, stop]);
  useEffect(() => { if (!rulesOpen) return; const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') setRulesOpen(false); if (event.key === 'Tab') { const items = document.querySelectorAll<HTMLElement>('.rules-modal button, .rules-modal a'); const first = items[0], last = items[items.length - 1]; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); } } }; const previous = document.activeElement as HTMLElement | null; document.querySelector<HTMLElement>('.rules-modal button')?.focus(); window.addEventListener('keydown', handler); return () => { window.removeEventListener('keydown', handler); previous?.focus(); }; }, [rulesOpen]);
  const remove = () => apply({ type: 'set', notes: notes.filter(n => !selected.includes(n.id)) });
  const put = (index: number, pitch: Pitch) => apply({ type: 'set', notes: putNote(exercise, notes, index, pitch) });
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (rulesOpen || mode === 'score' || (event.target as HTMLElement).closest('input,select,textarea,[contenteditable="true"]')) return;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); apply({ type: event.shiftKey ? 'redo' : 'undo' }); }
      else if ((event.key === 'Delete' || event.key === 'Backspace') && selected.length) { event.preventDefault(); apply({ type: 'set', notes: notes.filter(n => !selected.includes(n.id)) }); }
      else if ((event.key === 'ArrowUp' || event.key === 'ArrowDown') && selected.length === 1) {
        const note = notes.find(n => n.id === selected[0]);
        if (!note) return;
        event.preventDefault();
        const pitches = [...exercise.allowedPitches].sort((a, b) => midi(a) - midi(b));
        const next = pitches[pitches.findIndex(p => midi(p) === midi(note.pitch)) + (event.key === 'ArrowUp' ? 1 : -1)];
        if (next) apply({ type: 'set', notes: putNote(exercise, notes, noteSlots(exercise).findIndex(n => n.startTick === note.startTick), next) });
      }
    };
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);
  }, [apply, exercise, notes, selected, rulesOpen, mode]);
  const select = (ids: string[]) => { setSelected(ids); setActiveIssue(undefined); };
  const focusIssue = (id: string, ids: string[]) => {
    setSelected(ids); setActiveIssue(id);
    requestAnimationFrame(() => {
      for (const surface of ['roll', 'staff']) {
        const elements = ids.map(note => document.querySelector<HTMLElement>(`[data-testid="${surface}-${CSS.escape(note)}"]`)).filter(Boolean);
        elements[0]?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      }
    });
  };
  const play = async () => {
    if (playTick !== null) { stop(); return; }
    setError('');
    try { await player.current.play([...exercise.cantus, ...notes], exercise.ppq, tempo, exercise.cantus.at(-1)!.startTick + exercise.cantus.at(-1)!.durationTicks, muted, setPlayTick); } catch { setError('音声を開始できませんでした。ブラウザの音声設定を確認してください。'); }
  };
  const submit = async () => {
    stop(); setGrading(true); setError('');
    const snapshot = structuredClone(notes), attemptId = draft.attemptId;
    try {
      const grade = await api<Grade>('grade', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ exerciseId: exercise.id, notes: snapshot, cantus: exercise.cantus, ruleProfileId: exercise.ruleProfileId, ruleProfileVersion: exercise.ruleProfileVersion }) });
      const record: SubmissionRecord = { id: crypto.randomUUID(), attemptId, submittedAt: new Date().toISOString(), notes: snapshot, result: grade, hints: {} };
      onChange(d => ({ ...d, submissions: [...d.submissions, record] })); setSideTab('feedback'); setSelected([]); setActiveIssue(undefined);
    } catch (err) { setError(err instanceof Error ? err.message : '採点に失敗しました'); } finally { setGrading(false); }
  };
  const reveal = (issueId: string, level: number) => { if (latest) onChange(d => ({ ...d, submissions: d.submissions.map(s => s.id === latest.id ? { ...s, hints: { ...s.hints, [issueId]: level } } : s) })); };
  const beginAttempt = (restored: Note[] = []) => { stop(); onChange(d => restored.length ? restoreAttempt(d, restored) : newAttempt(d)); const next = { notes: structuredClone(restored), past: [], future: [] }; editorRef.current = next; setEditor(next); setSelected([]); setActiveIssue(undefined); setSideTab('feedback'); };
  const startAttempt = () => beginAttempt();
  const completed = notes.length === slots.length;
  const selectedNote = [...notes, ...exercise.cantus].find(n => selected.includes(n.id));
  return <>
    <section className="lesson-heading"><div><div className="eyebrow">SPECIES {String(exercise.species).padStart(2, '0')} <span>·</span> COUNTERPOINT STUDY</div><h1>{exercise.title}</h1><p>{exercise.objective}</p><div className="lesson-tags"><span>第{exercise.species}種・2声</span><span>{exercise.tonic} / {exercise.mode}</span><span>{exercise.position === 'above' ? '上声' : '下声'}に対旋律</span><span>{exercise.cantus.length}小節 · 4/4</span></div></div><div className="lesson-number"><span>EXERCISE</span><strong>{String(exerciseIndex + 1).padStart(2, '0')}<small> / {String(exerciseCount).padStart(2, '0')}</small></strong><button className="text-button" onClick={() => setRulesOpen(true)}><BookOpen size={14}/> 適用ルールを見る <ArrowRight size={13}/></button></div></section>
    <section className="lesson-brief" aria-label="この課題の進め方"><div className="brief-intro"><span className="eyebrow">BEFORE YOU WRITE</span><h2>この課題の進め方</h2><p>{brief.summary}</p><div className="brief-rhythm"><Music2 size={16}/><span>{brief.rhythm}</span></div></div><div className="brief-rules"><h3>まず覚えるルール</h3><ul>{brief.rules.map(rule => <li key={rule}>{rule}</li>)}</ul></div></section>
    <div className="workspace-grid"><div className="editor-column">
      <div className="workspace-toolbar"><div className="view-tabs" aria-label="表示モード"><button className={mode === 'both' ? 'active' : ''} onClick={() => setMode('both')}><Layers3 size={13}/> 同期表示</button><button className={mode === 'roll' ? 'active' : ''} onClick={() => setMode('roll')}>ピアノロール</button><button className={mode === 'score' ? 'active' : ''} onClick={() => setMode('score')}>五線譜</button></div><span className="save-status"><Check size={12}/> 自動保存</span></div>
      {mode !== 'roll' && <section className="panel score-panel"><div className="panel-heading"><div><Music2 size={15}/><h2>五線譜</h2><span className="subtle-label">SCORE</span></div><span className="subtle-label">閲覧・選択のみ</span></div><Score exercise={exercise} notes={notes} selected={selected} problematic={problematic} playTick={playTick} onSelect={select}/><div className="score-footer"><span><span className="voice-dot cp"/> CP 対旋律</span><span><span className="voice-dot cf"/> CF 定旋律（固定）</span><span className="score-hint">音符をクリックして選択</span></div></section>}
      {mode === 'score' && <p className="view-notice">五線譜は閲覧・選択用です。入力や音高の変更はピアノロールへ切り替えて行います。</p>}
      {mode !== 'score' && <section className="panel roll-panel"><div className="panel-heading"><div><Settings2 size={15}/><h2>ピアノロール</h2><span className="subtle-label">PIANO ROLL</span></div><div className="edit-actions"><button className="icon-button" aria-label="元に戻す" title="元に戻す (⌘/Ctrl Z)" disabled={!editor.past.length} onClick={() => apply({ type: 'undo' })}><Undo2 size={15}/></button><button className="icon-button" aria-label="やり直す" title="やり直す (⌘/Ctrl Shift Z)" disabled={!editor.future.length} onClick={() => apply({ type: 'redo' })}><Redo2 size={15}/></button><span className="tool-divider"/><button className="icon-button" aria-label="選択した対旋律を削除" disabled={!notes.some(n => selected.includes(n.id))} onClick={remove}><Trash2 size={14}/></button></div></div><PianoRoll exercise={exercise} notes={notes} selected={selected} problematic={problematic} playTick={playTick} studioOne={studioOne} onSelect={select} onPut={put}/><div className="roll-footer"><span>クリックで入力 · ドラッグで音高変更 · Deleteで削除</span><span>音の位置と長さは課題で固定</span></div></section>}
      <section className="transport panel"><div className="transport-main"><button className={`play-button ${playTick !== null ? 'playing' : ''}`} aria-label={playTick !== null ? '停止' : '再生'} onClick={play}>{playTick !== null ? <Square size={16} fill="currentColor"/> : <Play size={18} fill="currentColor"/>}</button><button className="icon-button" aria-label="先頭に戻って停止" onClick={stop}><Square size={13}/></button><div className="time-display">{String(playTick === null ? 1 : Math.floor(playTick / (exercise.ppq * 4)) + 1).padStart(2, '0')}<span> : {String(playTick === null ? 1 : Math.floor(playTick / exercise.ppq) % 4 + 1).padStart(2, '0')}</span><small>BAR : BEAT</small></div><span className="tool-divider"/><label className="tempo"><input aria-label="テンポ" type="number" min="40" max="180" value={tempoInput} onChange={e => { stop(); setTempoInput(e.target.value); const value = Number(e.target.value); if (value >= 40 && value <= 180) setTempo(value); }} onBlur={() => { const value = Math.max(40, Math.min(180, Number(tempoInput) || tempo)); setTempo(value); setTempoInput(String(value)); }} onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); }}/><span>BPM</span></label></div><div className="voice-controls">{(['cf', 'cp'] as const).map(voice => <button key={voice} className={muted[voice] ? 'muted' : ''} aria-pressed={muted[voice]} onClick={() => { const value = !muted[voice]; setMuted({ ...muted, [voice]: value }); player.current.setMute(voice, value); }} aria-label={`${voice === 'cf' ? '定旋律' : '対旋律'}を${muted[voice] ? 'ミュート解除' : 'ミュート'}`}>{muted[voice] ? <VolumeX size={13}/> : <Volume2 size={13}/>}<span className={`voice-dot ${voice}`}/>{voice.toUpperCase()}</button>)}</div></section>
      <div className="editor-status"><span>{selected.length > 1 ? `${selected.length}音を選択中` : selectedNote ? `${selectedNote.voiceId.toUpperCase()} · ${pitchName(selectedNote.pitch, studioOne)} · MIDI ${midi(selectedNote.pitch)}${selectedNote.voiceId === 'cf' ? ' · 固定' : ''}` : `CPの入力範囲 ${midiLabel(exercise.range.min, studioOne)}–${midiLabel(exercise.range.max, studioOne)}（課題の調の音のみ）`}</span><label><input type="checkbox" checked={studioOne} onChange={e => setStudioOne(e.target.checked)}/> Studio One音名 <span title="MIDI 60 は標準表記 C4、Studio One 表記 C3。音高・楽譜・再生は同じです。">ⓘ</span></label></div>
      <div className="learning-tip"><Headphones size={19}/><div><strong>2つの声部を、ひとつずつ聴く。</strong><p>CF / CP のミュートを切り替えて、旋律の流れと2声の関係を確かめましょう。</p></div></div>
    </div>
    <aside className="feedback-column"><section className="panel feedback-panel"><div className="feedback-tabs"><button className={sideTab === 'feedback' ? 'active' : ''} onClick={() => setSideTab('feedback')}><ShieldCheck size={15}/> 添削</button><button className={sideTab === 'history' ? 'active' : ''} onClick={() => setSideTab('history')}><History size={14}/> 履歴 <span>{draft.submissions.length}</span></button></div>
      {sideTab === 'feedback' ? <>
        <div className="submission-progress"><div><span>回答の入力</span><strong>{notes.length}<small> / {slots.length}</small></strong></div><div className="slot-progress">{slots.map(n => <span key={n.startTick} className={notes.some(note => note.startTick === n.startTick) ? 'filled' : ''}/>)}</div><p>{completed ? exercise.species === 1 ? '全小節の入力が揃いました。' : 'すべての入力枠が揃いました。' : `あと ${slots.length - notes.length} 音。途中でも入力状態を確認できます。`}</p><button className="submit-button" disabled={grading} onClick={submit}><Send size={15}/>{grading ? '確認しています…' : latest ? '修正して再提出' : '提出して添削を受ける'}<ArrowRight size={14}/></button></div>
        {error && <p className="error-message" role="alert">{error}</p>}
        {!latest ? <div className="empty-feedback"><span className="feedback-icon"><BookOpen size={25}/></span><h3>まずは、あなたの旋律を。</h3><p>定旋律を聴き、{exercise.position === 'above' ? '上声' : '下声'}に表示された入力枠ごとに音を置いてみましょう。</p><div className="quiet-rule"/><p className="muted-text">提出すると、問題のある音と理由が<br/>ここに表示されます。</p><span className="learning-pill">正解の音を先に見せない学習モード</span></div> : <div className="grade-results" data-testid="grade-results">
          {stale && <div className="stale-banner" role="status">変更前の結果です。現在の回答を再提出してください。</div>}
          <div className={`grade-summary ${result!.passed ? 'passed' : ''}`}><span className="eyebrow">{stale ? 'PREVIOUS SUBMISSION' : 'LATEST SUBMISSION'}</span><h3>{result!.assessmentStatus === 'invalid' ? '入力条件を確認してください' : result!.assessmentStatus === 'incomplete' ? 'まだ入力が揃っていません' : result!.passed ? '今回の規則に適合しています' : '声部の進行を見直しましょう'}</h3><div className="result-counts"><span><b>{result!.hardViolationCount}</b> 違反</span><span><b>{result!.warningCount}</b> 警告</span></div>{result!.passed && <p>規則への適合を確認しました。音楽の価値を点数化する評価ではありません。</p>}</div>
          <div className="issues">{result!.issues.map(issue => {
            const level = latest.hints?.[issue.id] ?? 0;
            return <div key={issue.id} className={`issue ${activeIssue === issue.id ? 'active' : ''}`}><button className="issue-select" onClick={() => focusIssue(issue.id, issue.noteIds)} aria-label={`指摘を選択: ${issue.message}`}><div><span className={`severity ${issue.severity}`}>{issue.severity === 'error' ? '違反' : issue.severity === 'warning' ? '警告' : '確認'}</span><span className="issue-location">{[...new Set(issue.locations.map(l => `${l.measure}小節 ${l.beat}拍`))].join('・')}</span><ChevronRight size={13}/></div><strong>{issue.message}</strong><span className="rule-id">{profile.rules.find(r => r.id === issue.ruleId)?.title ?? issue.ruleId}</span></button>{level > 0 && <p className="issue-explanation">{issue.explanation}</p>}{level > 1 && <div className="issue-hint"><CircleHelp size={13}/><p>{issue.hint}</p></div>}{level < 2 && <button className="hint-button" onClick={() => reveal(issue.id, level + 1)}>{level === 0 ? '理由を読む' : '考えるヒントを見る'} <ChevronDown size={12}/></button>}</div>;
          })}</div><div className="result-meta">プロファイル v{result!.ruleProfileVersion} · エンジン {result!.engineVersion}<br/>{new Date(latest.submittedAt).toLocaleString('ja-JP')}</div>
        </div>}
      </> : <div className="history-content"><div className="history-intro"><h3>試行の記録</h3><p>提出済みの回答・結果・ヒントは端末間で同期します。履歴から再開すると新しい試行になり、現在の回答はこの端末に退避されます。</p><button className="secondary-button" onClick={startAttempt} disabled={grading}>空の回答で新しい試行 <ArrowRight size={13}/></button></div>{draft.submissions.length === 0 ? <p className="muted-text history-empty">まだ提出はありません。</p> : [...draft.submissions].reverse().map((record, index) => <HistoryCard key={record.id} record={record} number={draft.submissions.length - index} first={draft.submissions.find(s => s.attemptId === record.attemptId)?.id === record.id} studioOne={studioOne} ppq={exercise.ppq} onRestore={() => beginAttempt(record.notes)}/> )}{!!draft.savedAttempts?.length && <div className="saved-attempts"><h3>この端末に退避した回答</h3><p>新しい試行を始める直前の入力です。提出すると履歴も同期されます。</p>{[...draft.savedAttempts].reverse().map(attempt => <div className="saved-attempt" key={attempt.id}><span>{new Date(attempt.createdAt).toLocaleString('ja-JP', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}<small>{attempt.notes.length} 音 · {attempt.id.slice(0, 8)}</small></span><button className="text-button" onClick={() => beginAttempt(attempt.notes)}>再開 <ArrowRight size={12}/></button></div>)}</div>}</div>}
    </section><div className="profile-card"><BookOpen size={16}/><div><strong>Fux-inspired · 第{exercise.species}種</strong><p>この課題で採用する規則と<br/>判定条件を確認できます。</p><button className="text-button" onClick={() => setRulesOpen(true)}>規則と前提 <ArrowRight size={12}/></button></div></div>{exerciseIndex < exerciseCount - 1 && <button className="next-exercise" onClick={() => { stop(); onNext(); }}>次の課題へ <ArrowRight size={14}/></button>}</aside></div>
    <footer className="page-footer"><span>TAMANEGI SENSEI <span> / </span> COUNTERPOINT LAB</span><span><a href={`${import.meta.env.BASE_URL}licenses/NOTICE.txt`} target="_blank" rel="noreferrer">ライセンス</a> · 書く。聴く。読み解く。</span></footer>
    {rulesOpen && <div className="modal-backdrop" onClick={() => setRulesOpen(false)}><section className="rules-modal" role="dialog" aria-modal="true" aria-label="適用ルール" onClick={e => e.stopPropagation()}><div className="modal-heading"><div><span className="eyebrow">RULE PROFILE · v{profile.version}</span><h2>{profile.title}</h2></div><button className="icon-button" onClick={() => setRulesOpen(false)} aria-label="ルールを閉じる"><ArrowLeft size={20}/></button></div><p>{profile.description}</p><div className="rules-list">{profile.rules.map(rule => <div key={rule.id}><span className={`severity ${rule.severity}`}>{rule.severity === 'error' ? '違反' : rule.severity === 'warning' ? '警告' : '確認'}</span><h3>{rule.title}</h3><p>{rule.description}</p></div>)}</div><div className="sources"><h3>参照資料</h3>{profile.sources.map(source => <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>{source.title} ↗</a>)}</div><p className="notation-note">内部の音高は MIDI 60 = C4。Studio One 表記を有効にするとピアノロールの音名だけが C3 になります。入力できる音域・音階・リズムは課題で指定されています。{brief.rhythm}</p></section></div>}
  </>;
}
function HistoryCard({ record, number, first, studioOne, ppq, onRestore }: { record: SubmissionRecord; number: number; first: boolean; studioOne: boolean; ppq: number; onRestore: () => void }) {
  return <details className="history-card"><summary><span className={`history-dot ${record.result.passed ? 'passed' : ''}`}/><span><strong>提出 {String(number).padStart(2, '0')} <small>{first ? '初回提出' : '再提出'}</small></strong><time>{new Date(record.submittedAt).toLocaleString('ja-JP', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</time></span><ChevronDown size={13}/></summary><div className="history-detail"><p>{record.result.assessmentStatus === 'complete' ? '入力完了' : record.result.assessmentStatus === 'incomplete' ? '未入力あり' : '入力不備'} · {record.result.passed ? '規則に適合' : `違反 ${record.result.hardViolationCount} / 警告 ${record.result.warningCount}`}</p><p>ヒント利用 {Object.values(record.hints ?? {}).filter(v => v > 0).length}件</p><p className="snapshot-notes">{record.notes.map(n => `${positionLabel(n.startTick, ppq)}: ${pitchName(n.pitch, studioOne)} (${n.durationTicks / ppq}拍)`).join(' / ') || '未入力'}</p><p>試行 {record.attemptId.slice(0, 8)}<br/>プロファイル {record.result.ruleProfileId} v{record.result.ruleProfileVersion}<br/>エンジン {record.result.engineVersion}</p>{Object.entries(record.result.ruleCounts).map(([rule, count]) => <span className="history-rule" key={rule}>{rule}: {count}</span>)}<button className="secondary-button restore-button" onClick={onRestore}>この回答から新しい試行 <ArrowRight size={13}/></button></div></details>;
}
