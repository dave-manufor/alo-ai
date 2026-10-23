import { act, render, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { COUNT_REARM_MS, useCountedWords, type MicMeter } from './micLevel';
import NightStage from './NightStage';
import { defaultInput, type StageInput } from './stageEngine';

// A meter whose level the test sets.
function meterAt(initial = -100) {
  const state = { level: initial, usable: true };
  const meter: MicMeter = { level: () => state.level, usable: () => state.usable, stop: () => undefined };
  return { state, meter };
}

describe('counting along with the child', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  /** One spoken number: a burst of voice, then a gap long enough to be a gap. */
  const say = (state: { level: number }, burstMs = 240, gapMs = COUNT_REARM_MS + 80) => {
    state.level = -25;
    act(() => void vi.advanceTimersByTime(burstMs));
    state.level = -80;
    act(() => void vi.advanceTimersByTime(gapMs));
  };

  it('lights one more for each number the child says, to five and no more', () => {
    const { state, meter } = meterAt();
    const { result } = renderHook(() => useCountedWords(meter, true, 40));
    expect(result.current).toBe(0);
    for (let n = 1; n <= 5; n += 1) {
      say(state);
      expect(result.current).toBe(n);
    }
    say(state); // a sixth: still five
    expect(result.current).toBe(5);
  });

  it('one long word is one number, and a dip inside a word is not a gap', () => {
    const { state, meter } = meterAt();
    const { result } = renderHook(() => useCountedWords(meter, true, 40));
    state.level = -25;
    act(() => void vi.advanceTimersByTime(1_500)); // a long "fiiive"
    expect(result.current).toBe(1);
    state.level = -80;
    act(() => void vi.advanceTimersByTime(COUNT_REARM_MS - 80)); // a breath that is too short
    state.level = -25;
    act(() => void vi.advanceTimersByTime(200));
    expect(result.current).toBe(1);
  });

  it('room noise between the two levels neither counts nor ends a number', () => {
    const { state, meter } = meterAt();
    const { result } = renderHook(() => useCountedWords(meter, true, 40));
    state.level = -48; // above the quiet level, below a voice
    act(() => void vi.advanceTimersByTime(1_000));
    expect(result.current).toBe(0);
  });

  it('does not count while Kemi is speaking, and starts again from zero when it is the child’s turn', () => {
    const { state, meter } = meterAt();
    const { result, rerender } = renderHook(({ active }) => useCountedWords(meter, active, 40), {
      initialProps: { active: true },
    });
    say(state);
    say(state);
    expect(result.current).toBe(2);
    rerender({ active: false }); // Kemi says "count again"
    state.level = -25;
    act(() => void vi.advanceTimersByTime(500));
    expect(result.current).toBe(0);
    state.level = -80;
    rerender({ active: true });
    say(state);
    expect(result.current).toBe(1);
  });

  it('hears nothing from a meter whose audio context is not running, or from no meter', () => {
    const { state, meter } = meterAt();
    state.usable = false;
    const { result } = renderHook(() => useCountedWords(meter, true, 40));
    state.level = -20;
    act(() => void vi.advanceTimersByTime(1_000));
    expect(result.current).toBe(0);
    const none = renderHook(() => useCountedWords(null, true, 40));
    expect(none.result.current).toBe(0);
  });
});

describe('the stage', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const stage = (input: Partial<StageInput>) =>
    render(
      <NightStage
        input={{ ...defaultInput, showStart: false, ...input }}
        story={null}
        start={null}
        hand={null}
        srText={null}
      />,
    );
  const lit = (container: HTMLElement) =>
    [0, 1, 2, 3, 4].map((k) => container.querySelector(`[data-k="c${k}"]`)?.classList.contains('lit'));
  const opacity = (container: HTMLElement, key: string) =>
    Number((container.querySelector(`[data-k="${key}"]`) as HTMLElement).style.opacity);

  it('lights as many count lights as the child has counted, and no timer lights the rest', () => {
    const { container } = stage({ mode: 'count', counting: true, countHeard: 2 });
    act(() => void vi.advanceTimersByTime(8_000)); // long past when a timer would have lit all five
    expect(lit(container)).toEqual([true, true, false, false, false]);
  });

  it('with no measured count the lights come on by themselves, one after another', () => {
    const { container } = stage({ mode: 'count', counting: true, countHeard: null });
    act(() => void vi.advanceTimersByTime(8_000));
    expect(lit(container)).toEqual([true, true, true, true, true]);
  });

  it('shows the turning ring while the session is being made ready, and the caption only after a wait', () => {
    const { container } = stage({ mode: 'call', preparing: true });
    act(() => void vi.advanceTimersByTime(600));
    expect(opacity(container, 'shim')).toBeGreaterThan(0.5);
    expect(opacity(container, 'prepNote')).toBe(0); // a short wait needs no words
    act(() => void vi.advanceTimersByTime(5_000));
    expect(opacity(container, 'prepNote')).toBeGreaterThan(0.5);
    expect(container.querySelector('[data-k="prepNote"]')?.textContent).toMatch(/Getting your reading check ready/);
  });

  it('shows neither when nothing is being prepared', () => {
    const { container } = stage({ mode: 'count', preparing: false });
    act(() => void vi.advanceTimersByTime(6_000));
    expect(opacity(container, 'shim')).toBe(0);
    expect(opacity(container, 'prepNote')).toBe(0);
  });
});
