import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ReportsPage from '../pages/ReportsPage';
import { POLL_MS } from './status';

const get = vi.fn();
vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { dataMode: 'live', liveApi: () => ({ get }), ApiError: actual.ApiError };
});

const status = (over: object) => ({
  schema_version: 2,
  session_id: 'sess_1',
  status: 'STARTED',
  report_ready: false,
  plan_ready: false,
  ...over,
});

const statusCalls = () => get.mock.calls.filter(([path]) => String(path).startsWith('/v1/sessions')).length;

function renderReports() {
  return render(
    <MemoryRouter initialEntries={['/reports?pending=sess_1']}>
      <ReportsPage />
    </MemoryRouter>,
  );
}

describe('the reports screen after a reading check (live build)', () => {
  beforeEach(() => {
    get.mockReset();
  });

  it('says the report is being made while it is, and reloads the list once it exists', async () => {
    get.mockImplementation(async (path: string) => {
      if (path === '/v1/reports') return { reports: [] };
      const ready = statusCalls() > 1;
      return status({ report_ready: ready, status: ready ? 'COMPLETE' : 'STARTED' });
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderReports();
      expect(await screen.findByText(/report is being made/i)).toBeInTheDocument();
      await vi.advanceTimersByTimeAsync(POLL_MS + 100);
      await waitFor(() => expect(screen.queryByText(/report is being made/i)).not.toBeInTheDocument());
      expect(get.mock.calls.filter(([path]) => path === '/v1/reports').length).toBeGreaterThanOrEqual(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('says so kindly when the check stopped before the end', async () => {
    get.mockImplementation(async (path: string) =>
      path === '/v1/reports' ? { reports: [] } : status({ status: 'INCOMPLETE' }),
    );
    renderReports();
    expect(await screen.findByText(/stopped before the end/i)).toBeInTheDocument();
  });
});
