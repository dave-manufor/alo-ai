import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { accountStore } from '../account/store';
import SessionPage from '../pages/SessionPage';
import type { AgentMessage } from './protocol';

// The reconnecting and listening states never occur in the fixture
// driver's happy path, so this file drives the screen with a mocked
// driver that answers "session_started" with those agent messages.
const startMessages = vi.hoisted(() => ({ current: [] as AgentMessage[] }));

vi.mock('./fixtureDriver', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./fixtureDriver')>();
  return {
    ...actual,
    messagesFor: (event: string, step: string | null) =>
      event === 'session_started'
        ? startMessages.current
        : actual.messagesFor(event as never, step),
  };
});

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
        <Route path="/session/:childId" element={<SessionPage />} />
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
    startMessages.current = [{ schema_version: 2, cmd: 'reconnecting' }];
    renderSession(signedInChild());
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    expect(await screen.findByText('Let’s wait for the internet.')).toBeInTheDocument();
    expect(document.querySelector('.voice-orb')).not.toBeNull();
    expect(screen.queryByRole('button', { name: /Listening/ })).not.toBeInTheDocument();
  });

  it('puts rain over the listening step', async () => {
    startMessages.current = [{ schema_version: 2, cmd: 'step', step: 'LISTENING' }];
    const { container } = renderSession(signedInChild());
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    await screen.findByRole('button', { name: /Listening/ });
    expect(container.querySelector('.night-session--rain')).not.toBeNull();
    expect(container.querySelector('.voice-orb')).not.toBeNull();
  });
});
