import { useEffect, useRef, useState } from 'react';
import { Accidental, Dot, Formatter, Renderer, Stave, StaveConnector, StaveNote, StaveTie, Voice } from 'vexflow/bravura';
import { midi, pitchName, positionLabel } from './model';
import type { Exercise, Note } from './model';
import { scoreSegments } from './notation';
import type { ScoreSegment } from './notation';

type Hit = { id: string; x: number; y: number; startTick: number; durationTicks: number; note?: Note; voice: 'cf' | 'cp'; tieFrom: boolean; tieTo: boolean };
type Props = { exercise: Exercise; notes: Note[]; selected: string[]; problematic: Set<string>; playTick: number | null; onSelect: (ids: string[]) => void };
export default function Score({ exercise, notes, selected, problematic, playTick, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const [hits, setHits] = useState<Hit[]>([]);
  const [error, setError] = useState('');
  const [fontsReady, setFontsReady] = useState(false);
  useEffect(() => { let alive = true; document.fonts.ready.then(() => { if (alive) setFontsReady(true); }); return () => { alive = false; }; }, []);
  const barWidth = exercise.species === 1 ? 105 : exercise.species === 2 || exercise.species === 4 ? 150 : 220;
  const lead = 112, width = exercise.cantus.length * barWidth + lead, height = 285;
  useEffect(() => {
    if (!container.current || !fontsReady) return;
    container.current.innerHTML = '';
    try {
      const renderer = new Renderer(container.current, Renderer.Backends.SVG);
      renderer.resize(width, height);
      const context = renderer.getContext();
      const found: Hit[] = [];
      const upper = exercise.position === 'above' ? 'cp' : 'cf';
      const voices = [upper, upper === 'cp' ? 'cf' : 'cp'] as const;
      const clefs: Record<string, string> = {};
      for (const voice of voices) { const values = (voice === 'cf' ? exercise.cantus.map(n => n.pitch) : exercise.allowedPitches).map(midi); clefs[voice] = (values.length ? values.reduce((a, b) => a + b, 0) / values.length : (exercise.range.min + exercise.range.max) / 2) < 60 ? 'bass' : 'treble'; }
      const previousFragments = new Map<string, StaveNote>();
      for (let i = 0; i < exercise.cantus.length; i++) {
        const x = i === 0 ? 15 : lead + i * barWidth;
        const staveWidth = i === 0 ? lead - 15 + barWidth : barWidth;
        const staves = voices.map((voice, row) => {
          const stave = new Stave(x, row === 0 ? 24 : 150, staveWidth);
          if (i === 0) stave.addClef(clefs[voice]).addKeySignature(exercise.keySignature).addTimeSignature('4/4');
          stave.setStyle({ strokeStyle: '#b9b3a5', fillStyle: '#8c887e' }).setContext(context).draw();
          return stave;
        });
        const startX = Math.max(...staves.map(s => s.getNoteStartX()));
        staves.forEach(s => s.setNoteStartX(startX));
        const rows = voices.map((voice, row) => {
          const segments = scoreSegments(exercise, notes, voice, i);
          const staveNotes = segments.map(fragment => {
            const actual = fragment.note;
            const key = actual ? `${actual.pitch.step.toLowerCase()}${actual.pitch.alter === 1 ? '#' : actual.pitch.alter === -1 ? 'b' : ''}/${actual.pitch.octave}` : clefs[voice] === 'bass' ? 'd/3' : 'b/4';
            const vn = new StaveNote({ clef: clefs[voice], keys: [key], duration: fragment.duration + (fragment.dotted ? 'd' : '') + (actual ? '' : 'r'), stemDirection: voice === upper ? 1 : -1 });
            if (fragment.dotted) Dot.buildAndAttach([vn], { all: true });
            if (actual) {
              const expected = exercise.keySignature === 'G' && actual.pitch.step === 'F' ? 1 : exercise.keySignature === 'F' && actual.pitch.step === 'B' ? -1 : 0;
              if (actual.pitch.alter !== expected && !fragment.tieFrom) vn.addModifier(new Accidental(actual.pitch.alter === 1 ? '#' : actual.pitch.alter === -1 ? 'b' : 'n'));
            }
            const color = !actual ? fragment.required ? '#b7b2a7' : '#6a746f' : selected.includes(actual.id) ? '#087569' : problematic.has(actual.id) ? '#b75530' : voice === 'cf' ? '#516a88' : '#273d38';
            vn.setStyle({ fillStyle: color, strokeStyle: color }).setStave(staves[row]);
            return vn;
          });
          return { segments, staveNotes, vexVoice: new Voice({ numBeats: 4, beatValue: 4 }).addTickables(staveNotes) };
        });
        const formatter = new Formatter();
        rows.forEach(row => formatter.joinVoices([row.vexVoice]));
        formatter.formatToStave(rows.map(row => row.vexVoice), staves[0]);
        rows.forEach((row, rowIndex) => {
          row.vexVoice.draw(context, staves[rowIndex]);
          row.segments.forEach((fragment: ScoreSegment, index: number) => {
            const vn = row.staveNotes[index];
            if (fragment.id) {
              const y = fragment.note ? vn.getYs()[0] : staves[rowIndex].getYForLine(2);
              found.push({ id: fragment.id, x: vn.getAbsoluteX(), y, startTick: fragment.startTick, durationTicks: fragment.durationTicks, note: fragment.note, voice: voices[rowIndex], tieFrom: fragment.tieFrom, tieTo: fragment.tieTo });
              if (fragment.note && fragment.tieFrom) {
                const first = previousFragments.get(fragment.id);
                if (first) new StaveTie({ firstNote: first, lastNote: vn, firstIndexes: [0], lastIndexes: [0] }).setContext(context).draw();
              }
              if (fragment.note) previousFragments.set(fragment.id, vn);
            }
          });
        });
        if (i === 0) new StaveConnector(staves[0], staves[1]).setType(StaveConnector.type.BRACKET).setContext(context).draw();
      }
      setHits(found); setError('');
    } catch (err) { setError(err instanceof Error ? err.message : '楽譜を表示できませんでした'); }
  }, [exercise, notes, selected, problematic, width, barWidth, fontsReady]);
  return <div className="score-scroll"><div className="score-sheet" style={{ width, height }}>
    <div className="score-label upper">{exercise.position === 'above' ? 'CP' : 'CF'}</div><div className="score-label lower">{exercise.position === 'above' ? 'CF' : 'CP'}</div>
    <div ref={container} aria-hidden="true" />
    <div className="score-overlay">{hits.map(hit => <button key={`${hit.id}-${hit.startTick}`} type="button" data-testid={`staff-${hit.id}`} data-note-id={hit.id} data-midi={hit.note ? midi(hit.note.pitch) : ''} data-start-tick={hit.startTick} data-duration-ticks={hit.durationTicks} data-tie-from={String(hit.tieFrom)} data-tie-to={String(hit.tieTo)} data-selected={selected.includes(hit.id) ? 'true' : 'false'} aria-label={`${hit.voice === 'cf' ? '定旋律' : '対旋律'} ${positionLabel(hit.startTick, exercise.ppq)} ${hit.note ? pitchName(hit.note.pitch) : '未入力'}${hit.tieFrom ? ' タイの継続' : ''}`} className={`score-hit ${selected.includes(hit.id) ? 'selected' : ''} ${problematic.has(hit.id) ? 'problem' : ''}`} style={{ left: hit.x - 10, top: hit.y - 17 }} onClick={() => onSelect([hit.id])} />)}</div>
    {exercise.cantus.map((note, i) => <span key={note.id} className={`score-bar ${playTick !== null && playTick >= note.startTick && playTick < note.startTick + note.durationTicks ? 'playing' : ''}`} style={{ left: i === 0 ? 110 : lead + i * barWidth + 35 }}>{i + 1}</span>)}
    {error && <p role="alert" className="score-error">楽譜の描画エラー: {error}</p>}
  </div></div>;
}
