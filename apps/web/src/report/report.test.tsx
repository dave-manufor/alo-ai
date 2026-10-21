import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import ReportDetailPage from '../pages/ReportDetailPage';
import ReportsPage from '../pages/ReportsPage';
import { levelLabel, sampleReports } from './reportFixture';

describe('report screens (PRD 10.4, fixture-backed)', () => {
  it('joins the report with its child and shows the Coach summary, not the profile label', () => {
    render(
      <MemoryRouter initialEntries={['/reports/sess_demo_001']}>
        <Routes>
          <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    const report = sampleReports[0];
    expect(screen.getByRole('heading', { name: "Adaeze's report" })).toBeInTheDocument();
    expect(screen.getByText(report.parent_reporting!.summary_script)).toBeInTheDocument();
    expect(screen.getByText(report.parent_reporting!.home_practice)).toBeInTheDocument();
    expect(screen.getByText(`${report.fluency.accuracy_pct}%`)).toBeInTheDocument();
    // Comprehension is a score out of 100, not a share of the story.
    expect(screen.getByText('70 out of 100')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/diagnos|dyslex|failing/i);
  });

  it('keeps the weekly plan behind the entitlement and shows books with attribution', () => {
    render(
      <MemoryRouter initialEntries={['/reports/sess_demo_001']}>
        <Routes>
          <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(/The Goat at the Market/)).toBeInTheDocument();
    expect(screen.getAllByText(/Sample attribution/).length).toBeGreaterThan(0);
    // Plan activities are the paid part (PRD 11.1): not shown free.
    expect(screen.queryByText('Word cards')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Get the weekly plan' })).toBeInTheDocument();
  });

  it('shows no numbers and a try-again message for insufficient evidence', () => {
    render(
      <MemoryRouter initialEntries={['/reports/sess_demo_002']}>
        <Routes>
          <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: "Tunde's report" })).toBeInTheDocument();
    expect(screen.getByText(/try another check/i)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/null|NaN/);
    expect(levelLabel(sampleReports[1])).toBeNull();
  });

  it('labels an independent level as "or above" (PRD 6.7)', () => {
    const independent = {
      ...sampleReports[0],
      level: { ...sampleReports[0].level, at_least: true, band: 'INDEPENDENT' },
    };
    expect(levelLabel(independent)).toBe('ARL 2 or above');
    expect(levelLabel(sampleReports[0])).toBe('About ARL 2');
  });

  it('lists reports and handles an unknown report kindly', () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Reading reports' })).toBeInTheDocument();

    render(
      <MemoryRouter initialEntries={['/reports/nope']}>
        <Routes>
          <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      screen.getByRole('heading', { name: 'We could not find that report' }),
    ).toBeInTheDocument();
  });
});
