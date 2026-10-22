import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { accountStore } from '../account/store';
import SessionPage from '../pages/SessionPage';
import type { SessionDriver } from './driver';
import type { AgentMessage } from './protocol';

// The reconnecting and listening states never occur in the fixture
// driver's happy path, so this file drives the screen with a stub
// SessionDriver that answers start() with those agent messages.
let startMessages: AgentMessage[] = [];

function stubDriver(): SessionDriver {
  return {
    start: (sink) => {
      void (async () => {
        for (const message of startMessages) await sink(message);
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

function renderSession(childId: string) {
  return render(
    <MemoryRouter initialEntries={[`/session/${childId}`]}>
      <Routes>
        <Route path="/session/:childId" element={<SessionPage createDriver={stubDriver} />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('night session states the fixture driver never reaches', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
  });

  it('shows the waiting bubble and orb while reconnecting', async () => {
    startMessages = [{ schema_version: 2, cmd: 'reconnecting' }];
    renderSession(signedInChild());
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    expect(await screen.findByText('Let’s wait for the internet.')).toBeInTheDocument();
    expect(document.querySelector('.voice-orb')).not.toBeNull();
    expect(screen.queryByRole('button', { name: /Listening/ })).not.toBeInTheDocument();
  });

  it('puts rain over the listening step', async () => {
    startMessages = [{ schema_version: 2, cmd: 'step', step: 'LISTENING' }];
    const { container } = renderSession(signedInChild());
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    await screen.findByRole('button', { name: /Listening/ });
    expect(container.querySelector('.night-session--rain')).not.toBeNull();
    expect(container.querySelector('.voice-orb')).not.toBeNull();
  });
});

describe('what Auntie Kemi says (B3)', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
  });

  it('is carried by a visually hidden polite live region, with no visible bubble', async () => {
    startMessages = [
      {
        schema_version: 2,
        cmd: 'clip_list',
        clips: [{ clip_id: 'interest_prompt', url: '/c.mp3', text: 'What stories do you like?' }],
      },
      { schema_version: 2, cmd: 'step', step: 'INTEREST_CHAT' },
      { schema_version: 2, cmd: 'play', clip_id: 'interest_prompt' },
    ];
    const { container } = renderSession(signedInChild());
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    const region = await screen.findByRole('status');
    await screen.findByText('What stories do you like?');
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveTextContent('What stories do you like?');
    expect(region).toHaveClass('sr-only');
    // Only the hidden region carries the clip text: one match, no bubble.
    expect(screen.getAllByText('What stories do you like?')).toHaveLength(1);
    expect(container.querySelector('.sr-only')).toBe(region);
  });
});
