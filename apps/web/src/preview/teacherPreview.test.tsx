import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderApp } from '../test/helpers';
import { previewBannerText, previewClass } from './teacherFixture';

// The preview is rendered the way a visitor reaches it: through the app's routes, inside the
// school layout that carries the sample-data banner on every screen.
describe('teacher view preview (PRD 4.7)', () => {
  it('shows the banner, the sample class of 23, and groups for all profiles', () => {
    renderApp('/schools');
    expect(screen.getByText(previewBannerText)).toBeInTheDocument();
    expect(screen.getByText('P3B (sample), 23 children')).toBeInTheDocument();
    expect(previewClass).toHaveLength(23);
    expect(new Set(previewClass.map((child) => child.profile)).size).toBe(7);
    expect(screen.getByRole('heading', { name: 'Groups for practice' })).toBeInTheDocument();
  });

  it('summarises the class in stat tiles worked out from the sample rows', () => {
    renderApp('/schools');
    const glance = screen.getByRole('region', { name: 'Class at a glance' });
    const checked = previewClass.filter((child) => child.lastCheckIso !== '').length;
    expect(checked).toBeLessThan(previewClass.length); // the sample has children not yet checked
    expect(within(glance).getByText(`${checked} of ${previewClass.length}`)).toBeInTheDocument();
    expect(within(glance).getByText('Need help understanding')).toBeInTheDocument();
    expect(within(glance).getByText('Provisional results')).toBeInTheDocument();
  });

  it('makes no network calls and needs no sign-in', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderApp('/schools');
    expect(screen.getByRole('heading', { name: 'P3B reading checks' })).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it('labels children due a check and says coming soon for actions', () => {
    renderApp('/schools');
    expect(screen.getAllByText('Due a check').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Run a check' }));
    expect(screen.getByRole('status')).toHaveTextContent(/coming soon/i);
  });

  it('sorts the class table and reveals scripted assistant answers', () => {
    renderApp('/schools');
    const table = screen.getByRole('table');
    fireEvent.click(within(table).getByRole('button', { name: 'Words a minute' }));
    const firstRow = within(table).getAllByRole('row')[1];
    expect(firstRow).toHaveTextContent('Ifeanyi J.');

    fireEvent.click(screen.getByRole('button', { name: "Who hasn't been checked this term?" }));
    expect(screen.getByText(/Blessing Q\. and Segun V\./)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Coming soon')).toBeDisabled();
  });

  it('sorts from the phone control too, where the column buttons are hidden', () => {
    renderApp('/schools');
    fireEvent.change(screen.getByLabelText('Sort by'), { target: { value: 'wcpm:asc' } });
    const firstRow = within(screen.getByRole('table')).getAllByRole('row')[1];
    expect(firstRow).toHaveTextContent('Ifeanyi J.');
  });

  it('opens a child page with the sample story and marked words, banner still showing', () => {
    renderApp('/schools/children/bola-k');
    expect(screen.getByText(previewBannerText)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Bola K.' })).toBeInTheDocument();
    expect(screen.getAllByText(/was read as/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Hear a word' }));
    expect(screen.getByRole('status')).toHaveTextContent(/coming soon/i);
  });

  it('keeps the old preview addresses working', () => {
    renderApp('/schools/preview/children/bola-k');
    expect(screen.getByRole('heading', { name: 'Bola K.' })).toBeInTheDocument();
  });

  it('is reachable from a child link in the class table', () => {
    renderApp('/schools');
    fireEvent.click(screen.getByRole('link', { name: 'Bola K.' }));
    expect(screen.getByRole('heading', { name: 'Bola K.' })).toBeInTheDocument();
  });
});
