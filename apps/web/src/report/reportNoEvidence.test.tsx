import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import ReportDetailPage from '../pages/ReportDetailPage';
import { sampleReports } from './reportFixture';

// A check with no usable evidence has no numbers at all (PRD 6, 10.4). Fixture reports are
// all the first sample, so this one hands the screen the no-evidence sample directly.
vi.mock('./useReports', () => ({
  useReport: () => ({
    status: 'ready',
    report: sampleReports[1],
    children: { child_demo_002: { child_id: 'child_demo_002', first_name: 'Tunde' } },
  }),
}));

describe('a report with insufficient evidence', () => {
  it('shows no numbers and a try-again message', () => {
    render(
      <MemoryRouter initialEntries={['/reports/sess_demo_002']}>
        <Routes>
          <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: "Tunde's report" })).toBeInTheDocument();
    expect(screen.getByText(/try another check/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start another check' })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/null|NaN/);
    expect(screen.queryByText(/out of 100/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /See the plan/ })).not.toBeInTheDocument();
  });
});
