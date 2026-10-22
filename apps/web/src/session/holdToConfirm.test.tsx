import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import HoldToConfirm from './HoldToConfirm';

describe('HoldToConfirm (the grown-ups gate)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('does not complete on a quick tap, and completes when held the full time', () => {
    const done = vi.fn();
    render(<HoldToConfirm label="Grown-ups: press and hold" onComplete={done} />);
    const button = screen.getByRole('button', { name: /press and hold/i });
    fireEvent.pointerDown(button);
    act(() => void vi.advanceTimersByTime(500));
    fireEvent.pointerUp(button);
    act(() => void vi.advanceTimersByTime(3000));
    expect(done).not.toHaveBeenCalled();
    fireEvent.pointerDown(button);
    act(() => void vi.advanceTimersByTime(2100));
    expect(done).toHaveBeenCalledTimes(1);
  });

  it('works by holding Space or Enter, for keyboard users', () => {
    const done = vi.fn();
    render(<HoldToConfirm label="Grown-ups: press and hold" onComplete={done} />);
    const button = screen.getByRole('button', { name: /press and hold/i });
    fireEvent.keyDown(button, { key: ' ' });
    act(() => void vi.advanceTimersByTime(2100));
    expect(done).toHaveBeenCalledTimes(1);
  });

  it('completes at once when the child prefers reduced motion', () => {
    const done = vi.fn();
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    render(<HoldToConfirm label="Grown-ups: press and hold" onComplete={done} />);
    fireEvent.pointerDown(screen.getByRole('button', { name: /press and hold/i }));
    expect(done).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });
});
