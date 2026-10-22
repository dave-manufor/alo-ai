import { useEffect, useId, useRef, useState } from 'react';

// "Grown-ups: press and hold" (the "Àlọ́ Night Session" demo). The
// grown-up gate at the end of a kid session: a child tapping happily
// cannot complete it by accident, because the press must be held for
// the full duration; letting go early starts again. Works by pointer
// and by holding Enter/Space on a keyboard, with a hint saying so.
// The ring fills as the hold progresses; under
// `prefers-reduced-motion: reduce` the intermediate fill is skipped
// and a press completes at once, so the ring simply appears filled.
const HOLD_MS = 2000;
const TICK_MS = 50;

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

export default function HoldToConfirm({
  label,
  onComplete,
}: {
  label: string;
  onComplete: () => void;
}) {
  const [progress, setProgress] = useState(0);
  const timer = useRef<number | null>(null);
  const hintId = useId();

  function clearTimer() {
    if (timer.current !== null) {
      window.clearInterval(timer.current);
      timer.current = null;
    }
  }

  function cancel() {
    clearTimer();
    setProgress(0);
  }

  function start() {
    if (timer.current !== null) return;
    if (prefersReducedMotion()) {
      setProgress(1);
      onComplete();
      return;
    }
    const startedAt = Date.now();
    timer.current = window.setInterval(() => {
      const next = (Date.now() - startedAt) / HOLD_MS;
      if (next >= 1) {
        clearTimer();
        setProgress(1);
        onComplete();
      } else {
        setProgress(next);
      }
    }, TICK_MS);
  }

  // On unmount only the interval needs clearing; no state update.
  useEffect(() => clearTimer, []);

  const ringRadius = 16;
  const circumference = 2 * Math.PI * ringRadius;

  return (
    <>
      <button
        type="button"
        className="hold"
        aria-label={label}
        aria-describedby={hintId}
        onPointerDown={start}
        onPointerUp={cancel}
        onPointerLeave={cancel}
        onPointerCancel={cancel}
        onContextMenu={(event) => event.preventDefault()}
        onKeyDown={(event) => {
          if ((event.key === 'Enter' || event.key === ' ') && !event.repeat) start();
        }}
        onKeyUp={(event) => {
          if (event.key === 'Enter' || event.key === ' ') cancel();
        }}
        onBlur={cancel}
      >
        <svg viewBox="0 0 40 40" aria-hidden="true">
          <circle className="track" cx="20" cy="20" r={ringRadius} />
          <circle
            className="fill"
            cx="20"
            cy="20"
            r={ringRadius}
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - progress)}
          />
        </svg>
        <span>{label}</span>
      </button>
      <span id={hintId} className="sr-only">
        Keep holding until the ring fills — press and hold, or hold the Enter or Space key.
      </span>
    </>
  );
}
