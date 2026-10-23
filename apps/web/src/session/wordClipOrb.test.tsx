import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { accountStore } from '../account/store';
import SessionPage from '../pages/SessionPage';
import { startSessionScreen, stubMic } from '../test/mic';
import type { SessionDriver } from './driver';
import { fixtureClips, fixturePassage } from './fixtureDriver';
import type { AgentMessage } from './protocol';

const v2 = { schema_version: 2 as const };

// "That word is X." is Kemi speaking, like any other clip: her light pulses. The turtle (Jàpá)
// does not come out for it.
describe('a "That word is X." clip during the reading', () => {
  beforeEach(() => {
    stubMic();
    localStorage.clear();
    accountStore.resetForTests();
  });

  it('pulses the orb and leaves the turtle where it is', async () => {
    const messages: AgentMessage[] = [
      { ...v2, cmd: 'clip_list', clips: fixtureClips },
      { ...v2, cmd: 'step', step: 'READING' },
      { ...v2, cmd: 'show_passage', ...fixturePassage },
      { ...v2, cmd: 'play', clip_id: 'word_market' },
    ];
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
    const { container } = render(
      <MemoryRouter initialEntries={[`/session/${child.child_id}`]}>
        <Routes>
          <Route path="/session/:childId" element={<SessionPage createDriver={driver} />} />
        </Routes>
      </MemoryRouter>,
    );
    startSessionScreen();
    await screen.findAllByText(fixturePassage.title);
    const opacity = (key: string) =>
      Number((container.querySelector(`[data-k="${key}"]`) as HTMLElement).style.opacity);
    // The clip plays (the test cache plays instantly) and the stage settles: the turtle's
    // opacity never rises, at any point.
    const seen: number[] = [];
    for (let i = 0; i < 20; i += 1) {
      seen.push(opacity('jpeek'));
      await new Promise((resolve) => setTimeout(resolve, 25));
    }
    expect(Math.max(...seen)).toBe(0);
    await waitFor(() => expect(container.querySelector('[data-k="rings"]')).not.toBeNull());
  });
});
