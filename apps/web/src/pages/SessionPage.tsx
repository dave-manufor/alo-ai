import { useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { accountStore } from '../account/store';
import { dataMode } from '../api';
import { createSessionClipCache, unlockAudio } from '../session/clipCache';
import type { SessionDriver } from '../session/driver';
import { createSessionDriver } from '../session/driverFactory';
import HoldToConfirm from '../session/HoldToConfirm';
import {
  createMicMeter,
  primeAudioContext,
  useCountedWords,
  useMicWatch,
  type MicMeter,
} from '../session/micLevel';
import { openMic, stopMic, type MicResult } from '../session/micPermission';
import japaBase from '../session/assets/japa-base.svg';
import NightStage from '../session/NightStage';
import type { AgentMessage } from '../session/protocol';
import { applyAgentMessage, initialSessionState, recordAck } from '../session/sessionState';
import type { Mode, StageInput } from '../session/stageEngine';

// How long the moon, the constellation and the child's star stay before the
// hand-back (the artifact: 8 s after the light becomes the moon).
const END_MS = 8000;
const QUESTION_CLIP = /^question:(\d+)$/;
// How long showing the passage waits for its word clips (they are listed first).
const WORD_CLIPS_WAIT_MS = 8000;
// The steps in which the child is expected to talk.
const LISTEN_STEPS = new Set([
  'INTEREST_CHAT',
  'MIC_CHECK',
  'READING',
  'RETELL',
  'QUESTIONS',
  'LISTENING',
]);

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
  createMeter = createMicMeter,
}: {
  /** Overrides which SessionDriver carries the session (tests). By default the
   *  build decides (driverFactory): fixture replay, or LiveKit in a live build. */
  createDriver?: () => SessionDriver;
  /** Overrides how the microphone level is measured (tests). */
  createMeter?: (stream: MediaStream) => MicMeter;
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
  // The one microphone capture: published to the room, and measured for the green lights.
  const micStreamRef = useRef<MediaStream | null>(null);
  const meterRef = useRef<MicMeter | null>(null);
  const [meter, setMeter] = useState<MicMeter | null>(null);
  const [quietDismissed, setQuietDismissed] = useState(false);
  // The next clip is still loading: the session is being made ready behind the scenes.
  const [waitingClip, setWaitingClip] = useState(false);

  // Fixture build: clips are simulated locally. Live build: every clip is
  // downloaded into Cache Storage before it can be played (D4).
  const clipCache = useMemo(() => createSessionClipCache(), []);
  const [failure, setFailure] = useState<string | null>(null);

  async function dispatch(message: AgentMessage) {
    if (message.cmd === 'clip_list') {
      // Downloaded in the background: nothing waits for the whole list, and a clip is
      // played as soon as its own download is done (a `play` jumps the queue).
      void clipCache.downloadAll(message.clips);
    }
    if (message.cmd === 'show_passage') {
      // Reading starts with the word clips ready ("That word is X." must start at once),
      // but never waits for the rest of the list, and never for long.
      await clipCache.settled((id) => id.startsWith('word_'), WORD_CLIPS_WAIT_MS);
    }
    if (message.cmd === 'play') {
      const q = QUESTION_CLIP.exec(message.clip_id);
      if (q) setQuestionsLit((n) => Math.max(n, Number(q[1])));
    }
    setState((current) =>
      applyAgentMessage(current, message, (clipId) => clipCache.textFor(clipId)),
    );
    if (message.cmd === 'play') {
      if (!clipCache.has(message.clip_id)) setWaitingClip(true); // still downloading
      const ack = await clipCache.play(message.clip_id);
      setWaitingClip(false);
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
    const driver = (
      createDriver ?? (() => createSessionDriver(childId ?? '', micStreamRef.current ?? undefined))
    )();
    driverRef.current = driver;
    driver.onFailed?.((plain) => setFailure(plain));
    driver.start(dispatch);
  }

  // Opens the microphone and starts measuring it. Stopping a driver ends the track it
  // published, so a fresh capture is opened for every (re)start.
  async function acquireMic(): Promise<MicResult> {
    meterRef.current?.stop();
    stopMic(micStreamRef.current);
    micStreamRef.current = null;
    meterRef.current = null;
    setMeter(null);
    const { result, stream } = await openMic();
    if (result === 'granted' && stream) {
      micStreamRef.current = stream;
      meterRef.current = createMeter(stream);
      setMeter(meterRef.current);
    }
    return result;
  }

  async function retrySession() {
    primeAudioContext(); // inside the tap, before any await (Safari)
    driverRef.current?.stop();
    setState(initialSessionState);
    setQuestionsLit(0);
    setQuietDismissed(false);
    const result = await acquireMic();
    if (result !== 'granted') {
      setMicPhase(result);
      return;
    }
    startSession();
  }

  async function askForMic() {
    primeAudioContext(); // inside the tap, before the browser's own prompt (Safari)
    const result = await acquireMic();
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
      meterRef.current?.stop();
      stopMic(micStreamRef.current);
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
  // The child is expected to talk (and Kemi is not): the green lights follow the microphone
  // only then, so Kemi's own voice through the speaker never lights them.
  const listening =
    started && !state.reconnecting && failure === null && !speaking && LISTEN_STEPS.has(step ?? '');
  const watch = useMicWatch(meter, listening);
  const micQuiet = watch.quiet && !quietDismissed;
  const savedEarly = started && failure !== null && step !== null;
  const reading = step === 'READING' && state.passageVisible && state.passage !== null;
  // The count lights follow what the child counts, once Kemi has finished asking them to.
  const countActive = started && step === 'MIC_CHECK' && !state.reconnecting && !speaking;
  const counted = useCountedWords(meter, countActive);
  const countMeasured = meter !== null && meter.usable?.() !== false;
  // The session is being made ready behind the scenes: connecting, the story still on its
  // way, or the next clip still loading.
  const preparing =
    started &&
    !state.reconnecting &&
    failure === null &&
    (step === null ||
      waitingClip ||
      (step === 'MIC_CHECK' && state.playingClipId === 'story_almost_ready') ||
      (step === 'READING' && state.passage === null && !speaking));

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
      // The green lights: the agent heard the child, or this phone's microphone does.
      childSpeaking: state.childSpeaking || watch.heard,
      counting: mode === 'count' && !speaking,
      // Following the child's own count when the microphone is measured; else on a timer.
      countHeard: mode === 'count' && countMeasured ? counted : null,
      preparing,
      questionsLit: ending ? 3 : questionsLit,
      seeds: 0,
      // "That word is X." is Kemi speaking: her light pulses (speaking, above), and nothing else.
      // Jàpá (the turtle) does not come out for it.
      peek: false,
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
      watch.heard,
      counted,
      countMeasured,
      preparing,
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
  const quietCard = micQuiet && !blocked && !failedToStart;
  const grownUp =
    blocked || failedToStart || quietCard ? (
      <div className="l grownup" data-theme="dark">
        <div className="report" data-theme="light" role={failedToStart || quietCard ? 'alert' : undefined}>
          <h5>
            {failedToStart
              ? 'We could not start'
              : quietCard
                ? `We can’t hear ${childName} yet`
                : micPhase === 'denied'
                  ? 'The microphone is turned off'
                  : 'No microphone found'}
          </h5>
          {failedToStart ? (
            <p>{failure}</p>
          ) : quietCard ? (
            <p>
              The microphone sounds very quiet. Please check it is not muted or covered, that the
              phone is not on silent for calls, and that {childName} is close to it. Then tap Try again.
            </p>
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
              onClick={() => (failedToStart || quietCard ? void retrySession() : void askForMic())}
            >
              Try again
            </button>
            {quietCard ? (
              <button type="button" className="cta2" onClick={() => setQuietDismissed(true)}>
                Carry on anyway
              </button>
            ) : (
              <button type="button" className="cta2" onClick={() => navigate('/children')}>
                Back to your children
              </button>
            )}
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
      srText={
        started && !state.reconnecting
          ? preparing && !state.bubbleText
            ? 'Getting your reading check ready.'
            : state.bubbleText
          : null
      }
    />
  );
}
