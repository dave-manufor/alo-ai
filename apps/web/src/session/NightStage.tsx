import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import japaBase from './assets/japa-base.svg';
import japaCheer from './assets/japa-cheer.svg';
import './artifact-tokens.css';
import './nightStage.css';
import { StageEngine, type StageInput } from './stageEngine';

// The kid session screen, ported from the "Alo Night Session V" artifact:
// the markup below is the artifact's `.stage`, the look is nightStage.css,
// the motion is stageEngine.ts. This component only mounts the DOM and
// hands the engine the session's state. No words reach the child except
// the call, the story and the hand-back (the artifact's own rule); what
// Auntie Kemi says is a screen-reader-only live region.

const VOICE: [number, number, string][] = [
  [0.25, 44, '0.00s'],
  [0.59, 80, '-0.10s'],
  [0.48, 76, '-0.20s'],
  [-0.94, -6, '-0.30s'],
  [0.89, 27, '-0.40s'],
  [0.8, -70, '-0.50s'],
  [-0.06, -46, '-0.60s'],
  [0.09, 13, '-0.70s'],
  [-0.97, -51, '-0.80s'],
  [-0.44, 75, '-0.90s'],
  [0.53, -61, '-1.00s'],
  [0.59, -65, '-1.10s'],
  [0.23, -67, '-1.20s'],
  [-1, 67, '-1.30s'],
  [-0.58, -51, '-1.40s'],
  [0.96, 67, '-1.50s'],
];

const orbSet = (color: string, hidden: boolean) => (
  <div className={`set ${color}`} data-k={`os-${color}`} style={hidden ? { opacity: 0 } : undefined}>
    <div className="halo" />
    <div className="spin a">
      <div className="lobe" />
    </div>
    <div className="spin b">
      <div className="lobe" />
    </div>
    <div className="spin c">
      <div className="lobe" />
    </div>
    <div className="core" />
  </div>
);

interface Props {
  input: StageInput;
  story: { title: string; sentences: string[] } | null;
  /** Inside the Start overlay (the greeting, or the microphone explainer). */
  start: ReactNode;
  /** Inside the hand-back overlay (the press-and-hold gate, then the report card). */
  hand: ReactNode;
  /** A grown-up card over the whole screen (microphone off, could not start). */
  grownUp?: ReactNode;
  /** What Auntie Kemi says, for screen readers only. */
  srText: string | null;
}

