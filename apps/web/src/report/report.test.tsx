import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { accountStore } from '../account/store';
import { renderApp, signInWithChild } from '../test/helpers';
import { levelLabel, sampleBooks, samplePlan, sampleReports } from './reportFixture';

describe('report screens (PRD 10.4, fixture-backed)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('joins the report with the guardian’s own child and shows the Coach summary', () => {
    const { report } = signInWithChild('Adaeze');
    renderApp(`/reports/${report.session_id}`);
    expect(screen.getByRole('heading', { name: "Adaeze's report" })).toBeInTheDocument();
    expect(screen.getByText(report.parent_reporting!.summary_script)).toBeInTheDocument();
    expect(screen.getByText(report.parent_reporting!.home_practice)).toBeInTheDocument();
    expect(screen.getByText(`${report.fluency.accuracy_pct}%`)).toBeInTheDocument();
    // Comprehension is a score out of 100, not a share of the story.
    expect(screen.getByText('70 out of 100')).toBeInTheDocument();
    expect(screen.getByText(/This is a screening to guide practice/)).toBeInTheDocument();
    // Screening language only (PRD 3.1, 12; design system README).
    expect(document.body.textContent).not.toMatch(/diagnos|dyslex|disorder|behind|failing|slow learner|hyperlexic|word caller/i);
    expect(document.body.textContent).not.toMatch(/null|NaN/);
  });

  it('keeps the weekly plan behind the entitlement', () => {
    const { report } = signInWithChild('Adaeze');
    renderApp(`/reports/${report.session_id}`);
    // The report offers the plan but does not show its activities (PRD 11.1).
    expect(screen.getByRole('button', { name: /See the plan/ })).toBeInTheDocument();
    expect(screen.queryByText(samplePlan[1].title)).not.toBeInTheDocument();
  });

  it('shows the plan activities and books with attribution once subscribed', () => {
    signInWithChild('Adaeze');
    accountStore.activateSampleSubscription();
    renderApp('/plan');
    expect(screen.getByRole('heading', { name: "Adaeze's plan" })).toBeInTheDocument();
    expect(screen.getByText(samplePlan[1].title)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(sampleBooks.book_demo_001.title.replace(/[()]/g, '.')))).toBeInTheDocument();
    expect(screen.getAllByText(/Sample attribution/).length).toBeGreaterThan(0);
  });

  it('before subscribing, the plan screen shows the free tip and the way to get the plan', () => {
    const { report } = signInWithChild('Adaeze');
    renderApp('/plan');
    expect(screen.getByText(report.parent_reporting!.home_practice)).toBeInTheDocument();
    expect(screen.queryByText(samplePlan[1].title)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /See the plan/ })).toBeInTheDocument();
  });

  it('lists the reports, and handles an unknown report kindly', () => {
    signInWithChild('Adaeze');
    renderApp('/reports');
    expect(screen.getByRole('heading', { name: 'Reading reports' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Adaeze' })).toBeInTheDocument();
  });

  it('says "We could not find that report" for an unknown report', () => {
    signInWithChild('Adaeze');
    renderApp('/reports/nope');
    expect(screen.getByRole('heading', { name: 'We could not find that report' })).toBeInTheDocument();
  });

  it('labels an independent level as "or above" (PRD 6.7)', () => {
    const independent = {
      ...sampleReports[0],
      level: { ...sampleReports[0].level, at_least: true, band: 'INDEPENDENT' },
    };
    expect(levelLabel(independent)).toBe('ARL 2 or above');
    expect(levelLabel(sampleReports[0])).toBe('About ARL 2');
    expect(levelLabel(sampleReports[1])).toBeNull();
  });
});
