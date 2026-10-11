import { frequency } from './model';
import type { Note } from './model';

/** A single Web Audio clock drives both scheduled voices and the visible playhead. */
export class Player {
  private context?: AudioContext;
  private nodes: OscillatorNode[] = [];
  private channels?: { cf: GainNode; cp: GainNode };
  private started = 0;
  private secondsPerTick = 0;
  private endTick = 0;
  private frame = 0;
  private generation = 0;
  stop() {
    this.generation++;
    cancelAnimationFrame(this.frame);
    for (const node of this.nodes) { try { node.stop(); } catch { /* already stopped */ } node.disconnect(); }
    this.nodes = [];
    this.channels?.cf.disconnect(); this.channels?.cp.disconnect(); this.channels = undefined;
  }
  async dispose() {
    this.stop();
    const context = this.context;
    this.context = undefined;
    if (context && context.state !== 'closed') {
      try { await context.close(); } catch { /* context may already be closing */ }
    }
  }
  setMute(voice: 'cf' | 'cp', muted: boolean) { if (this.channels && this.context) this.channels[voice].gain.setTargetAtTime(muted ? 0 : 0.18, this.context.currentTime, 0.015); }
  async play(notes: Note[], ppq: number, tempo: number, endTick: number, muted: { cf: boolean; cp: boolean }, onTick: (tick: number | null) => void) {
    this.stop();
    const generation = this.generation;
    const ctx = this.context ??= new AudioContext();
    try { await ctx.resume(); } catch (error) {
      if (generation !== this.generation) return;
      throw error;
    }
    if (generation !== this.generation || this.context !== ctx || ctx.state === 'closed') return;
    this.started = ctx.currentTime + 0.045;
    this.secondsPerTick = 60 / tempo / ppq;
    this.endTick = endTick;
    this.channels = { cf: ctx.createGain(), cp: ctx.createGain() };
    for (const voice of ['cf', 'cp'] as const) { this.channels[voice].gain.value = muted[voice] ? 0 : 0.18; this.channels[voice].connect(ctx.destination); }
    for (const note of notes) {
      const osc = ctx.createOscillator();
      const envelope = ctx.createGain();
      const start = this.started + note.startTick * this.secondsPerTick;
      const duration = note.durationTicks * this.secondsPerTick;
      osc.type = note.voiceId === 'cf' ? 'triangle' : 'sine';
      osc.frequency.value = frequency(note.pitch);
      envelope.gain.setValueAtTime(0, start);
      envelope.gain.linearRampToValueAtTime(0.8, start + 0.025);
      envelope.gain.setValueAtTime(0.65, start + Math.max(0.03, duration - 0.12));
      envelope.gain.linearRampToValueAtTime(0, start + duration);
      osc.connect(envelope); envelope.connect(this.channels[note.voiceId]);
      osc.onended = () => { osc.disconnect(); envelope.disconnect(); };
      osc.start(start); osc.stop(start + duration + 0.01); this.nodes.push(osc);
    }
    const tick = () => {
      if (generation !== this.generation) return;
      const position = Math.max(0, (ctx.currentTime - this.started) / this.secondsPerTick);
      if (position >= this.endTick) { this.stop(); onTick(null); return; }
      onTick(position);
      this.frame = requestAnimationFrame(tick);
    };
    tick();
  }
}
