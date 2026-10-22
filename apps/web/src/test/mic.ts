import { fireEvent, screen } from '@testing-library/react';
import { vi } from 'vitest';

/** Gives the page a fake microphone that is allowed (or blocked with the given error name). */
export function stubMic(outcome: 'allow' | string = 'allow') {
  const stop = vi.fn();
  const getUserMedia = vi.fn(async () => {
    if (outcome !== 'allow') {
      const error = new Error(outcome);
      error.name = outcome;
      throw error;
    }
    return { getTracks: () => [{ stop }] } as unknown as MediaStream;
  });
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  });
  return { getUserMedia, stop };
}

export function removeMic() {
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: undefined });
}

/** Start -> the explainer -> "I'm ready" (the browser would ask here). */
export function startSessionScreen() {
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  fireEvent.click(screen.getByRole('button', { name: /ready/i }));
}
