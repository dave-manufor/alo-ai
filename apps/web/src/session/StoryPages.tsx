import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Button, Paper, ReadingPanel, RoundButton } from '../design-system/alo';
import {
  firstSentenceOfPage,
  fixedPages,
  pageOfSentence,
  splitIntoPages,
} from './paginate';

// The story, one page at a time (B5). Pages are measured against the box
// the story has on this screen, in Andika, once the font has loaded and
// again whenever the size changes (resize, rotation). If measuring is
// not possible (no layout yet, no font API) the story falls back to
// fixed pages of two sentences. A tap on the page turns to the next;
// "Back" goes back. The indicator is dots only: no number, timer or
// score. Nothing animates, so reduced motion is respected by default.
export default function StoryPages({
  title,
  level,
  sentences,
}: {
  title: string;
  level: 'p1' | 'p3' | 'p5';
  sentences: string[];
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLDivElement>(null);
  const [pages, setPages] = useState<string[][]>(() => fixedPages(sentences));
  const [pageIndex, setPageIndex] = useState(0);
  const pagesRef = useRef(pages);
  const indexRef = useRef(pageIndex);
  pagesRef.current = pages;
  indexRef.current = pageIndex;

  const measure = useCallback(() => {
    const box = boxRef.current;
    const twin = measureRef.current;
    const text = twin?.querySelector<HTMLElement>('.alo-reading-text');
    const panel = twin?.querySelector<HTMLElement>('.alo-reading');
    const available = box?.clientHeight ?? 0;
    // No layout (or no panel markup to copy): keep the fixed pages.
    if (!box || !text || !panel || available <= 0) return;
    text.textContent = sentences[0] ?? '';
    if (panel.offsetHeight <= 0) return;
    const next = splitIntoPages(sentences, (run) => {
      text.textContent = run.join(' ');
      return panel.offsetHeight <= available;
    });
    // Keep the reader's place: stay on the page holding the same first sentence.
    const keep = firstSentenceOfPage(pagesRef.current, indexRef.current);
    setPages(next);
    setPageIndex(pageOfSentence(next, keep));
  }, [sentences]);

  // New story: start again from fixed pages.
  useEffect(() => {
    setPages(fixedPages(sentences));
    setPageIndex(0);
  }, [sentences]);

  useLayoutEffect(() => {
    let cancelled = false;
    const run = () => {
      if (!cancelled) measure();
    };
    // Wait for Andika so the measurements match what the child sees.
    const fonts = (document as Document & { fonts?: { ready: Promise<unknown> } }).fonts;
    if (fonts?.ready) void fonts.ready.then(run).catch(run);
    else run();

    let frame = 0;
    const onResize = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(run);
    };
    window.addEventListener('resize', onResize);
    window.addEventListener('orientationchange', onResize);
    const observer =
      typeof ResizeObserver === 'undefined' || !boxRef.current ? null : new ResizeObserver(onResize);
    if (observer && boxRef.current) observer.observe(boxRef.current);
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', onResize);
      window.removeEventListener('orientationchange', onResize);
      observer?.disconnect();
    };
  }, [measure]);

  const last = pages.length - 1;
  const turn = () => setPageIndex((i) => Math.min(i + 1, last));

  return (
    <Paper className="story-pages">
      <div
        ref={boxRef}
        className="story-pages__box"
        role="group"
        aria-label={`${title}, page ${pageIndex + 1} of ${pages.length}`}
        tabIndex={0}
        onClick={turn}
        onKeyDown={(event) => {
          if (event.key === 'ArrowRight' || event.key === 'ArrowDown') turn();
          if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
            setPageIndex((i) => Math.max(i - 1, 0));
          }
        }}
      >
        <ReadingPanel title={title} level={level} text={pages[pageIndex] ?? []} />
      </div>
      {/* Hidden twin used only to measure how much text fits. */}
      <div ref={measureRef} className="story-pages__measure" aria-hidden="true">
        <ReadingPanel title={title} level={level} text={[' ']} />
      </div>
      {pages.length > 1 ? (
        <div className="story-pages__nav">
          {pageIndex > 0 ? (
            <Button variant="secondary" size="kid" onClick={() => setPageIndex((i) => i - 1)}>
              Back
            </Button>
          ) : null}
          <span className="story-pages__dots" aria-hidden="true">
            {pages.map((_, i) => (
              <span
                key={i}
                className={`story-pages__dot${i === pageIndex ? ' story-pages__dot--now' : ''}`}
              />
            ))}
          </span>
          {pageIndex < last ? <RoundButton kind="next" label="Next page" onClick={turn} /> : null}
        </div>
      ) : null}
    </Paper>
  );
}
