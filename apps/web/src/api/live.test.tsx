import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { addChild, syncAccount } from '../account/actions';
import { accountStore } from '../account/store';
import ReportDetailPage from '../pages/ReportDetailPage';
import ReportsPage from '../pages/ReportsPage';
import { createSessionDriver } from '../session/driverFactory';
import { sampleReports } from '../report/reportFixture';
import { ApiError } from './client';

// A live build, with the API faked: nothing here touches the network.
const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
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
  sign_in_method: 'google',
  verified_email: 'e@example.com',
  timestamp: '2026-10-01T00:00:00Z',
  training_opt_in: false,
};

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  accountStore.resetForTests();
  accountStore.signInVerified({ id: 'g1', email: 'e@example.com', method: 'google' });
});

describe('live build: account', () => {
  it('syncs children and consents from the API into the store', async () => {
    api.get.mockImplementation(async (path: string) =>
      path === '/v1/children' ? { children: [child] } : consent,
    );
    await syncAccount();
    expect(accountStore.getState().children[0].first_name).toBe('Ada');
    expect(accountStore.canStartSession('child_1')).toBe(true);
  });

  it('adds a child through the API, and refuses without the tick before any call', async () => {
    api.post.mockResolvedValue({ child_id: 'child_1', child, consent });
    const input = { firstName: 'Ada', primaryClass: 3, birthYear: 2017, attested: true, trainingOptIn: false };
    await addChild(input);
    expect(api.post).toHaveBeenCalledWith('/v1/children', expect.objectContaining({ attested: true }));
    expect(accountStore.getState().children).toHaveLength(1);

    api.post.mockClear();
    await expect(addChild({ ...input, attested: false })).rejects.toThrow(/Consent is needed/);
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe('live build: reports', () => {
  function renderAt(path: string) {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it('shows loading, then the reports the API returned', async () => {
    api.get.mockResolvedValue({ reports: [sampleReports[0]] });
    renderAt('/reports');
    expect(screen.getByText('Getting the reports…')).toBeInTheDocument();
    expect(await screen.findByText('See the full report')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/v1/reports');
  });

  it('shows a plain message when the reports cannot be loaded', async () => {
    api.get.mockRejectedValue(new ApiError(503, 'X', true, 'Something went wrong on our side. Please try again in a moment.'));
    renderAt('/reports');
    expect(await screen.findByText(/Something went wrong on our side/)).toBeInTheDocument();
    api.get.mockRejectedValue(new Error('boom'));
    renderAt('/reports');
    expect(await screen.findByText(/We could not load the reports/)).toBeInTheDocument();
  });

  it('shows one report, and "could not find" for a 404', async () => {
    api.get.mockResolvedValue(sampleReports[0]);
    renderAt(`/reports/${sampleReports[0].session_id}`);
    expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith(`/v1/reports/${sampleReports[0].session_id}`);

    api.get.mockRejectedValue(new ApiError(404, 'NOT_FOUND', false, 'x'));
    renderAt('/reports/nope');
    expect(await screen.findByText('We could not find that report')).toBeInTheDocument();
  });
});

describe('live build: session driver', () => {
  it('asks the API for a session for this child only', async () => {
    api.post.mockRejectedValue(new Error('offline'));
    const driver = createSessionDriver('child_1');
    const failures: string[] = [];
    driver.onFailed?.((plain) => failures.push(plain));
    driver.start(() => undefined);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(api.post).toHaveBeenCalledWith('/v1/sessions', { child_id: 'child_1' });
    expect(failures).toHaveLength(1);
    driver.stop();
  });
});
