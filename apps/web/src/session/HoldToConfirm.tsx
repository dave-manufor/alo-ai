import { useEffect, useRef, useState } from 'react';

// "Grown-ups: press and hold" (the "Àlọ́ Night Session" demo). The
// grown-up gate at the end of a kid session: a child tapping happily
// cannot complete it by accident, because the press must be held for
// the full duration; letting go early starts again. Works by pointer
// and by holding Enter/Space on a keyboard. The ring fills as the
// hold progresses (motion the design system allows: it is the control
// itself showing its state, and it stops under reduced motion where
// the fill simply appears at the end).
const HOLD_MS = 1000;
const TICK_MS = 50;

export default function HoldToConfirm({
  label,
  onComplete,
}: {
  label: string;
  onComplete: () => void;
}) {
  const [progress, setProgress] = useState(0);
  const timer = useRef<number | null>(null);

  function cancel() {
    if (timer.current !== null) {
      window.clearInterval(timer.current);
      timer.current = null;
    }
    setProgress(0);
  }

  function start() {
    if (timer.current !== null) return;
    const startedAt = Date.now();
    timer.current = window.setInterval(() => {
      const next = (Date.now() - startedAt) / HOLD_MS;
      if (next >= 1) {
        cancel();
        setProgress(1);
        onComplete();
      } else {
        setProgress(next);
      }
    }, TICK_MS);
  }

  useEffect(() => cancel, []);

  const ringRadius = 10;
  const circumference = 2 * Math.PI * ringRadius;

  return (
    <button
      type="button"
      className="hold-to-confirm"
      aria-label={label}
      onPointerDown={start}
      onPointerUp={cancel}
      onPointerLeave={cancel}
      onKeyDown={(event) => {
        if ((event.key === 'Enter' || event.key === ' ') && !event.repeat) start();
      }}
      onKeyUp={(event) => {
        if (event.key === 'Enter' || event.key === ' ') cancel();
      }}
      onBlur={cancel}
    >
      <svg className="hold-to-confirm__ring" viewBox="0 0 24 24" aria-hidden="true">
        <circle className="hold-to-confirm__track" cx="12" cy="12" r={ringRadius} />
        <circle
          className="hold-to-confirm__fill"
          cx="12"
          cy="12"
          r={ringRadius}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - progress)}
        />
      </svg>
      <span>{label}</span>
    </button>
  );
}
