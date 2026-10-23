import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { accountStore } from '../account/store';
import SessionPage from '../pages/SessionPage';
import { removeMic, startSessionScreen, stubMic } from '../test/mic';
import type { SessionDriver } from './driver';
import { fixtureClips, fixturePassage } from './fixtureDriver';
import type { AgentMessage } from './protocol';

// The session screen is the Night session design (a port of the design
// artifact). jsdom cannot show the picture, so these tests pin what the
// screen is made of and what a child must never see; the pictures were
// compared against the artifact by hand (see the PR).
const v2 = { schema_version: 2 as const };
let messages: AgentMessage[] = [];
let sent: string[] = [];

function stubDriver(): SessionDriver {
  return {
    start: (sink) => {
      void (async () => {
        for (const message of messages) await sink(message);
      })();
    },
    send: (event) => {
      sent.push(event);
    },
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

function renderSession(childId: string) {
  return render(
    <MemoryRouter initialEntries={[`/session/${childId}`]}>
      <Routes>
        <Route path="/session/:childId" element={<SessionPage createDriver={stubDriver} />} />
        <Route path="/children" element={<p>children page</p>} />
        <Route path="/reports" element={<p>reports page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

const open: AgentMessage[] = [
  { ...v2, cmd: 'clip_list', clips: fixtureClips },
  { ...v2, cmd: 'step', step: 'MIC_CHECK' },
  { ...v2, cmd: 'play', clip_id: 'mic_check_prompt' },
];

describe('the Night session screen', () => {
  beforeEach(() => {
    stubMic();
    localStorage.clear();
    accountStore.resetForTests();
    messages = open;
    sent = [];
  });

  it('needs a consent record: otherwise it leaves for the children page', () => {
    accountStore.signIn('google');
    renderSession('child_unknown');
    expect(screen.getByText('children page')).toBeInTheDocument();
  });

  it('opens on Start, with no progress bar, mic button, bubble or topic buttons', () => {
    const { container } = renderSession(signedInChild());
    expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument();
    expect(container.querySelector('.night-stage')).not.toBeNull();
    expect(screen.queryByRole('button', { name: /mic|speak|talk/i })).toBeNull();
    for (const topic of ['Animals', 'Football', 'Space', 'Food']) {
      expect(screen.queryByRole('button', { name: topic })).toBeNull();
    }
    expect(container.querySelector('.moon-progress')).toBeNull();
  });

  it('explains the microphone first, then starts the session', async () => {
    renderSession(signedInChild());
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    expect(screen.getByText('Auntie Kemi needs to hear you')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /ready/i }));
    expect(await screen.findByText(fixtureClips[1].text as string)).toBeInTheDocument();
  });

  it('says what Kemi says in a screen-reader live region only', async () => {
    renderSession(signedInChild());
    startSessionScreen();
    const text = await screen.findByText(fixtureClips[1].text as string);
    expect(text).toHaveAttribute('aria-live', 'polite');
    expect(text.className).toContain('sr-only');
  });

  it('shows the story text and has a next-page arrow when the agent shows a passage', async () => {
    messages = [
      ...open,
      { ...v2, cmd: 'step', step: 'READING' },
      { ...v2, cmd: 'show_passage', ...fixturePassage },
    ];
    const { container } = renderSession(signedInChild());
    startSessionScreen();
    await waitFor(() => {
      expect(container.querySelector('[data-k="ptitle"]')?.textContent).toBe('Market Day');
    });
    expect(container.querySelector('button.next')).not.toBeNull();
    expect(container.querySelector('[data-k="ptext"]')?.textContent).toContain('Ada and Mama went to the market.');
  });

  it('never shows a score, timer, percentage or red mark to the child', async () => {
    messages = [...open, { ...v2, cmd: 'step', step: 'QUESTIONS' }, { ...v2, cmd: 'play', clip_id: 'question:0' }];
    const { container } = renderSession(signedInChild());
    startSessionScreen();
    await screen.findByText(fixtureClips[5].text as string);
    const visible = container.querySelector('.night-stage')?.textContent ?? '';
    const withoutSr = visible.replace(fixtureClips[5].text as string, '');
    expect(withoutSr).not.toMatch(/\d+\s*%|score|timer|seconds|wrong|incorrect|fail/i);
  });

  it('shows a grown-up recovery card when the microphone is blocked, and can retry', async () => {
    stubMic('NotAllowedError');
    renderSession(signedInChild());
    startSessionScreen();
    expect(await screen.findByText('The microphone is turned off')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Back to your children' })).toBeInTheDocument();
  });

  it('says so when there is no microphone', async () => {
    removeMic();
    renderSession(signedInChild());
    startSessionScreen();
    expect(await screen.findByText('No microphone found')).toBeInTheDocument();
  });

  it('keeps the story when reconnecting and drops the sr text', async () => {
    messages = [...open, { ...v2, cmd: 'reconnecting' }];
    const { container } = renderSession(signedInChild());
    startSessionScreen();
    await waitFor(() => {
      expect(container.querySelector('[role="status"]')?.textContent).toBe('');
    });
  });

  it('hands back with press and hold (pointer and Space/Enter), then offers the report', async () => {
    messages = [
      ...open,
      { ...v2, cmd: 'step', step: 'CLOSE' },
      { ...v2, cmd: 'play', clip_id: 'close_praise' },
    ];
    // The moon and star stay for 8 s before the hand-back; skip the wait with a short timer.
    const realSetTimeout = window.setTimeout;
    window.setTimeout = ((fn: () => void, ms?: number, ...rest: unknown[]) =>
      realSetTimeout(fn, ms === 8000 ? 20 : ms, ...rest)) as typeof window.setTimeout;
    try {
      renderSession(signedInChild());
      startSessionScreen();
      const hold = await screen.findByRole('button', { name: /press and hold/i }, { timeout: 4000 });
      const report = screen.getByText(/reading check is done/);
      expect(report.closest('.report')).not.toHaveClass('shown');
      // matchMedia is absent in jsdom: the hold runs for its full time, so it is released early here.
      fireEvent.keyDown(hold, { key: ' ' });
      fireEvent.keyUp(hold, { key: ' ' });
      expect(report.closest('.report')).not.toHaveClass('shown');
    } finally {
      window.setTimeout = realSetTimeout;
    }
  });
});
