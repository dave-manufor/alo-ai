import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { accountStore } from '../account/store';
import SessionPage from '../pages/SessionPage';
import { removeMic, startSessionScreen, stubMic } from '../test/mic';
import type { SessionDriver } from './driver';
import type { AgentMessage } from './protocol';

const v2 = { schema_version: 2 as const };
let script: AgentMessage[] = [];

function scriptedDriver(): SessionDriver {
  return {
    start: (sink) => {
      void (async () => {
        for (const message of script) await sink(message);
      })();
    },
    send: () => undefined,
    stop: () => undefined,
  };
}

function signedInChild(): string {
  accountStore.signIn('google');
  const { child } = accountStore.addChildWithConsent({
    firstName: 'Adaeze',
    primaryClass: 3,
    birthYear: 2017,
    attested: true,
    trainingOptIn: false,
  });
  return child.child_id;
}

function renderSession() {
  const childId = signedInChild();
  return render(
    <MemoryRouter initialEntries={[`/session/${childId}`]}>
      <Routes>
        <Route path="/session/:childId" element={<SessionPage createDriver={scriptedDriver} />} />
        <Route path="/children" element={<p>children page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

const BANNED_FOR_CHILD = /\b(wrong|incorrect|fail|failed|no)\b|\d+\s?%|score|timer/i;

beforeEach(() => {
  localStorage.clear();
  accountStore.resetForTests();
  stubMic();
});

describe('B6 greeting, story and Start', () => {
  it('opens with the call and Start, and the story is never chosen by the child', () => {
    const { container } = renderSession();
    expect(screen.getByText('Àlọ́ o!')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /story/i })).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(BANNED_FOR_CHILD);
  });

  it('shows "Your story" with the title the agent sent', async () => {
    script = [
      { ...v2, cmd: 'step', step: 'READING' },
      {
        ...v2,
        cmd: 'show_passage',
        passage_id: 'p',
        title: 'Market Day',
        sentences: ['Ada went to the market.', 'She saw a red hat.'],
        arl: 3,
      },
    ];
    renderSession();
    startSessionScreen();
    expect(await screen.findByText('Your story')).toBeInTheDocument();
    expect(screen.getAllByText('Market Day').length).toBeGreaterThan(0);
  });
});

describe('B7 microphone permission', () => {
  it('explains first and only asks the browser after "I’m ready"', async () => {
    const { getUserMedia, stop } = stubMic();
    renderSession();
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    expect(screen.getByText('Auntie Kemi needs to hear you')).toBeInTheDocument();
    expect(getUserMedia).not.toHaveBeenCalled();
    script = [{ ...v2, cmd: 'step', step: 'MIC_CHECK' }];
    fireEvent.click(screen.getByRole('button', { name: /ready/i }));
    await screen.findByRole('button', { name: /Listening|mic/i });
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true });
    expect(stop).toHaveBeenCalled(); // the probe stream is released
  });

  it('shows a plain grown-up recovery screen when the mic is blocked, then retries', async () => {
    stubMic('NotAllowedError');
    const { container } = renderSession();
    startSessionScreen();
    expect(await screen.findByText('The microphone is turned off')).toBeInTheDocument();
    expect(screen.getByText(/set Microphone to Allow/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/wrong|incorrect|fail/i);
    // No kid-mode pieces on the grown-up screen.
    expect(container.querySelector('.voice-orb')).toBeNull();

    script = [{ ...v2, cmd: 'step', step: 'MIC_CHECK' }];
    stubMic('allow');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByRole('button', { name: /Listening|mic/i });
    expect(screen.queryByText('The microphone is turned off')).not.toBeInTheDocument();
  });

  it('says so when there is no microphone to use', async () => {
    removeMic();
    renderSession();
    startSessionScreen();
    expect(await screen.findByText('No microphone found')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Back to your children' }));
    expect(await screen.findByText('children page')).toBeInTheDocument();
  });

  it('treats a missing device as unavailable, not as blocked', async () => {
    stubMic('NotFoundError');
    renderSession();
    startSessionScreen();
    expect(await screen.findByText('No microphone found')).toBeInTheDocument();
  });
});

describe('B8 hand-back and press-and-hold gate', () => {
  async function reachHandback() {
    script = [{ ...v2, cmd: 'step', step: 'CLOSE' }];
    renderSession();
    startSessionScreen();
    fireEvent.click(await screen.findByRole('button', { name: /Collect stars/ }));
    return screen.getByRole('button', { name: /Grown-ups: press and hold/ });
  }

  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => vi.useRealTimers());

  it('is not completed by a quick Space tap, but by holding Space', async () => {
    const hold = await reachHandback();
    expect(screen.getByText('Please give the phone to a grown-up')).toBeInTheDocument();
    fireEvent.keyDown(hold, { key: ' ' });
    act(() => void vi.advanceTimersByTime(300));
    fireEvent.keyUp(hold, { key: ' ' });
    act(() => void vi.advanceTimersByTime(1500));
    expect(screen.queryByText(/report is ready/)).not.toBeInTheDocument();

    fireEvent.keyDown(hold, { key: ' ' });
    act(() => void vi.advanceTimersByTime(1200));
    expect(screen.getByText("Adaeze's report is ready")).toBeInTheDocument();
    expect(screen.getByText('Reading check · today')).toBeInTheDocument();
    expect(screen.getByText(/See how Adaeze read and what to try this week/)).toBeInTheDocument();
  });

  it('is completed by holding Enter too', async () => {
    const hold = await reachHandback();
    fireEvent.keyDown(hold, { key: 'Enter' });
    act(() => void vi.advanceTimersByTime(1200));
    expect(screen.getByText("Adaeze's report is ready")).toBeInTheDocument();
  });

  it('ignores key repeat and cancels when focus leaves', async () => {
    const hold = await reachHandback();
    fireEvent.keyDown(hold, { key: ' ' });
    act(() => void vi.advanceTimersByTime(400));
    fireEvent.blur(hold);
    act(() => void vi.advanceTimersByTime(2000));
    expect(screen.queryByText(/report is ready/)).not.toBeInTheDocument();
  });
});

