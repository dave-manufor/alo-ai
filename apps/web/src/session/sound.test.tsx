import { fireEvent, render, renderHook, screen, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { accountStore } from '../account/store';
import SessionPage from '../pages/SessionPage';
import { stubMic } from '../test/mic';
import type { SessionDriver } from './driver';
import {
  createSoundBoard,
  loadSoundPreference,
  MASTER_GAIN,
  saveSoundPreference,
  useSoundPreference,
} from './sound';

function fakeContext(state: 'running' | 'suspended' = 'running') {
  const oscillators: { type: string; frequency: { value: number }; start: ReturnType<typeof vi.fn>; stop: ReturnType<typeof vi.fn>; connect: ReturnType<typeof vi.fn> }[] = [];
  const gains: { gain: { value: number; setValueAtTime: ReturnType<typeof vi.fn>; linearRampToValueAtTime: ReturnType<typeof vi.fn>; exponentialRampToValueAtTime: ReturnType<typeof vi.fn>; cancelScheduledValues: ReturnType<typeof vi.fn> }; connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }[] = [];
  const destination = {};
  const context = {
    state,
    currentTime: 1,
    destination,
    createGain() {
      const gain = {
        gain: {
          value: 1,
          setValueAtTime: vi.fn(),
          linearRampToValueAtTime: vi.fn(),
          exponentialRampToValueAtTime: vi.fn(),
          cancelScheduledValues: vi.fn(),
        },
        connect: vi.fn(),
        disconnect: vi.fn(),
      };
      gains.push(gain);
      return gain;
    },
    createOscillator() {
      const oscillator = {
        type: '',
        frequency: { value: 0 },
        start: vi.fn(),
        stop: vi.fn(),
        connect: vi.fn(),
      };
      oscillators.push(oscillator);
      return oscillator;
    },
  };
  return { context: context as unknown as AudioContext, oscillators, gains, destination };
}

describe('the sound board', () => {
  it('makes no sound with no audio context, or one that is not running', () => {
    createSoundBoard(null).chime('step');
    const suspended = fakeContext('suspended');
    const board = createSoundBoard(suspended.context);
    board.chime('step');
    board.pop(0);
    board.tick();
    board.ambience(true);
    expect(suspended.oscillators).toHaveLength(0);
  });

  it('plays two soft notes for a new stage, four rising ones to finish, all quiet', () => {
    const { context, oscillators, gains, destination } = fakeContext();
    const board = createSoundBoard(context);
    board.chime('step');
    expect(oscillators.map((o) => o.frequency.value)).toEqual([523.25, 659.25]);
    board.chime('reward');
    expect(oscillators.slice(2).map((o) => o.frequency.value)).toEqual([523.25, 659.25, 783.99, 1046.5]);
    // pure tones, through one master level that is well under a voice
    expect(oscillators.every((o) => o.type === 'sine')).toBe(true);
    const master = gains[0];
    expect(master.gain.value).toBe(MASTER_GAIN);
    expect(MASTER_GAIN).toBeLessThanOrEqual(0.1);
    expect(master.connect).toHaveBeenCalledWith(destination);
    expect(oscillators.every((o) => o.start.mock.calls.length === 1 && o.stop.mock.calls.length === 1)).toBe(true);
  });

  it('pops a little higher for each number counted, and stays inside its five notes', () => {
    const { context, oscillators } = fakeContext();
    const board = createSoundBoard(context);
    for (const i of [0, 1, 2, 3, 4, 9, -3]) board.pop(i);
    const heard = oscillators.map((o) => o.frequency.value);
    expect(heard.slice(0, 5)).toEqual([...heard.slice(0, 5)].sort((a, b) => a - b));
    expect(heard[5]).toBe(heard[4]); // past the last: the last note
    expect(heard[6]).toBe(heard[0]); // below the first: the first note
  });

  it('ticks once when the story appears', () => {
    const { context, oscillators } = fakeContext();
    createSoundBoard(context).tick();
    expect(oscillators).toHaveLength(1);
  });

  it('is silent when a grown-up has turned sound off, and stops the shimmer at once', () => {
    const { context, oscillators } = fakeContext();
    const board = createSoundBoard(context);
    board.ambience(true);
    const voices = oscillators.length;
    expect(voices).toBe(3); // two tones and the slow swell
    board.setEnabled(false);
    expect(oscillators.every((o) => o.stop.mock.calls.length >= 1)).toBe(true);
    board.chime('step');
    board.pop(0);
    board.tick();
    expect(oscillators).toHaveLength(voices);
    board.setEnabled(true);
    board.chime('step');
    expect(oscillators).toHaveLength(voices + 2);
  });

  it('the shimmer starts once, fades out when the wait is over, and is not used with reduced motion', () => {
    const { context, oscillators, gains } = fakeContext();
    const board = createSoundBoard(context);
    board.ambience(true);
    board.ambience(true); // still the same one
    expect(oscillators).toHaveLength(3);
    board.ambience(false);
    expect(oscillators.every((o) => o.stop.mock.calls.length === 1)).toBe(true);
    const shimmerGain = gains[1];
    expect(shimmerGain.gain.linearRampToValueAtTime).toHaveBeenLastCalledWith(0, expect.any(Number));
    board.ambience(false); // nothing to stop twice
    expect(oscillators.every((o) => o.stop.mock.calls.length === 1)).toBe(true);

    const calm = fakeContext();
    createSoundBoard(calm.context, { reducedMotion: true }).ambience(true);
    expect(calm.oscillators).toHaveLength(0);
  });

  it('lets go of its output when the screen is left', () => {
    const { context, gains } = fakeContext();
    const board = createSoundBoard(context);
    board.chime('step');
    board.dispose();
    expect(gains[0].disconnect).toHaveBeenCalled();
    board.dispose(); // harmless twice
  });
});

describe('the grown-up’s sound switch', () => {
  beforeEach(() => localStorage.clear());

  it('is on until turned off, and remembers', () => {
    expect(loadSoundPreference()).toBe(true);
    saveSoundPreference(false);
    expect(loadSoundPreference()).toBe(false);
    saveSoundPreference(true);
    expect(loadSoundPreference()).toBe(true);
  });

  it('carries on when storage is blocked', () => {
    const blocked = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(loadSoundPreference()).toBe(true);
    expect(() => saveSoundPreference(false)).not.toThrow();
    blocked.mockRestore();
    set.mockRestore();
  });

  it('the hook flips and saves it', () => {
    const { result } = renderHook(() => useSoundPreference());
    expect(result.current[0]).toBe(true);
    act(() => result.current[1](false));
    expect(result.current[0]).toBe(false);
    expect(localStorage.getItem('alo.sound')).toBe('off');
  });
});

describe('on the session screen', () => {
  afterEach(() => localStorage.clear());

  it('the microphone card has a sound switch for the grown-up', () => {
    stubMic();
    localStorage.clear();
    accountStore.resetForTests();
    accountStore.signIn('google');
    const { child } = accountStore.addChildWithConsent({
      firstName: 'Adaeze',
      primaryClass: 3,
      birthYear: 2017,
      attested: true,
      trainingOptIn: false,
    });
    const driver = (): SessionDriver => ({ start: () => undefined, send: () => undefined, stop: () => undefined });
    render(
      <MemoryRouter initialEntries={[`/session/${child.child_id}`]}>
        <Routes>
          <Route path="/session/:childId" element={<SessionPage createDriver={driver} />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    const toggle = screen.getByRole('button', { name: 'Sound on' });
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(toggle);
    expect(screen.getByRole('button', { name: 'Sound off' })).toHaveAttribute('aria-pressed', 'false');
    expect(localStorage.getItem('alo.sound')).toBe('off');
  });
});
