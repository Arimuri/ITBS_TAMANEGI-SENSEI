import { useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { midi, midiLabel, noteId, noteSlots, pitchName, positionLabel, slotAtTick } from './model';
import type { Exercise, Note, Pitch } from './model';

type Props = { exercise: Exercise; notes: Note[]; selected: string[]; problematic: Set<string>; playTick: number | null; studioOne: boolean; onSelect: (ids: string[]) => void; onPut: (index: number, pitch: Pitch) => void };
const LEFT = 65, TOP = 29, ROW = 20;
export default function PianoRoll({ exercise, notes, selected, problematic, playTick, studioOne, onSelect, onPut }: Props) {
  const CELL = exercise.species === 1 ? 101 : exercise.species === 2 || exercise.species === 4 ? 148 : 196;
  const slots = noteSlots(exercise);
  const tickWidth = CELL / (exercise.ppq * 4);
  const svg = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<{ index: number; pitch: Pitch; startY: number; moved: boolean } | null>(null);
  const min = Math.min(exercise.range.min, ...exercise.cantus.map(n => midi(n.pitch))) - 1;
  const max = Math.max(exercise.range.max, ...exercise.cantus.map(n => midi(n.pitch))) + 1;
  const pitches = Array.from({ length: max - min + 1 }, (_, i) => max - i);
  const width = LEFT + exercise.cantus.length * CELL + 1;
  const height = TOP + pitches.length * ROW;
  const allowed = new Map(exercise.allowedPitches.map(p => [midi(p), p]));
  const pointer = (event: PointerEvent<SVGSVGElement>) => {
    const bounds = svg.current!.getBoundingClientRect();
    return { x: (event.clientX - bounds.left) * width / bounds.width, y: (event.clientY - bounds.top) * height / bounds.height };
  };
  const getPitch = (y: number) => { const value = max - Math.floor((y - TOP) / ROW); return [...exercise.allowedPitches].sort((a, b) => Math.abs(midi(a) - value) - Math.abs(midi(b) - value))[0]; };
  const down = (event: PointerEvent<SVGSVGElement>) => {
    if (event.button !== 0) return;
    const point = pointer(event);
    const target = (event.target as Element).closest('[data-note-id]');
    if (target?.getAttribute('data-voice') === 'cf') { onSelect([target.getAttribute('data-note-id')!]); return; }
    if (point.x < LEFT || point.y < TOP) return;
    const index = slotAtTick(exercise, (point.x - LEFT) / tickWidth);
    if (index < 0) return;
    const existing = notes.find(n => n.id === noteId(exercise, index));
    if (target && existing) {
      onSelect([existing.id]); setDrag({ index, pitch: existing.pitch, startY: point.y, moved: false }); svg.current!.setPointerCapture(event.pointerId);
    } else {
      const pitch = allowed.get(max - Math.floor((point.y - TOP) / ROW));
      if (pitch) { onPut(index, pitch); onSelect([noteId(exercise, index)]); }
    }
  };
  const move = (event: PointerEvent<SVGSVGElement>) => {
    if (!drag) return;
    const p = pointer(event);
    if (Math.abs(p.y - drag.startY) > 3 || drag.moved) setDrag({ ...drag, pitch: getPitch(p.y), moved: true });
  };
  const up = () => { if (drag?.moved) onPut(drag.index, drag.pitch); setDrag(null); };
  const displayedNotes = notes.map(n => drag && n.id === noteId(exercise, drag.index) ? { ...n, pitch: drag.pitch } : n);
  return <div className="roll-scroll" data-testid="piano-scroll"><svg ref={svg} className="piano-roll" role="group" aria-label="ピアノロール。クリックで入力、音符を上下にドラッグして移動" width={width} height={height} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={() => setDrag(null)}>
    <rect width={width} height={height} fill="#18212d" />
    {pitches.map((value, row) => <g key={value}>
      <rect x={LEFT} y={TOP + row * ROW} width={width - LEFT} height={ROW} fill={allowed.has(value) ? (value % 12 === 0 ? '#263546' : '#1f2b38') : '#18222e'} />
      <path d={`M${LEFT} ${TOP + row * ROW}H${width}`} stroke={value % 12 === 0 ? '#435164' : '#2d3948'} strokeWidth="0.5" />
      <rect x="0" y={TOP + row * ROW} width={LEFT - 1} height={ROW - 1} fill={[1, 3, 6, 8, 10].includes(value % 12) ? '#121a23' : '#c9d0d8'} />
      <text x="52" y={TOP + row * ROW + 13} textAnchor="end" fill={[1, 3, 6, 8, 10].includes(value % 12) ? '#9daec0' : '#354454'} fontSize="10">{midiLabel(value, studioOne)}</text>
    </g>)}
    {exercise.cantus.map((cf, index) => <g key={cf.id}>
      <text x={LEFT + index * CELL + 11} y="19" fontSize="11" fill="#8f9fb2">{String(index + 1).padStart(2, '0')}</text>
      <path d={`M${LEFT + index * CELL} ${TOP}V${height}`} stroke="#526071" strokeWidth="0.65" />
      {[1, 2, 3].map(beat => <path key={beat} d={`M${LEFT + index * CELL + beat * CELL / 4} ${TOP}V${height}`} stroke="#33404f" strokeWidth="0.4" />)}

    </g>)}
    {slots.map((slot, index) => <g key={index} pointerEvents="none">
      <path d={`M${LEFT + slot.startTick * tickWidth} ${TOP}V${height}`} stroke="#829991" strokeWidth="0.7" strokeDasharray="2 4"/>
      {!notes.some(n => n.id === noteId(exercise, index)) && <text x={LEFT + (slot.startTick + slot.durationTicks / 2) * tickWidth} y={height - 7} textAnchor="middle" fontSize="8" fill="#82978f">未入力</text>}
    </g>)}
    {slots[0]?.startTick > 0 && <g pointerEvents="none"><rect x={LEFT} y={TOP} width={slots[0].startTick * tickWidth} height={height - TOP} fill="#0c151f" opacity="0.42"/><text x={LEFT + slots[0].startTick * tickWidth / 2} y={height - 7} textAnchor="middle" fontSize="9" fill="#a2afbd">休符</text></g>}
    {[...exercise.cantus, ...displayedNotes].map(note => {
      const fixed = note.voiceId === 'cf';
      const active = selected.includes(note.id);
      const issue = problematic.has(note.id);
      const x = LEFT + note.startTick * tickWidth + (fixed ? 7 : 3), y = TOP + (max - midi(note.pitch)) * ROW + (fixed ? 6 : 2);
      return <g key={note.id} data-note-id={note.id} data-voice={note.voiceId} data-midi={midi(note.pitch)} data-start-tick={note.startTick} data-duration-ticks={note.durationTicks} data-selected={active ? 'true' : 'false'} data-testid={`roll-${note.id}`} role="button" tabIndex={0} aria-label={`${fixed ? '定旋律・固定' : '対旋律'} ${positionLabel(note.startTick, exercise.ppq)} ${pitchName(note.pitch, studioOne)}`} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect([note.id]); } }} className={`roll-note ${fixed ? 'fixed' : ''}`}>
        <rect x={x} y={y} width={Math.max(8, note.durationTicks * tickWidth - (fixed ? 13 : 9))} height={fixed ? 11 : 16} rx="3" fill={fixed ? '#668db9' : '#8ad3c6'} stroke={active ? '#ffffff' : issue ? '#f6ac85' : fixed ? '#80a6d3' : '#acecdf'} strokeWidth={active ? 2.5 : issue ? 2 : 0.6} />
        <text x={x + 6} y={y + (fixed ? 8.7 : 11.5)} fill={fixed ? '#e5effc' : '#173c38'} fontSize={fixed ? 8 : 9} pointerEvents="none">{fixed ? 'CF ' : note.durationTicks * tickWidth > 65 ? 'CP ' : ''}{pitchName(note.pitch, studioOne)}{issue ? ' !' : ''}</text>
      </g>;
    })}
    {playTick !== null && <g pointerEvents="none" data-testid="playhead"><path d={`M${LEFT + playTick / (exercise.ppq * 4) * CELL} 0V${height}`} stroke="#f4d69d" strokeWidth="2"/><path d={`M${LEFT + playTick / (exercise.ppq * 4) * CELL - 5} 0h10l-5 7z`} fill="#f4d69d"/></g>}
  </svg></div>;
}
