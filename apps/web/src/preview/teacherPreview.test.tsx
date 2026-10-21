import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import SchoolChildPage from '../pages/SchoolChildPage';
import SchoolsPreviewPage from '../pages/SchoolsPreviewPage';
import { previewClass } from './teacherFixture';

function renderPreview() {
  return render(
    <MemoryRouter initialEntries={['/schools/preview']}>
      <Routes>
        <Route path="/schools/preview" element={<SchoolsPreviewPage />} />
        <Route path="/schools/preview/children/:childId" element={<SchoolChildPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('teacher view preview (PRD 4.7)', () => {
  it('shows the banner, the sample class of 23, and groups for all profiles', () => {
    renderPreview();
    expect(
      screen.getByText('Preview with sample data. Coming soon for schools.'),
    ).toBeInTheDocument();
    expect(screen.getByText('P3B (sample), 23 children')).toBeInTheDocument();
    expect(previewClass).toHaveLength(23);
    expect(new Set(previewClass.map((child) => child.profile)).size).toBe(7);
    expect(screen.getByRole('heading', { name: 'Groups for practice' })).toBeInTheDocument();
  });

  it('makes no network calls', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderPreview();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it('labels children due a check and says coming soon for actions', () => {
    renderPreview();
    expect(screen.getAllByText('Due a check').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Run a check' }));
    expect(screen.getByRole('status')).toHaveTextContent(/coming soon/i);
  });

  it('sorts the class table and reveals scripted assistant answers', () => {
    renderPreview();
    const table = screen.getByRole('table');
    fireEvent.click(within(table).getByRole('button', { name: 'Words a minute' }));
    const firstRow = within(table).getAllByRole('row')[1];
    expect(firstRow).toHaveTextContent('Ifeanyi J.');

    fireEvent.click(
      screen.getByRole('button', { name: "Who hasn't been checked this term?" }),
    );
    expect(screen.getByText(/Blessing Q\. and Segun V\./)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Coming soon')).toBeDisabled();
  });

  it('shows a child page with the sample story and marked words', () => {
    render(
      <MemoryRouter initialEntries={['/schools/preview/children/bola-k']}>
        <Routes>
          <Route path="/schools/preview/children/:childId" element={<SchoolChildPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      screen.getByText('Preview with sample data. Coming soon for schools.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Bola K.' })).toBeInTheDocument();
    expect(screen.getAllByText(/was read as/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Hear a word' }));
    expect(screen.getByRole('status')).toHaveTextContent(/coming soon/i);
  });
});
