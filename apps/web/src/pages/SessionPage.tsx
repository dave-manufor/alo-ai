import { useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { accountStore } from '../account/store';
import {
  Button,
  Japa,
  LanternStreak,
  MicButton,
  MoonProgress,
  ReadingPanel,
  RewardBadge,
  SpeechBubble,
} from '../design-system/alo';
import { createClipCache, unlockAudio } from '../session/clipCache';
import {
  closingMessages,
  messagesFor,
  type DriverEvent,
} from '../session/fixtureDriver';
import type { AgentMessage } from '../session/protocol';
import {
  applyAgentMessage,
  initialSessionState,
  readingLevelForArl,
  recordAck,
} from '../session/sessionState';

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

// Kid mode session screen (PRD 4.1, 4.4). The gate comes first: no
// signed-in guardian + no per-child consent record, no session (PRD 12).
// The screen follows the agent's protocol v2 messages only — step, clip
// texts for the bubble, the story from show_passage — and never moves
// the session on itself. In this phase a fixture driver emits those
// messages; the LiveKit driver in #24's protocol replaces it. The told
// word is the agent's decision during reading, never a child's button.
// Children never see a score, timer, percentage or red mark.
export default function SessionPage() {
  const { childId } = useParams();
  const [started, setStarted] = useState(false);
  const [state, setState] = useState(initialSessionState);
  const [starsCollected, setStarsCollected] = useState(false);
  const answersRef = useRef(0);
  const toldWordTimer = useRef<number | null>(null);

  const clipCache = useMemo(
    () =>
      createClipCache({
        // Fixture clips are simulated locally; the live cache stores the
        // bytes in Cache Storage (clipCache.loadClipIntoCache).
        load: async (url) => `fixture:${url}`,
        player: { play: async () => undefined },
      }),
    [],
  );

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
    }
  }

  async function dispatchAll(messages: AgentMessage[]) {
    for (const message of messages) await dispatch(message);
  }

  function driverEvent(event: DriverEvent) {
    if (event === 'child_spoke' && state.step === 'QUESTIONS') {
      answersRef.current += 1;
      if (answersRef.current >= 2) {
        void dispatchAll(closingMessages());
        return;
      }
    }
    void dispatchAll(messagesFor(event, state.step));
    if (event === 'child_spoke' && state.step === 'MIC_CHECK') {
      // During reading, the agent tells a word after a pause (PRD 4.1).
      toldWordTimer.current = window.setTimeout(() => {
        void dispatchAll(messagesFor('reading_pause', 'READING'));
      }, 900);
    }
  }

  useEffect(
    () => () => {
      if (toldWordTimer.current !== null) window.clearTimeout(toldWordTimer.current);
    },
    [],
  );

  // The mic gate (PRD 12): this child's consent record must exist.
  if (!childId || !accountStore.canStartSession(childId)) {
    return <Navigate to="/children" replace />;
  }

  const step = state.step;
  const listening =
    state.playingClipId === null &&
    (step === 'INTEREST_CHAT' ||
      step === 'MIC_CHECK' ||
      step === 'READING' ||
      step === 'RETELL' ||
      step === 'QUESTIONS' ||
      step === 'LISTENING');

  return (
    <main className="app-main">
      <MoonProgress
        steps={['Say hello', 'Read', 'Tell', 'Answer']}
        current={step ? STEP_INDEX[step] : 0}
      />

      {!started ? (
        <section className="stack">
          <SpeechBubble tone="call">Àlọ́ o!</SpeechBubble>
          <Japa pose="happy" />
          <Button
            variant="call"
            size="kid"
            icon="star"
            onClick={() => {
              unlockAudio();
              setStarted(true);
              driverEvent('session_started');
            }}
          >
            Ààlọ̀!
          </Button>
        </section>
      ) : null}

      {started && state.reconnecting ? (
        <section className="stack">
          <SpeechBubble>{state.bubbleText ?? 'Let’s wait for the internet.'}</SpeechBubble>
          <Japa pose="thinking" />
        </section>
      ) : null}

      {started && !state.reconnecting && step === 'INTEREST_CHAT' ? (
        <section className="stack">
          {state.bubbleText ? <SpeechBubble>{state.bubbleText}</SpeechBubble> : null}
          <Japa pose="listening" />
          <div className="row">
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
        <section className="stack">
          {state.bubbleText ? <SpeechBubble>{state.bubbleText}</SpeechBubble> : null}
          <MicButton state={listening ? 'listening' : 'idle'} onClick={() => driverEvent('child_spoke')} />
        </section>
      ) : null}

      {started && !state.reconnecting && step === 'READING' && state.passageVisible && state.passage ? (
        <section className="stack">
          <ReadingPanel
            title={state.passage.title}
            level={readingLevelForArl(state.passage.arl)}
            text={state.passage.sentences}
          />
          {state.bubbleText ? <SpeechBubble>{state.bubbleText}</SpeechBubble> : null}
          <MicButton state={listening ? 'listening' : 'idle'} onClick={() => driverEvent('child_spoke')} />
        </section>
      ) : null}

      {started && !state.reconnecting && step === 'RETELL' ? (
        <section className="stack">
          {state.bubbleText ? <SpeechBubble>{state.bubbleText}</SpeechBubble> : null}
          <Japa pose="listening" />
          <MicButton state={listening ? 'listening' : 'idle'} onClick={() => driverEvent('child_spoke')} />
        </section>
      ) : null}

      {started && !state.reconnecting && step === 'QUESTIONS' ? (
        <section className="stack">
          {state.bubbleText ? <SpeechBubble>{state.bubbleText}</SpeechBubble> : null}
          <MicButton state={listening ? 'listening' : 'idle'} onClick={() => driverEvent('child_spoke')} />
        </section>
      ) : null}

      {started && !state.reconnecting && step === 'CLOSE' ? (
        <section className="stack">
          {state.bubbleText ? <SpeechBubble>{state.bubbleText}</SpeechBubble> : null}
          <Japa pose="cheer" />
          <RewardBadge kind="teller" earned />
          {starsCollected ? <LanternStreak weeks={[true]} /> : null}
          <Button
            variant="reward"
            size="kid"
            icon="star"
            onClick={() => setStarsCollected(true)}
          >
            Collect stars
          </Button>
          <p className="kid-body">Give the phone back to a grown-up now.</p>
        </section>
      ) : null}

    </main>
  );
}
