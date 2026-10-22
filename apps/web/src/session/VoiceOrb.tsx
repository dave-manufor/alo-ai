// Auntie Kemi's voice, made visible (the "Àlọ́ Night Session V" design).
// A slowly spinning three-lobe aurora with a halo, coloured by state:
// indigo while Kemi speaks, coral while it is the child's turn, blue
// over the listening story. Rings flow out while a voice is active.
// Purely presentational — the session state machine decides the state;
// the orb never advances anything. Decorative, so it is hidden from
// assistive tech; Kemi's words are in the screen-reader-only status.

export type VoiceOrbState = 'speaking' | 'listening' | 'idle';
export type VoiceOrbTone = 'indigo' | 'coral' | 'blue';

const TONE_BY_STATE: Record<VoiceOrbState, VoiceOrbTone> = {
  speaking: 'indigo',
  listening: 'coral',
  idle: 'indigo',
};

export default function VoiceOrb({
  state,
  tone,
  countDots = false,
  small = false,
}: {
  state: VoiceOrbState;
  /** Overrides the colour the state would pick (blue for the listening story). */
  tone?: VoiceOrbTone;
  /** Mic check: five dots light as the child counts to five. */
  countDots?: boolean;
  /** The small listening indicator kept on the reading card. */
  small?: boolean;
}) {
  return (
    <div
      aria-hidden="true"
      className={`voice-orb voice-orb--${state} voice-orb--${tone ?? TONE_BY_STATE[state]}${
        small ? ' voice-orb--small' : ''
      }`}
    >
      <span className="voice-orb__halo" />
      <span className="voice-orb__ring" />
      <span className="voice-orb__ring voice-orb__ring--late" />
      {(['a', 'b', 'c'] as const).map((id) => (
        <span key={id} className={`voice-orb__spin voice-orb__spin--${id}`}>
          <span className="voice-orb__lobe" />
        </span>
      ))}
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
