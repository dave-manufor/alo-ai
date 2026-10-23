import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { accountStore } from '../account/store';
import App from '../App';
import { consentDraft } from '../onboarding/draft';

// The whole app in a live build, with only the API faked: the first-child flow from the
// consent step to the saved child, through the real route guards, shell and Home screen.
const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn() }));
vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('./client')>('./client');
  return { dataMode: 'live', liveApi: () => api, ApiError: actual.ApiError };
});

const child = {
  child_id: 'child_1',
  first_name: 'Ada',
  primary_class: 3,
  birth_year: 2017,
  class_confirmed_year: 2026,
};
const consent = {
  consent_id: 'c1',
  guardian_id: 'g1',
  child_id: 'child_1',
  text_version: 'v',
  attestation: 'a',
  sign_in_method: 'email_code',
  verified_email: 'e@example.com',
  timestamp: '2026-10-01T00:00:00Z',
  training_opt_in: false,
};

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  accountStore.resetForTests();
  accountStore.signInVerified({ id: 'g1', email: 'e@example.com', method: 'email_code' });
  consentDraft.clear();
  api.get.mockResolvedValue({ reports: [] });
  api.post.mockResolvedValue({ child_id: 'child_1', child, consent });
});

describe('live build: the first child', () => {
  it('goes from the consent step to Home and stays there', async () => {
    window.history.pushState({}, '', '/onboarding/consent');
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );
    // Step 1: the parent-or-guardian tick, then on.
    fireEvent.click(await screen.findByRole('checkbox', { name: /parent or guardian/i }));
    fireEvent.click(screen.getByRole('button', { name: /continue|next/i }));
    // Step 2: the child.
    fireEvent.change(await screen.findByRole('textbox', { name: /First name/ }), { target: { value: 'Ada' } });
    // In a browser the updates that follow the save (after an await) are not flushed together
    // the way Testing Library's act() flushes them. Switch act off for the part after the click
    // so the test schedules closer to the browser.
    const react = globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean };
    react.IS_REACT_ACT_ENVIRONMENT = false;
    fireEvent.click(screen.getByRole('button', { name: /save|add|continue|finish/i }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/v1/children', expect.anything()));
    await waitFor(() => expect(window.location.pathname).toBe('/home'));
    // Give any late redirect the chance to happen, then check it stayed.
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(window.location.pathname).toBe('/home');
    expect(accountStore.getState().children).toHaveLength(1);
  });
});