export default function NightStage({ input, story, start, hand, grownUp, srText }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const engine = useRef<StageEngine | null>(null);
  const latest = useRef({ input, story });
  latest.current = { input, story };

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;
    const e = new StageEngine(root);
    engine.current = e;
    const { input: i, story: s } = latest.current;
    if (s) e.setStory(s.title, s.sentences);
    e.setInput(i);
    return () => {
      e.destroy();
      engine.current = null;
    };
  }, []);

  useEffect(() => {
    engine.current?.setInput(input);
  }, [input]);

  useEffect(() => {
    if (story) engine.current?.setStory(story.title, story.sentences);
  }, [story]);

  return (
    <div className="night-stage" data-theme="dark" ref={rootRef}>
      <div className="l sky dusk" />
      <div className="l sky night" data-k="skyNight" style={{ opacity: 0 }} />
      <div className="l sky deep" data-k="skyDeep" style={{ opacity: 0 }} />
      <div className="l aurset" data-k="aurCoral">
        <div className="l aur a1 coral" />
        <div className="l aur a2 coral" />
      </div>
      <div className="l aurset" data-k="aurIndigo" style={{ opacity: 0 }}>
        <div className="l aur a1 indigo" />
        <div className="l aur a2 blue" />
      </div>
      <div className="l aurset" data-k="aurBlue" style={{ opacity: 0 }}>
        <div className="l aur a1 blue" />
        <div className="l aur a2 blue" />
      </div>
      <div className="l aurset" data-k="aurGold" style={{ opacity: 0 }}>
        <div className="l aur a1 gold" />
        <div className="l aur a2 indigo" />
      </div>
      <div className="l stars" data-k="stars1" style={{ opacity: 0 }} />
      <div className="l stars stars2" data-k="stars2" style={{ opacity: 0 }} />
      <svg className="l const" data-k="const" aria-hidden="true" />
      <div className="l rainbox" data-k="rain" style={{ opacity: 0 }}>
        <div className="l rain r2" />
        <div className="l rain" />
      </div>
      <div className="l orb" data-k="orb" aria-hidden="true">
        <div className="lvl" data-k="orbLvl">
          {orbSet('coral', false)}
          {orbSet('indigo', true)}
          {orbSet('blue', true)}
          {orbSet('gold', true)}
          <div className="shim" data-k="shim" style={{ opacity: 0 }}>
            <i />
          </div>
          <div className="outline" data-k="outline" style={{ opacity: 0 }}>
            <i />
          </div>
          <div className="rings" data-k="rings" style={{ opacity: 0 }}>
            <i />
            <i />
            <i />
          </div>
        </div>
      </div>
      <div className="l voice" data-k="voice" aria-hidden="true">
        {VOICE.map(([f, w, d]) => (
          <i key={d} data-f={f} style={{ '--w': `${w}px`, '--d': d } as CSSProperties} />
        ))}
      </div>
      <svg className="l glyph" data-k="g0" width="58" height="58" viewBox="0 0 58 58" aria-hidden="true">
        <circle cx="29" cy="29" r="24" pathLength="1" />
        <path d="M29 19 L38.5 25.9 L34.9 37.1 L23.1 37.1 L19.5 25.9Z" pathLength="1" />
        <path d="M29 19V5 M38.5 25.9L51.5 21.6 M34.9 37.1L42.9 48.4 M23.1 37.1L15.1 48.4 M19.5 25.9L6.5 21.6" pathLength="1" />
      </svg>
      <svg className="l glyph" data-k="g1" width="70" height="54" viewBox="0 0 70 54" aria-hidden="true">
        <path d="M10 30 Q12 20 26 20 H44 Q50 20 52 16 L56 9 M52 16 Q60 17 62 24 Q62 31 55 30 Q50 30 48 28 Q46 36 40 37 H22 Q13 37 10 30Z" pathLength="1" />
        <path d="M16 36 V50 M24 37 V50 M39 37 V50 M45 35 V50 M56 9 Q53 2 46 3 M58 11 Q62 4 68 6 M10 30 Q4 28 4 22" pathLength="1" />
      </svg>
      {[0, 1, 2, 3, 4].map((k) => (
        <div key={`c${k}`} className="l pt8" data-k={`c${k}`} aria-hidden="true" />
      ))}
      {[0, 1, 2].map((k) => (
        <div key={`q${k}`} className="l pt8" data-k={`q${k}`} aria-hidden="true" />
      ))}
      <div className="l call" data-k="call" aria-hidden="true">
        Àlọ́ o!
      </div>
      <div className="l page" data-k="page" data-theme="light">
        <div className="ph" data-k="ph">
          <small>Your story</small>
          <h3 data-k="ptitle">{story?.title}</h3>
        </div>
        <div className="pt" data-k="pt">
          <p data-k="ptext" />
        </div>
        <div className="pf">
          <div className="pdots" data-k="pdots" aria-hidden="true" />
          <button
            type="button"
            className="next"
            data-k="next"
            aria-label="Next page"
            onClick={() => engine.current?.turnPage()}
          >
            <span className="rip" data-k="nrip" />
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--on-night)' }} aria-hidden="true">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </button>
        </div>
      </div>
      <div className="l page measure" data-k="mpage" data-theme="light" aria-hidden="true">
        <div className="ph" data-k="mph">
          <small>Your story</small>
          <h3 data-k="mtitle" />
        </div>
        <div className="pt" data-k="mpt">
          <p data-k="mtext" />
        </div>
        <div className="pf" />
      </div>
      <div className="l japa" data-k="jpeek" aria-hidden="true">
        <img src={japaBase} alt="" />
      </div>
      <div className="l japa" data-k="jnod" aria-hidden="true">
        <img src={japaBase} alt="" />
      </div>
      <div className="l japa" data-k="jcheer" aria-hidden="true">
        <img src={japaCheer} alt="" />
      </div>
      <div className="l gstar" data-k="gstar" aria-hidden="true">
        <svg viewBox="-10 -10 20 20">
          <path d="M0-9 L2.4-2.6 L9-2.6 L3.6 1.6 L5.6 8.4 L0 4.2 L-5.6 8.4 L-3.6 1.6 L-9-2.6 L-2.4-2.6Z" style={{ fill: 'var(--art-star)' }} />
        </svg>
      </div>
      <div className="l ov startov" data-k="startov">
        <div className="startbox">{start}</div>
      </div>
      <div className="l ov handov" data-k="handov" data-theme="dark">
        {hand}
      </div>
      <p className="l prep" data-k="prepNote" aria-hidden="true" style={{ opacity: 0 }}>
        Getting your reading check ready…
      </p>
      <div className="l grain" aria-hidden="true" />
      <div className="l vignette" data-k="vig" aria-hidden="true" />
      {grownUp}
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {srText}
      </p>
    </div>
  );
}

