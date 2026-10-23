import { useEffect, useState } from 'react';

// Subtle sound for the child's session: a soft turning shimmer while the session is being made
// ready, a two-note chime when a new stage begins, a tiny pop for each number counted, a soft
// tick when the story appears, and a rising chime at the end. Every sound is made here with
// Web Audio (no files), is quiet next to Auntie Kemi's voice, is off if a grown-up has turned
// sound off, and never plays while the audio context is not running.
//
// Care for the microphone: the phone's speaker is next to its microphone, and the agent listens
// for the child's voice. The tones are pure sines, short, and at a low level (MASTER_GAIN), and
// the shimmer plays only while the session is being prepared (the child is not expected to talk).
// The counting pops are the one sound during a child's turn: a brief note a fraction as loud as
// speech. The agent's per-turn input level and voice-detector counts show whether it matters.

/** Level of every sound: its loudest note is about -16 dBFS, softer than a voice (the first
 *  0.07 could not be heard through a phone or laptop speaker in a live test). The counting
 *  pop is scaled down to stay at the old level, since it falls in the child's turn. */
export const MASTER_GAIN = 0.2;

export interface SoundBoard {
  setEnabled(on: boolean): void;
  /** The shimmer while the session is being prepared. */
  ambience(on: boolean): void;
  /** A new stage begins (two soft notes), or the end (a rising chime). */
  chime(kind: 'step' | 'reward'): void;
  /** The nth number counted (0 to 4): a small pop, a little higher each time. */
  pop(index: number): void;
  /** The story appears. */
  tick(): void;
  dispose(): void;
}

const STEP_NOTES = [523.25, 659.25]; // C5, E5
const REWARD_NOTES = [523.25, 659.25, 783.99, 1046.5]; // C5, E5, G5, C6
const POP_NOTES = [392, 440, 494, 523.25, 587.33]; // G4 up to D5

type Maker = {
  context: AudioContext;
  master: GainNode;
};

export function createSoundBoard(
  context: AudioContext | null,
  options: { reducedMotion?: boolean } = {},
): SoundBoard {
  let enabled = true;
  let maker: Maker | null = null;
  let shimmer: { stop: () => void } | null = null;

  let wantShimmer = false;
  let reported = false;

  /** Plays now if the audio context is running. Safari suspends (or "interrupts") a context
   *  when the microphone opens, so otherwise it is woken first and the sound plays once it
   *  runs: before, a suspended context meant no sound at all for the whole session. */
  function whenRunning(play: () => void): void {
    if (!enabled || context === null) return;
    if (!reported) {
      reported = true;
      console.info('sound: audio context is', context.state);
    }
    if (context.state === 'running') {
      play();
      return;
    }
    const woken = context.resume?.();
    void woken
      ?.then(() => {
        if (enabled && context.state === 'running') play();
      })
      .catch(() => undefined);
  }

  function make(): Maker | null {
    if (!context) return null;
    if (!maker) {
      const master = context.createGain();
      master.gain.value = MASTER_GAIN;
      master.connect(context.destination);
      maker = { context, master };
    }
    return maker;
  }

  /** One soft note: a short rise, then a fall. */
  function note(freq: number, at: number, length: number, peak = 1): void {
    const m = make();
    if (!m) return;
    const oscillator = m.context.createOscillator();
    const gain = m.context.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.value = freq;
    const start = m.context.currentTime + at;
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(peak, start + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + length);
    oscillator.connect(gain);
    gain.connect(m.master);
    oscillator.start(start);
    oscillator.stop(start + length + 0.05);
  }

  function stopShimmer(): void {
    shimmer?.stop();
    shimmer = null;
  }

  function startShimmer(): void {
    if (!wantShimmer || shimmer) return;
    const m = make();
    if (!m) return;
    const { context: ctx, master } = m;
    const gain = ctx.createGain();
    gain.gain.value = 0;
    gain.connect(master);
    const voices = [196, 293.66].map((freq) => {
      const oscillator = ctx.createOscillator();
      oscillator.type = 'sine';
      oscillator.frequency.value = freq;
      oscillator.connect(gain);
      oscillator.start();
      return oscillator;
    });
    // A slow swell in and out, so it breathes rather than drones.
    const lfo = ctx.createOscillator();
    const depth = ctx.createGain();
    lfo.frequency.value = 0.3;
    depth.gain.value = 0.2;
    lfo.connect(depth);
    depth.connect(gain.gain);
    lfo.start();
    gain.gain.linearRampToValueAtTime(0.35, ctx.currentTime + 0.8);
    shimmer = {
      stop: () => {
        const now = ctx.currentTime;
        gain.gain.cancelScheduledValues(now);
        gain.gain.setValueAtTime(gain.gain.value, now);
        gain.gain.linearRampToValueAtTime(0, now + 0.5);
        for (const oscillator of [...voices, lfo]) oscillator.stop(now + 0.6);
      },
    };
  }

  return {
    setEnabled(on) {
      enabled = on;
      if (!on) stopShimmer();
    },
    ambience(on) {
      wantShimmer = on;
      if (!on || options.reducedMotion) {
        stopShimmer();
        return;
      }
      whenRunning(startShimmer);
    },
    chime(kind) {
      const notes = kind === 'reward' ? REWARD_NOTES : STEP_NOTES;
      whenRunning(() =>
        notes.forEach((freq, i) => note(freq, i * 0.16, kind === 'reward' ? 0.9 : 0.55, 0.8)),
      );
    },
    pop(index) {
      // Scaled to the old, quieter master level: this is the one sound in the child's turn.
      const peak = (0.6 * 0.07) / MASTER_GAIN;
      whenRunning(() =>
        note(POP_NOTES[Math.max(0, Math.min(POP_NOTES.length - 1, index))], 0, 0.16, peak),
      );
    },
    tick() {
      whenRunning(() => note(880, 0, 0.09, 0.35));
    },
    dispose() {
      stopShimmer();
      maker?.master.disconnect();
      maker = null;
    },
  };
}

// ---- the grown-up's switch

const KEY = 'alo.sound';

export function loadSoundPreference(): boolean {
  try {
    return window.localStorage.getItem(KEY) !== 'off';
  } catch {
    return true;
  }
}

export function saveSoundPreference(on: boolean): void {
  try {
    window.localStorage.setItem(KEY, on ? 'on' : 'off');
  } catch {
    // Private mode: the choice lasts for this visit.
  }
}

/** Sound on or off, remembered on this phone (a grown-up's choice, not a child's). */
export function useSoundPreference(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(loadSoundPreference);
  useEffect(() => saveSoundPreference(on), [on]);
  return [on, setOn];
}
