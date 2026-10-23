import { act, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { accountStore } from '../account/store';
import SessionPage from '../pages/SessionPage';
import { startSessionScreen, stubMic } from '../test/mic';
import type { SessionDriver } from './driver';
import { fixtureClips } from './fixtureDriver';
import {
  createMicMeter,
  forgetAudioContext,
  primeAudioContext,
  QUIET_MS,
  rmsDbfs,
  useMicWatch,
  VOICE_HOLD_MS,
  type MicMeter,
} from './micLevel';
import { MIC_CONSTRAINTS, openMic, stopMic } from './micPermission';
import type { AgentMessage } from './protocol';

const v2 = { schema_version: 2 as const };

describe('the microphone, opened once', () => {
  it('asks with the browser’s voice processing on, and keeps the stream', async () => {
    const track = { stop: vi.fn(), getSettings: () => ({ echoCancellation: true, sampleRate: 48000 }) };
    const stream = { getTracks: () => [track], getAudioTracks: () => [track] } as unknown as MediaStream;
    const getUserMedia = vi.fn(async () => stream);
    const info = vi.spyOn(console, 'info').mockImplementation(() => undefined);
    const opened = await openMic({ getUserMedia });
    expect(opened).toEqual({ result: 'granted', stream });
    expect(getUserMedia).toHaveBeenCalledWith({ audio: MIC_CONSTRAINTS });
    // All three processing options on: switching noise suppression off cost 10 to 30 dB of
    // signal on Safari in a live session (the automatic gain went with it).
    expect(MIC_CONSTRAINTS).toMatchObject({
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    });
    expect(track.stop).not.toHaveBeenCalled(); // kept for the room and the meter
    expect(info).toHaveBeenCalledWith('microphone settings:', expect.objectContaining({ sampleRate: 48000 }));
    stopMic(opened.stream);
    expect(track.stop).toHaveBeenCalled();
    info.mockRestore();
  });

  it('says unavailable with no microphone api, and tells denied from missing', async () => {
    expect(await openMic(undefined)).toEqual({ result: 'unavailable' });
    const failing = (name: string) => ({
      getUserMedia: async () => {
        throw Object.assign(new Error(name), { name });
      },
    });
    expect((await openMic(failing('NotAllowedError'))).result).toBe('denied');
    expect((await openMic(failing('NotFoundError'))).result).toBe('unavailable');
    expect((await openMic(failing('NotReadableError'))).result).toBe('unavailable');
  });

  it('stopMic does nothing for no stream', () => {
    expect(() => stopMic(null)).not.toThrow();
  });
});

describe('the microphone level', () => {
  it('measures a sample block in dBFS, and silence as -Infinity', () => {
    expect(rmsDbfs(new Float32Array([0.5, -0.5, 0.5, -0.5]))).toBeCloseTo(-6.02, 1);
    expect(rmsDbfs(new Float32Array(8))).toBe(-Infinity);
    expect(rmsDbfs(new Float32Array(0))).toBe(-Infinity);
  });

  it('reads the analyser on a timer and stops', () => {
    vi.useFakeTimers();
    let amplitude = 0.1;
    const analyser = {
      fftSize: 4,
      getFloatTimeDomainData: (into: Float32Array) => into.fill(amplitude),
    };
    const meter = createMicMeter({} as MediaStream, { analyser, intervalMs: 50 });
    expect(meter.level()).toBe(-Infinity); // nothing read yet
    vi.advanceTimersByTime(50);
    expect(meter.level()).toBeCloseTo(-20, 0);
    amplitude = 0;
    vi.advanceTimersByTime(50);
    expect(meter.level()).toBe(-Infinity);
    meter.stop();
    amplitude = 1;
    vi.advanceTimersByTime(500);
    expect(meter.level()).toBe(-Infinity); // stopped
    vi.useRealTimers();
  });

  it('is a silent no-op where there is no audio context', () => {
    const meter = createMicMeter({} as MediaStream);
    expect(meter.level()).toBe(-Infinity);
    expect(meter.usable?.()).toBe(false);
    expect(() => meter.stop()).not.toThrow();
    expect(() => primeAudioContext()).not.toThrow(); // nothing to prime either
  });

  describe('with an audio context', () => {
    const made: FakeContext[] = [];
    class FakeContext {
      state: 'suspended' | 'running' | 'closed' = 'suspended';
      resume = vi.fn(async () => {
        this.state = 'running';
      });
      close = vi.fn(async () => {
        this.state = 'closed';
      });
      source = { connect: vi.fn(), disconnect: vi.fn() };
      constructor() {
        made.push(this);
      }
      createMediaStreamSource() {
        return this.source;
      }
      createAnalyser() {
        return { fftSize: 0, getFloatTimeDomainData: (into: Float32Array) => into.fill(0.1) };
      }
    }
    let original: unknown;
    beforeEach(() => {
      forgetAudioContext();
      made.length = 0;
      original = (window as unknown as { AudioContext?: unknown }).AudioContext;
      (window as unknown as { AudioContext: unknown }).AudioContext = FakeContext;
      vi.useFakeTimers();
    });
    afterEach(() => {
      forgetAudioContext();
      (window as unknown as { AudioContext: unknown }).AudioContext = original;
      vi.useRealTimers();
    });

    it('uses the context started inside the tap, and leaves it open for the next meter', () => {
      primeAudioContext(); // the tap
      expect(made).toHaveLength(1);
      expect(made[0].resume).toHaveBeenCalled();
      const first = createMicMeter({} as MediaStream);
      vi.advanceTimersByTime(100);
      expect(made).toHaveLength(1); // no second context
      expect(first.level()).toBeCloseTo(-20, 0);
      first.stop();
      expect(made[0].source.disconnect).toHaveBeenCalled();
      expect(made[0].close).not.toHaveBeenCalled(); // shared, kept for Try again
      primeAudioContext(); // another tap reuses it
      expect(made).toHaveLength(1);
      createMicMeter({} as MediaStream).stop();
      expect(made).toHaveLength(1);
    });

    it('says it is not usable while the context is not running', () => {
      primeAudioContext();
      made[0].resume.mockImplementation(async () => undefined); // Safari: stays suspended
      made[0].state = 'suspended';
      const meter = createMicMeter({} as MediaStream);
      expect(meter.usable?.()).toBe(false);
      made[0].state = 'running';
      expect(meter.usable?.()).toBe(true);
      meter.stop();
    });
  });
});

describe('useMicWatch', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const meterAt = (initial: number) => {
    const state = { level: initial };
    const meter: MicMeter = { level: () => state.level, stop: () => undefined };
    return { state, meter };
  };

  it('lights while a voice is heard and the child is expected to talk, then lets go', () => {
    const { state, meter } = meterAt(-80);
    const { result } = renderHook(() => useMicWatch(meter, true, 50));
    act(() => void vi.advanceTimersByTime(100));
    expect(result.current.heard).toBe(false);
    state.level = -30;
    act(() => void vi.advanceTimersByTime(100));
    expect(result.current.heard).toBe(true);
    state.level = -80;
    act(() => void vi.advanceTimersByTime(VOICE_HOLD_MS + 100));
    expect(result.current.heard).toBe(false);
  });

  it('never lights while Kemi is speaking, even if the microphone is loud', () => {
    const { meter } = meterAt(-20);
    const { result } = renderHook(() => useMicWatch(meter, false, 50));
    act(() => void vi.advanceTimersByTime(1_000));
    expect(result.current).toEqual({ heard: false, quiet: false });
  });

  it('says the microphone is quiet after a long silence, and clears when a sound comes', () => {
    const { state, meter } = meterAt(-90);
    const { result } = renderHook(() => useMicWatch(meter, true, 100));
    act(() => void vi.advanceTimersByTime(QUIET_MS - 500));
    expect(result.current.quiet).toBe(false);
    act(() => void vi.advanceTimersByTime(1_000));
    expect(result.current.quiet).toBe(true);
    state.level = -40;
    act(() => void vi.advanceTimersByTime(200));
    expect(result.current.quiet).toBe(false);
  });

  it('room noise is not silence: a microphone that hears anything is not called quiet', () => {
    const { meter } = meterAt(-55);
    const { result } = renderHook(() => useMicWatch(meter, true, 100));
    act(() => void vi.advanceTimersByTime(QUIET_MS * 2));
    expect(result.current.quiet).toBe(false);
  });

  it('does not call the microphone quiet while its audio context is not running', () => {
    const meter: MicMeter = { level: () => -100, usable: () => false, stop: () => undefined };
    const { result } = renderHook(() => useMicWatch(meter, true, 100));
    act(() => void vi.advanceTimersByTime(QUIET_MS * 2));
    expect(result.current.quiet).toBe(false);
  });

  it('does nothing without a meter', () => {
    const { result } = renderHook(() => useMicWatch(null, true, 50));
    act(() => void vi.advanceTimersByTime(QUIET_MS * 2));
    expect(result.current).toEqual({ heard: false, quiet: false });
  });
});

