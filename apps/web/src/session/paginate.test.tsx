import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { firstSentenceOfPage, fixedPages, pageOfSentence, splitIntoPages } from './paginate';
import StoryPages from './StoryPages';

const story = ['One.', 'Two.', 'Three.', 'Four.', 'Five.'];

describe('paginate (B5)', () => {
  it('fixed pages keep order and cover every sentence', () => {
    expect(fixedPages(story, 2)).toEqual([['One.', 'Two.'], ['Three.', 'Four.'], ['Five.']]);
    expect(fixedPages([], 2)).toEqual([[]]);
    expect(fixedPages(story, 0).length).toBe(5); // never loops on a bad size
  });

  it('measured split fills each page until it no longer fits', () => {
    const fitsThree = (run: string[]) => run.length <= 3;
    expect(splitIntoPages(story, fitsThree)).toEqual([
      ['One.', 'Two.', 'Three.'],
      ['Four.', 'Five.'],
    ]);
  });

  it('a page always holds at least one sentence, even when nothing fits', () => {
    expect(splitIntoPages(['A long one.', 'Another.'], () => false)).toEqual([
      ['A long one.'],
      ['Another.'],
    ]);
    expect(splitIntoPages([], () => true)).toEqual([[]]);
  });

  it('keeps your place when the pages change', () => {
    const before = fixedPages(story, 2);
    const first = firstSentenceOfPage(before, 1); // page 2 starts at sentence 2
    const after = fixedPages(story, 3);
    expect(pageOfSentence(after, first)).toBe(0);
    expect(pageOfSentence(after, 4)).toBe(1);
    expect(pageOfSentence(after, 99)).toBe(1); // past the end -> last page
  });
});

describe('StoryPages', () => {
  it('falls back to fixed pages when there is no layout to measure, and turns on tap', () => {
    const { container } = render(
      <StoryPages title="Market Day" level="p3" sentences={story} />,
    );
    // jsdom has no layout, so measuring is skipped: pages of two sentences.
    expect(screen.getByText(/One\. Two\./)).toBeInTheDocument();
    const box = screen.getByRole('group', { name: /Market Day, page 1 of 3/ });
    fireEvent.click(box);
    expect(screen.getByText(/Three\. Four\./)).toBeInTheDocument();
    fireEvent.keyDown(box, { key: 'ArrowLeft' });
    expect(screen.getByText(/One\. Two\./)).toBeInTheDocument();
    // No score, timer or number on the page indicator (dots only).
    expect(container.textContent).not.toMatch(/\d+\s?%|score|timer|second/i);
    expect(container.querySelectorAll('.story-pages__dot')).toHaveLength(3);
  });

  it('Next and Back buttons turn the page and stop at the ends', () => {
    render(<StoryPages title="T" level="p1" sentences={story} />);
    expect(screen.queryByRole('button', { name: 'Back' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByText('Five.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByText(/Three\. Four\./)).toBeInTheDocument();
  });

  it('re-measures with real sizes when the box has a height (resize)', async () => {
    // Fake layout: the box is 100px tall and each sentence in the twin is 40px tall.
    const heightOf = (el: HTMLElement) => {
      if (el.classList.contains('story-pages__box')) return 100;
      return 0;
    };
    const clientHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientHeight');
    const offsetHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
      configurable: true,
      get(this: HTMLElement) {
        return heightOf(this);
      },
    });
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
      configurable: true,
      get(this: HTMLElement) {
        if (!this.classList.contains('alo-reading')) return 0;
        const text = this.querySelector('.alo-reading-text')?.textContent ?? '';
        const sentences = text.trim() === '' ? 1 : text.split('. ').length;
        return 40 * sentences;
      },
    });
    try {
      render(<StoryPages title="T" level="p3" sentences={story} />);
      await act(async () => {
        window.dispatchEvent(new Event('resize'));
        await new Promise((resolve) => setTimeout(resolve, 50));
      });
      // 100px box, 40px per sentence: two sentences fit per page -> 3 pages.
      expect(screen.getByRole('group', { name: /page 1 of 3/ })).toBeInTheDocument();
    } finally {
      if (clientHeight) Object.defineProperty(HTMLElement.prototype, 'clientHeight', clientHeight);
      if (offsetHeight) Object.defineProperty(HTMLElement.prototype, 'offsetHeight', offsetHeight);
    }
  });
});
