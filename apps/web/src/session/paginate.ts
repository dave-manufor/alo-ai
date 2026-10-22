// Splitting the story into pages that fit the screen (B5). Pure and
// testable: the caller supplies `fits`, which says whether a given run
// of sentences fits the available box (measured in the browser), or we
// fall back to fixed pages when measuring is not possible.

/** Fixed pages of `perPage` sentences (the fallback; also used before measuring). */
export function fixedPages(sentences: string[], perPage = 2): string[][] {
  const size = Math.max(1, perPage);
  const pages: string[][] = [];
  for (let i = 0; i < sentences.length; i += size) pages.push(sentences.slice(i, i + size));
  return pages.length > 0 ? pages : [[]];
}

/**
 * Greedy split: keep adding sentences to a page while `fits` is true.
 * A page always holds at least one sentence, so a very long sentence
 * still shows (it may scroll) rather than being dropped or looping.
 */
export function splitIntoPages(
  sentences: string[],
  fits: (pageSentences: string[]) => boolean,
): string[][] {
  const pages: string[][] = [];
  let current: string[] = [];
  for (const sentence of sentences) {
    const next = [...current, sentence];
    if (current.length === 0 || fits(next)) {
      current = next;
    } else {
      pages.push(current);
      current = [sentence];
    }
  }
  if (current.length > 0) pages.push(current);
  return pages.length > 0 ? pages : [[]];
}

/** The index of the page that contains a sentence (so a resize keeps your place). */
export function pageOfSentence(pages: string[][], sentenceIndex: number): number {
  let seen = 0;
  for (let i = 0; i < pages.length; i += 1) {
    seen += pages[i].length;
    if (sentenceIndex < seen) return i;
  }
  return Math.max(0, pages.length - 1);
}

/** How many sentences come before a page. */
export function firstSentenceOfPage(pages: string[][], pageIndex: number): number {
  return pages.slice(0, pageIndex).reduce((total, page) => total + page.length, 0);
}