// ---- on the session screen

const open: AgentMessage[] = [
  { ...v2, cmd: 'clip_list', clips: fixtureClips },
  { ...v2, cmd: 'step', step: 'MIC_CHECK' },
  { ...v2, cmd: 'play', clip_id: 'mic_check_prompt' },
];

function stubDriver(): SessionDriver {
  return {
    start: (sink) => {
      void (async () => {
        for (const message of open) await sink(message);
      })();
    },
    send: () => undefined,
    stop: () => undefined,
  };
}

function signedInChild(): string {
  accountStore.signIn('google');
  return accountStore.addChildWithConsent({
    firstName: 'Adaeze',
    primaryClass: 3,
    birthYear: 2017,
    attested: true,
    trainingOptIn: false,
  }).child.child_id;
}

describe('a microphone that hears nothing', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
  });

  function renderWithMeter(createMeter: (stream: MediaStream) => MicMeter) {
    return render(
      <MemoryRouter initialEntries={[`/session/${signedInChild()}`]}>
        <Routes>
          <Route
            path="/session/:childId"
            element={<SessionPage createDriver={stubDriver} createMeter={createMeter} />}
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  const silentMeter = (stopped = vi.fn()) => vi.fn((): MicMeter => ({ level: () => -100, stop: stopped }));

  it('tells a grown-up, and Carry on anyway puts the card away for good', async () => {
    stubMic();
    const createMeter = silentMeter();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderWithMeter(createMeter);
      startSessionScreen();
      await screen.findByText(fixtureClips[1].text as string);
      expect(createMeter).toHaveBeenCalledTimes(1);
      expect(screen.queryByText(/can’t hear Adaeze/)).not.toBeInTheDocument();

      await act(async () => void (await vi.advanceTimersByTimeAsync(QUIET_MS + 8_000)));
      expect(await screen.findByText(/We can’t hear Adaeze yet/)).toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: 'Carry on anyway' }));
      expect(screen.queryByText(/can’t hear Adaeze/)).not.toBeInTheDocument();
      await act(async () => void (await vi.advanceTimersByTimeAsync(QUIET_MS + 8_000)));
      expect(screen.queryByText(/can’t hear Adaeze/)).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  }, 20_000);

  it('Try again stops the old capture and opens the microphone afresh', async () => {
    const { getUserMedia, stop } = stubMic();
    const stopped = vi.fn();
    const createMeter = silentMeter(stopped);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderWithMeter(createMeter);
      startSessionScreen();
      await screen.findByText(fixtureClips[1].text as string);
      await act(async () => void (await vi.advanceTimersByTimeAsync(QUIET_MS + 8_000)));
      fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
      await act(async () => void (await vi.advanceTimersByTimeAsync(100)));
      expect(getUserMedia).toHaveBeenCalledTimes(2); // a fresh capture
      expect(createMeter).toHaveBeenCalledTimes(2); // measured again
      expect(stopped).toHaveBeenCalledTimes(1); // the old meter stopped
      expect(stop).toHaveBeenCalled(); // and the old microphone released
    } finally {
      vi.useRealTimers();
    }
  }, 20_000);
});
