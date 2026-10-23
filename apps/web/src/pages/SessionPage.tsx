import { useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { accountStore } from '../account/store';
import { dataMode } from '../api';
import { createSessionClipCache, unlockAudio } from '../session/clipCache';
import type { SessionDriver } from '../session/driver';
import { createSessionDriver } from '../session/driverFactory';
import HoldToConfirm from '../session/HoldToConfirm';
import { requestMic, type MicResult } from '../session/micPermission';
import japaBase from '../session/assets/japa-base.svg';
import NightStage from '../session/NightStage';
import type { AgentMessage } from '../session/protocol';
import { applyAgentMessage, initialSessionState, recordAck } from '../session/sessionState';
import type { Mode, StageInput } from '../session/stageEngine';

// How long the moon, the constellation and the child's star stay before the
// hand-back (the artifact: 8 s after the light becomes the moon).
const END_MS = 8000;
const QUESTION_CLIP = /^question:(\d+)$/;

// Kid mode session screen (PRD 4.1, 4.4): the "Alo Night Session V" design.
// One night sky; Auntie Kemi is a light that moves (centre, the corner while
// the child reads, the moon at the end); the story is a page the child turns
// with the arrow; the only other control is Start and the grown-ups' press and
// hold. The gate comes first: no signed-in guardian + no per-child consent
// record, no session (PRD 12). The screen follows the agent's protocol v2
// messages only (step, clips, show_passage) and never moves the session on
// itself. Children never see a score, timer, percentage or red mark.
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
  // asks) -> started, or 'blocked' / 'unavailable' (a grown-up card to recover).
  const [micPhase, setMicPhase] = useState<'greeting' | 'explain' | MicResult>('greeting');
  const [state, setState] = useState(initialSessionState);
  const [questionsLit, setQuestionsLit] = useState(0);
  const [endDone, setEndDone] = useState(false);
  const [reported, setReported] = useState(false);
  const driverRef = useRef<SessionDriver | null>(null);

  // Fixture build: clips are simulated locally. Live build: every clip is
  // downloaded into Cache Storage before it can be played (D4).
  const clipCache = useMemo(() => createSessionClipCache(), []);
  const [failure, setFailure] = useState<string | null>(null);

  async function dispatch(message: AgentMessage) {
    if (message.cmd === 'clip_list') {
      await clipCache.downloadAll(message.clips);
    }
    if (message.cmd === 'play') {
      const q = QUESTION_CLIP.exec(message.clip_id);
      if (q) setQuestionsLit((n) => Math.max(n, Number(q[1])));
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
    setQuestionsLit(0);
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

  useEffect(
    () => () => {
      driverRef.current?.stop();
    },
    [],
  );

  const step = state.step;
  const ending = step === 'CLOSE' || step === 'ENDED';
  // After the closing praise: the moon and the star, then the hand-back.
  useEffect(() => {
    if (!ending) return undefined;
    const id = window.setTimeout(() => setEndDone(true), END_MS);
    return () => window.clearTimeout(id);
  }, [ending]);

  const speaking = state.playingClipId !== null;
  const savedEarly = started && failure !== null && step !== null;
  const reading = step === 'READING' && state.passageVisible && state.passage !== null;

  let mode: Mode = 'start';
  if (started) {
    if (savedEarly) mode = 'hand';
    else if (state.reconnecting) mode = 'reconnect';
    else if (step === null) mode = 'call';
    else if (step === 'INTEREST_CHAT') mode = 'seeds';
    else if (step === 'MIC_CHECK')
      mode = state.playingClipId === 'story_almost_ready' ? 'think' : 'count';
    else if (step === 'READING') mode = reading ? 'reading' : 'think';
    else if (step === 'RETELL') mode = 'retell';
    else if (step === 'QUESTIONS') mode = 'questions';
    else if (step === 'LISTENING') mode = 'listen';
    else mode = endDone ? 'hand' : 'end';
  }

  const input = useMemo<StageInput>(
    () => ({
      mode,
      speaking,
      childSpeaking: state.childSpeaking,
      counting: mode === 'count' && !speaking,
      questionsLit: ending ? 3 : questionsLit,
      seeds: 0,
      peek: mode === 'reading' && (state.playingClipId?.startsWith('word_') ?? false),
      nod: false,
      pageVisible: state.passageVisible && state.passage !== null,
      showStart: micPhase === 'greeting' || micPhase === 'explain',
    }),
    [
      mode,
      speaking,
      ending,
      questionsLit,
      state.childSpeaking,
      state.playingClipId,
      state.passageVisible,
      state.passage,
      micPhase,
    ],
  );

  const story = useMemo(
    () => (state.passage ? { title: state.passage.title, sentences: state.passage.sentences } : null),
    [state.passage],
  );

  // The mic gate (PRD 12): this child's consent record must exist.
  if (!childId || !accountStore.canStartSession(childId)) {
    return <Navigate to="/children" replace />;
  }

  const childName =
    accountStore.getState().children.find((child) => child.child_id === childId)?.first_name ??
    'Your child';

  const start =
    micPhase === 'explain' ? (
      <div className="handbox">
        <div className="jp">
          <img src={japaBase} alt="" />
        </div>
        <h4>Auntie Kemi needs to hear you</h4>
        <p>Ask a grown-up to tap Allow when the phone asks about the microphone.</p>
        <button type="button" className="pill" onClick={() => void askForMic()}>
          I’m ready
        </button>
      </div>
    ) : (
      <>
        <div className="jp">
          <img src={japaBase} alt="" />
        </div>
        <button
          type="button"
          className="startbtn"
          aria-label="Start"
          onClick={() => {
            unlockAudio();
            setMicPhase('explain');
          }}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M7 4.5v15l13-7.5z" style={{ fill: 'var(--night-edge)' }} />
          </svg>
        </button>
        <b aria-hidden="true">Start</b>
      </>
    );

  const hand = (
    <>
      <div className={`handbox${reported ? ' gone' : ''}`}>
        <div className="jp">
          <img src={japaBase} alt="" />
        </div>
        <h4>Please give the phone to a grown-up</h4>
        <HoldToConfirm label="Grown-ups: press and hold" onComplete={() => setReported(true)} />
      </div>
      <div className={`report${reported ? ' shown' : ''}`} data-theme="light">
        <small>{savedEarly ? 'Reading check · saved' : 'Reading check · today'}</small>
        <h5>
          {savedEarly ? `We saved ${childName}’s reading` : `${childName}’s reading check is done`}
        </h5>
        <p>
          {savedEarly
            ? 'The internet dropped, so the check stopped early. You’ll be offered a new session later, with a different story.'
            : `The report is being made. See how ${childName} read and what to try this week.`}
        </p>
        <button
          type="button"
          className="cta"
          tabIndex={reported ? 0 : -1}
          onClick={() => {
            const sessionId = driverRef.current?.sessionId?.();
            navigate(
              savedEarly ? '/children' : sessionId ? `/reports?pending=${encodeURIComponent(sessionId)}` : '/reports',
            );
          }}
        >
          {savedEarly ? 'Back to your children' : 'See the report'}
        </button>
      </div>
    </>
  );

  const blocked = micPhase === 'denied' || micPhase === 'unavailable';
  const failedToStart = failure !== null && !savedEarly;
  const grownUp =
    blocked || failedToStart ? (
      <div className="l grownup" data-theme="dark">
        <div className="report" data-theme="light" role={failedToStart ? 'alert' : undefined}>
          <h5>
            {failedToStart
              ? 'We could not start'
              : micPhase === 'denied'
                ? 'The microphone is turned off'
                : 'No microphone found'}
          </h5>
          {failedToStart ? (
            <p>{failure}</p>
          ) : (
            <>
              <p>
                Alo.ai listens to your child read aloud, so it needs the microphone.
                {micPhase === 'denied'
                  ? ' To turn it on:'
                  : ' Please check that a microphone is working on this phone, and that you are using Chrome.'}
              </p>
              {micPhase === 'denied' ? (
                <ol>
                  <li>Tap the icon next to the web address at the top of the screen.</li>
                  <li>Open Permissions, then set Microphone to Allow.</li>
                  <li>Come back here and tap Try again.</li>
                </ol>
              ) : null}
            </>
          )}
          <div className="row">
            <button
              type="button"
              className="cta"
              onClick={() => (failedToStart ? retrySession() : void askForMic())}
            >
              Try again
            </button>
            <button type="button" className="cta2" onClick={() => navigate('/children')}>
              Back to your children
            </button>
          </div>
        </div>
      </div>
    ) : null;

  return (
    <NightStage
      input={input}
      story={story}
      start={start}
      hand={hand}
      grownUp={grownUp}
      srText={started && !state.reconnecting ? state.bubbleText : null}
    />
  );
}
