import { useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { accountStore } from '../account/store';
import {
  Button,
  Japa,
  MicButton,
  MoonProgress,
  RewardBadge,
  SpeechBubble,
} from '../design-system/alo';
import { dataMode } from '../api';
import { createSessionClipCache, unlockAudio } from '../session/clipCache';
import type { ChildEvent, SessionDriver } from '../session/driver';
import { createSessionDriver } from '../session/driverFactory';
import HoldToConfirm from '../session/HoldToConfirm';
import type { AgentMessage } from '../session/protocol';
import {
  applyAgentMessage,
  initialSessionState,
  readingLevelForArl,
  recordAck,
} from '../session/sessionState';
import { requestMic, type MicResult } from '../session/micPermission';
import StoryPages from '../session/StoryPages';
import VoiceOrb from '../session/VoiceOrb';

const TOPICS: { label: string; icon: 'book' | 'star' | 'lantern' | 'ear' }[] = [
  { label: 'Animals', icon: 'book' },
  { label: 'Football', icon: 'star' },
  { label: 'Space', icon: 'lantern' },
  { label: 'Food', icon: 'ear' },
];

const STEP_INDEX: Record<string, number> = {
  INTEREST_CHAT: 0,
  MIC_CHECK: 0,
  READING: 1,
  RETELL: 2,
  QUESTIONS: 3,
  LISTENING: 3,
  CLOSE: 3,
  ENDED: 3,
};

// Kid mode session screen (PRD 4.1, 4.4), rebuilt on the "Àlọ́ Night
// Session" demo: a Night-theme screen where Kemi is a glowing voice
// orb, the story arrives on a raised card, and the reward is a moon
// and a constellation before the grown-up handover. The gate comes
// first: no signed-in guardian + no per-child consent record, no
// session (PRD 12). The screen follows the agent's protocol v2
// messages only — step, clip texts for the bubble, the story from
// show_passage — and never moves the session on itself. In this phase
// a fixture driver emits those messages; the LiveKit driver in #24's
// protocol replaces it. The told word is the agent's decision during
// reading, never a child's button. Children never see a score, timer,
// percentage or red mark.
export default function SessionPage({
  createDriver,
}: {
  /** Overrides which SessionDriver carries the session (tests). By default the
   *  build decides (driverFactory): fixture replay, or LiveKit in a live build. */
  createDriver?: () => SessionDriver;
} = {}) {
  const { childId } = useParams();
  const navigate = useNavigate();
  const [started, setStarted] = useState(false);
  // Before the session: 'greeting' (Start) -> 'explain' (why the mic, before the browser
  // asks) -> started, or 'blocked' / 'unavailable' (a grown-up screen to recover).
  const [micPhase, setMicPhase] = useState<'greeting' | 'explain' | MicResult>('greeting');
  const [state, setState] = useState(initialSessionState);
  const [starsCollected, setStarsCollected] = useState(false);
  const [handedOver, setHandedOver] = useState(false);
  const driverRef = useRef<SessionDriver | null>(null);

  // Fixture build: clips are simulated locally. Live build: every clip is
  // downloaded into Cache Storage before it can be played (D4).
  const clipCache = useMemo(() => createSessionClipCache(), []);
  const [failure, setFailure] = useState<string | null>(null);

  async function dispatch(message: AgentMessage) {
    if (message.cmd === 'clip_list') {
      await clipCache.downloadAll(message.clips);
    }
    setState((current) =>
      applyAgentMessage(current, message, (clipId) => clipCache.textFor(clipId)),
    );
    if (message.cmd === 'play') {
      const ack = await clipCache.play(message.clip_id);
      setState((current) => recordAck(current, ack));
      driverRef.current?.ack?.(ack); // live: tell the agent played / missing
    }
  }

  function startSession() {
    // A live session needs the internet to download its clips: refuse cleanly.
    if (dataMode === 'live' && typeof navigator !== 'undefined' && navigator.onLine === false) {
      setFailure('The reading check needs the internet to start. Please connect and try again.');
      return;
    }
    setFailure(null);
    const driver = (createDriver ?? (() => createSessionDriver(childId ?? '')))();
    driverRef.current = driver;
    driver.onFailed?.((plain) => setFailure(plain));
    driver.start(dispatch);
  }

  function retrySession() {
    driverRef.current?.stop();
    setState(initialSessionState);
    startSession();
  }

  async function askForMic() {
    const result = await requestMic();
    if (result === 'granted') {
      setMicPhase('granted');
      setStarted(true);
      startSession();
    } else {
      setMicPhase(result);
    }
  }

  function driverEvent(event: ChildEvent) {
    driverRef.current?.send(event);
  }

  useEffect(
    () => () => {
      driverRef.current?.stop();
    },
    [],
  );

  // The mic gate (PRD 12): this child's consent record must exist.
  if (!childId || !accountStore.canStartSession(childId)) {
    return <Navigate to="/children" replace />;
  }

  const childName =
    accountStore.getState().children.find((child) => child.child_id === childId)?.first_name ??
    'Your child';

  const step = state.step;
  const speaking = state.playingClipId !== null;
  const listening =
    !speaking &&
    (step === 'INTEREST_CHAT' ||
      step === 'MIC_CHECK' ||
      step === 'READING' ||
      step === 'RETELL' ||
      step === 'QUESTIONS' ||
      step === 'LISTENING');
  const orbState = speaking ? 'speaking' : listening ? 'listening' : 'idle';

  return (
    <main
      className={`night-session${step === 'LISTENING' ? ' night-session--rain' : ''}`}
      data-theme="dark"
    >
      <div className="night-stars" aria-hidden="true" />
      {/* What Auntie Kemi says, for screen readers and tests only (the
          design shows no words on the child's screen; README deviation
          B2). The text is the playing clip's exact words from clip_list. */}
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {started && !state.reconnecting ? state.bubbleText : null}
      </p>
      {handedOver || micPhase === 'denied' || micPhase === 'unavailable' ? null : (
        <MoonProgress
          steps={['Say hello', 'Read', 'Tell', 'Answer']}
          current={step ? STEP_INDEX[step] : 0}
        />
      )}

      {micPhase === 'explain' ? (
        <section className="night-centre">
          <Japa pose="happy" />
          <p className="kid-title">Auntie Kemi needs to hear you</p>
          <p className="kid-body">
            Ask a grown-up to tap Allow when the phone asks about the microphone.
          </p>
          <Button variant="primary" size="kid" onClick={() => void askForMic()}>
            I’m ready
          </Button>
        </section>
      ) : null}

      {micPhase === 'denied' || micPhase === 'unavailable' ? (
        <section className="night-centre night-grownup">
          <div className="night-report-card">
            <h1 className="title">
              {micPhase === 'denied' ? 'The microphone is turned off' : 'No microphone found'}
            </h1>
            <p className="body">
              Alo.ai listens to your child read aloud, so it needs the microphone.
              {micPhase === 'denied'
                ? ' To turn it on:'
                : ' Please check that a microphone is working on this phone, and that you are using Chrome.'}
            </p>
            {micPhase === 'denied' ? (
              <ol className="body">
                <li>Tap the icon next to the web address at the top of the screen.</li>
                <li>Open Permissions, then set Microphone to Allow.</li>
                <li>Come back here and tap Try again.</li>
              </ol>
            ) : null}
            <div className="row">
              <Button variant="primary" size="grown" onClick={() => void askForMic()}>
                Try again
              </Button>
              <Button variant="secondary" size="grown" onClick={() => navigate('/children')}>
                Back to your children
              </Button>
            </div>
          </div>
        </section>
      ) : null}

      {micPhase === 'greeting' ? (
        <section className="night-centre">
          <SpeechBubble tone="call">Àlọ́ o!</SpeechBubble>
          <Japa pose="happy" />
          <button
            type="button"
            className="night-start"
            onClick={() => {
              unlockAudio();
              setMicPhase('explain');
            }}
          >
            <span className="night-start__circle" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="40" height="40">
                <path d="M8 5v14l11-7z" fill="currentColor" />
              </svg>
            </span>
            <span className="night-start__label">Start</span>
          </button>
        </section>
      ) : null}

      {failure ? (
        <section className="night-centre">
          <div className="night-report-card" role="alert">
            <h1 className="title">We could not start</h1>
            <p className="body">{failure}</p>
            <div className="row">
              <Button variant="primary" size="grown" onClick={retrySession}>
                Try again
              </Button>
              <Button variant="secondary" size="grown" onClick={() => navigate('/children')}>
                Back to your children
              </Button>
            </div>
          </div>
        </section>
      ) : null}

      {started && !failure && state.reconnecting ? (
        <section className="night-centre">
          <VoiceOrb state="idle" />
          <SpeechBubble>Let’s wait for the internet.</SpeechBubble>
          <Japa pose="thinking" />
        </section>
      ) : null}

      {started && !state.reconnecting && step === 'INTEREST_CHAT' ? (
        <section className="night-centre">
          <VoiceOrb state={orbState} />
          <div className="night-topics">
            {TOPICS.map((topic) => (
              <Button
                key={topic.label}
                variant="secondary"
                size="kid"
                icon={topic.icon}
                onClick={() => driverEvent('topic_chosen')}
              >
                {topic.label}
              </Button>
            ))}
          </div>
        </section>
      ) : null}

      {started && !state.reconnecting && step === 'MIC_CHECK' ? (
        <section className="night-centre">
          <VoiceOrb state={orbState} countDots />
          <MicButton state={listening ? 'listening' : 'idle'} onClick={() => driverEvent('child_spoke')} />
        </section>
      ) : null}

      {started && !state.reconnecting && step === 'READING' && state.passageVisible && state.passage ? (
        <section className="night-reading">
          <span className="night-reading__head">
            <VoiceOrb state={orbState} small />
            <p className="label night-eyebrow">Your story</p>
          </span>
          <StoryPages
            title={state.passage.title}
            level={readingLevelForArl(state.passage.arl)}
            sentences={state.passage.sentences}
          />
          <MicButton state={listening ? 'listening' : 'idle'} onClick={() => driverEvent('child_spoke')} />
        </section>
      ) : null}

      {started &&
      !state.reconnecting &&
      (step === 'RETELL' || step === 'QUESTIONS' || step === 'LISTENING') ? (
        <section className="night-centre">
          <VoiceOrb state={orbState} />
          <MicButton state={listening ? 'listening' : 'idle'} onClick={() => driverEvent('child_spoke')} />
        </section>
      ) : null}

      {started &&
      !state.reconnecting &&
      (step === 'CLOSE' || step === 'ENDED') &&
      !starsCollected ? (
        <section className="night-centre">
          <span className="night-moon" aria-hidden="true" />
          <svg
            className="night-constellation"
            viewBox="0 0 200 70"
            aria-hidden="true"
          >
            <polyline points="10,55 45,20 90,8 140,22 168,40 188,58" pathLength={100} />
            <circle className="night-constellation__star" cx="188" cy="58" r="4" />
          </svg>
          <Japa pose="cheer" />
          <RewardBadge kind="teller" earned />
          <Button
            variant="reward"
            size="kid"
            icon="star"
            onClick={() => setStarsCollected(true)}
          >
            Collect stars
          </Button>
        </section>
      ) : null}

      {/* Keyed on starsCollected, not the step: if the agent moves to
          ENDED while the grown-up is holding, the handover must not
          vanish mid-hold. */}
      {started && starsCollected && !handedOver ? (
        <section className="night-centre">
          <Japa pose="happy" />
          <p className="kid-title">Please give the phone to a grown-up</p>
          <HoldToConfirm
            label="Grown-ups: press and hold"
            onComplete={() => setHandedOver(true)}
          />
        </section>
      ) : null}

      {started && handedOver ? (
        <section className="night-centre">
          <div className="night-report-card">
            <p className="caption muted">Reading check · today</p>
            <h2 className="title">{childName}&apos;s report is ready</h2>
            <p className="body">See how {childName} read and what to try this week.</p>
            <Button variant="primary" size="grown" onClick={() => navigate('/reports')}>
              See the report
            </Button>
          </div>
        </section>
      ) : null}
    </main>
  );
}