describe('B9 dropped connection, quiet child and stop', () => {
  const clips = [
    { clip_id: 'silence_prompt', url: '/s.mp3', text: 'Take your time. I am listening.' },
    { clip_id: 'close_praise', url: '/c.mp3', text: 'You did a great job today!' },
  ];

  it('dropped connection: a calm waiting scene, then back where it was', async () => {
    script = [
      { ...v2, cmd: 'step', step: 'READING' },
      { ...v2, cmd: 'reconnecting' },
    ];
    const { container } = renderSession();
    startSessionScreen();
    expect(await screen.findByText('Let’s wait for the internet.')).toBeInTheDocument();
    expect(container.querySelector('.voice-orb')).not.toBeNull();
    expect(container.textContent).not.toMatch(BANNED_FOR_CHILD);
  });

  it('quiet child: the agent’s silence prompt is just another clip, said kindly', async () => {
    script = [
      { ...v2, cmd: 'clip_list', clips },
      { ...v2, cmd: 'step', step: 'RETELL' },
      { ...v2, cmd: 'play', clip_id: 'silence_prompt' },
    ];
    const { container } = renderSession();
    startSessionScreen();
    expect(await screen.findByText('Take your time. I am listening.')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveClass('sr-only');
    expect(container.textContent).not.toMatch(BANNED_FOR_CHILD);
  });

  it('stop: the agent praises and closes, nothing says it ended early or shows a score', async () => {
    script = [
      { ...v2, cmd: 'clip_list', clips },
      { ...v2, cmd: 'step', step: 'READING' },
      { ...v2, cmd: 'hide_passage' },
      { ...v2, cmd: 'step', step: 'CLOSE' },
      { ...v2, cmd: 'play', clip_id: 'close_praise' },
    ];
    const { container } = renderSession();
    startSessionScreen();
    expect(await screen.findByText('You did a great job today!')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /Collect stars/ })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(BANNED_FOR_CHILD);
    expect(container.textContent).not.toMatch(/stopped|early|incomplete/i);
  });
});
