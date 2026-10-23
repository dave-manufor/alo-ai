import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { accountStore } from '../account/store';
import SessionPage from '../pages/SessionPage';
import { startSessionScreen, stubMic } from '../test/mic';
import type { SessionDriver } from './driver';
import { fixtureClips, fixturePassage } from './fixtureDriver';
import { forgetAudioContext } from './micLevel';
import type { AgentMessage } from './protocol';

// The session screen plays the sounds at the right moments (the sounds themselves are tested in
// sound.test.tsx), with a fake audio context that records what would have been played.
const v2 = { schema_version: 2 as const };

const made: { frequency: { value: number } }[] = [];
class FakeContext {
  state: 'suspended' | 'running' | 'closed' = 'suspended';
  currentTime = 0;
  destination = {};
  resume = vi.fn(async () => {
    this.state = 'running';
  });
  close = vi.fn(async () => undefined);
  createGain() {
    return {
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
  }
  createOscillator() {
    const oscillator = { type: '', frequency: { value: 0 }, start: vi.fn(), stop: vi.fn(), connect: vi.fn() };
    made.push(oscillator);
    return oscillator;
  }
  createMediaStreamSource() {
    return { connect: vi.fn(), disconnect: vi.fn() };
  }
  createAnalyser() {
    return { fftSize: 0, getFloatTimeDomainData: (into: Float32Array) => into.fill(0) };
  }
}

function renderSession(messages: AgentMessage[]) {
  const driver = (): SessionDriver => ({
    start: (sink) => {
      void (async () => {
        for (const message of messages) await sink(message);
      })();
    },
    send: () => undefined,
    stop: () => undefined,
  });
  accountStore.signIn('google');
  const { child } = accountStore.addChildWithConsent({
    firstName: 'Adaeze',
    primaryClass: 3,
    birthYear: 2017,
    attested: true,
    trainingOptIn: false,
  });
  return render(
    <MemoryRouter initialEntries={[`/session/${child.child_id}`]}>
      <Routes>
        <Route path="/session/:childId" element={<SessionPage createDriver={driver} />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('the session screen plays its sounds', () => {
  let original: unknown;
  beforeEach(() => {
    made.length = 0;
    original = (window as unknown as { AudioContext?: unknown }).AudioContext;
    (window as unknown as { AudioContext: unknown }).AudioContext = FakeContext;
    forgetAudioContext();
    stubMic();
    localStorage.clear();
    accountStore.resetForTests();
  });
  afterEach(() => {
    forgetAudioContext();
    (window as unknown as { AudioContext: unknown }).AudioContext = original;
    localStorage.clear();
  });

  it('a chime when a stage begins and a tick when the story appears', async () => {
    renderSession([
      { ...v2, cmd: 'clip_list', clips: fixtureClips },
      { ...v2, cmd: 'step', step: 'READING' },
      { ...v2, cmd: 'show_passage', ...fixturePassage },
    ]);
    startSessionScreen();
    await screen.findAllByText(fixturePassage.title);
    const heard = made.map((o) => o.frequency.value);
    expect(heard).toContain(523.25); // the stage chime: C5, then E5
    expect(heard).toContain(659.25);
    expect(heard).toContain(880); // the tick for the story
  });

  it('makes no sound at all when the grown-up has turned it off', async () => {
    localStorage.setItem('alo.sound', 'off');
    renderSession([
      { ...v2, cmd: 'clip_list', clips: fixtureClips },
      { ...v2, cmd: 'step', step: 'READING' },
      { ...v2, cmd: 'show_passage', ...fixturePassage },
    ]);
    startSessionScreen();
    await screen.findAllByText(fixturePassage.title);
    expect(made).toHaveLength(0);
  });
});
