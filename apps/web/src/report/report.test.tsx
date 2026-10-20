import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import ReportDetailPage from '../pages/ReportDetailPage';
import ReportsPage from '../pages/ReportsPage';
import { sampleReports } from './reportFixture';

describe('report screens (PRD 10.4, fixture-backed)', () => {
  it('lists reports with numbers taken from the ReadingReport fixture', () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );
    const report = sampleReports[0];
    expect(screen.getByRole('heading', { name: 'Reading reports' })).toBeInTheDocument();
    expect(screen.getByText(`${report.fluency.accuracy_pct}%`)).toBeInTheDocument();
    expect(screen.getByText(String(report.fluency.wcpm))).toBeInTheDocument();
    expect(screen.getByText(/Understands, building word reading/)).toBeInTheDocument();
  });

  it('shows the full report: strength first, level guide, books and plan', () => {
    render(
      <MemoryRouter initialEntries={['/reports/sess_demo_001']}>
        <Routes>
          <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(/short check, so think of it as a first look/i)).toBeInTheDocument();
    expect(screen.getByText(/About ARL 2/)).toBeInTheDocument();
    expect(screen.getByText('The Goat at the Market')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /get the weekly plan/i })).toHaveAttribute(
      'href',
      '/plan/checkout',
    );
    expect(document.body.textContent).not.toMatch(/diagnos|dyslex|failing|behind/i);
  });

  it('handles an unknown report kindly', () => {
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
