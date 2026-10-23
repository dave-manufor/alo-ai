import { useEffect, useRef, useState } from 'react';

// The child's microphone level, measured here in the browser. It does two jobs, and neither
// sends audio anywhere or keeps a word:
//  - the green lights that flow into the orb while the child is heard (the stage's `voice`
//    layer, which until now only moved when the AGENT said it heard the child);
//  - a grown-up warning when the microphone has been silent for a long while, so a dead or
//    muted microphone is seen on the phone instead of the session quietly running on timers.
// Levels are read about 12 times a second and only the on/off changes reach React.

export interface MicMeter {
  /** The most recent level in dBFS (-Infinity for digital silence). */
  level(): number;
  /** False while the audio context is not running (Safari keeps one suspended unless it was
   *  started inside a tap): its silence says nothing about the microphone. */
  usable?(): boolean;
  stop(): void;
}

type ContextConstructor = typeof AudioContext;

function contextConstructor(): ContextConstructor | undefined {
  if (typeof window === 'undefined') return undefined;
  return (
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: ContextConstructor }).webkitAudioContext
  );
}

let primed: AudioContext | null = null;

/** Lets go of the primed context (tests; and when the session screen is left for good). */
export function forgetAudioContext(): void {
  void primed?.close?.();
  primed = null;
}

/** Call inside the tap that starts the microphone (before any await): Safari and iOS only let
 *  an audio context run if it was started from a user gesture. The meter uses this context. */
export function primeAudioContext(): void {
  if (primed && primed.state !== 'closed') {
    void primed.resume?.();
    return;
  }
  const Ctx = contextConstructor();
  if (!Ctx) return;
  primed = new Ctx();
  void primed.resume?.();
}

export interface MeterOptions {
  intervalMs?: number;
  /** Test seam: a ready AnalyserNode-like source of time-domain samples. */
  analyser?: { getFloatTimeDomainData(into: Float32Array): void; fftSize: number };
}

const INTERVAL_MS = 80;

export function rmsDbfs(samples: Float32Array): number {
  if (samples.length === 0) return -Infinity;
  let sum = 0;
  for (let i = 0; i < samples.length; i += 1) sum += samples[i] * samples[i];
  const rms = Math.sqrt(sum / samples.length);
  return rms === 0 ? -Infinity : 20 * Math.log10(rms);
}

/** Starts measuring `stream`. Must be called from a user gesture on iOS (the Start tap chain). */
export function createMicMeter(stream: MediaStream, options: MeterOptions = {}): MicMeter {
  let analyser = options.analyser ?? null;
  let context: AudioContext | null = null;
  let source: MediaStreamAudioSourceNode | null = null;
  if (!analyser) {
    const Ctx = contextConstructor();
    if (!Ctx) return { level: () => -Infinity, usable: () => false, stop: () => undefined };
    context = primed && primed.state !== 'closed' ? primed : new Ctx();
    void context.resume?.();
    source = context.createMediaStreamSource(stream);
    const node = context.createAnalyser();
    node.fftSize = 1024;
    source.connect(node); // never connected to the speakers: no echo, no sound
    analyser = node;
  }
  const buffer = new Float32Array(analyser.fftSize);
  let last = -Infinity;
  const read = () => {
    analyser?.getFloatTimeDomainData(buffer);
    last = rmsDbfs(buffer);
  };
  const timer = setInterval(read, options.intervalMs ?? INTERVAL_MS);
  return {
    level: () => last,
    usable: () => (context ? context.state === 'running' : true),
    stop: () => {
      clearInterval(timer);
      source?.disconnect();
      // The primed context is shared and reused by the next meter; only one made here is closed.
      if (context && context !== primed) void context.close?.();
    },
  };
}

// Levels (dBFS). A voice a little above room noise lights the orb; a microphone whose best
// level stays below SILENT for QUIET_MS while the child is expected to talk is probably dead.
export const VOICE_ON_DBFS = -45;
export const VOICE_HOLD_MS = 350;
export const SILENT_DBFS = -65;
export const QUIET_MS = 15_000;

export interface MicWatch {
  /** The child's voice is being heard right now (for the lights). */
  heard: boolean;
  /** The microphone has been silent for a long time while the child was expected to talk. */
  quiet: boolean;
}

/**
 * Watches `meter`. `listening` is true while the child is expected to talk and Kemi is not
 * speaking: only then do lights follow the level (so Kemi's own voice through the speaker does
 * not light them) and only then does silence count toward `quiet`.
 */
export function useMicWatch(
  meter: MicMeter | null,
  listening: boolean,
  tickMs = 100,
): MicWatch {
  const [watch, setWatch] = useState<MicWatch>({ heard: false, quiet: false });
  const state = useRef({ lastLoudAt: 0, quietFor: 0, best: -Infinity });

  useEffect(() => {
    if (!meter || !listening) {
      setWatch((current) => (current.heard ? { ...current, heard: false } : current));
      state.current.quietFor = 0;
      state.current.best = -Infinity;
      return undefined;
    }
    const timer = setInterval(() => {
      const now = Date.now();
      const level = meter.level();
      const s = state.current;
      if (meter.usable && !meter.usable()) {
        // The audio context is not running: its silence is not the microphone's.
        s.quietFor = 0;
        s.best = -Infinity;
        return;
      }
      if (level > VOICE_ON_DBFS) s.lastLoudAt = now;
      s.best = Math.max(s.best, level);
      s.quietFor += tickMs;
      if (s.best > SILENT_DBFS) {
        s.quietFor = 0;
        s.best = -Infinity;
      }
      const heard = now - s.lastLoudAt < VOICE_HOLD_MS;
      const quiet = s.quietFor >= QUIET_MS;
      setWatch((current) =>
        current.heard === heard && current.quiet === quiet ? current : { heard, quiet },
      );
    }, tickMs);
    return () => clearInterval(timer);
  }, [meter, listening, tickMs]);

  return watch;
}
