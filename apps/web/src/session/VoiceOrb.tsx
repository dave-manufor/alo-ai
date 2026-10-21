// Auntie Kemi's voice, made visible (the "Àlọ́ Night Session" demo).
// The orb is the only thing on screen while Kemi speaks or listens:
// it glows and breathes while a clip plays, settles while it is the
// child's turn, and lights a row of count dots during the mic check.
// Purely presentational — the session state machine decides when a
// clip is playing; the orb never advances anything. Decorative, so it
// is hidden from assistive tech; Kemi's words are in the SpeechBubble.

export type VoiceOrbState = 'speaking' | 'listening' | 'idle';

export default function VoiceOrb({
  state,
  countDots = false,
  small = false,
}: {
  state: VoiceOrbState;
  /** Mic check: five dots light as the child counts to five. */
  countDots?: boolean;
  /** The small listening indicator kept on the reading card. */
  small?: boolean;
}) {
  return (
    <div
      aria-hidden="true"
      className={`voice-orb voice-orb--${state}${small ? ' voice-orb--small' : ''}`}
    >
      <span className="voice-orb__ring voice-orb__ring--outer" />
      <span className="voice-orb__ring voice-orb__ring--inner" />
      <span className="voice-orb__core" />
      {countDots ? (
        <span className="voice-orb__dots">
          {[0, 1, 2, 3, 4].map((dot) => (
            <span key={dot} className="voice-orb__dot" style={{ animationDelay: `${dot * 0.45}s` }} />
          ))}
        </span>
      ) : null}
    </div>
  );
}
