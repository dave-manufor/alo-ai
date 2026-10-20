import { useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Button,
  Japa,
  MicButton,
  MoonProgress,
  ReadingPanel,
  RewardBadge,
  SpeechBubble,
} from '../design-system/alo';
import { createClipCache } from '../session/clipCache';
import { parseAgentMessage, type ClientMessage } from '../session/protocol';
import {
  applyAgentMessage,
  initialSessionState,
  recordAck,
  sampleClips,
  sampleStory,
  type SessionPhase,
} from '../session/sessionState';

const PHASE_STEP: Record<SessionPhase, number> = {
  welcome: 0,
  interests: 0,
  mic_check: 0,
  getting_story: 1,
  reading: 1,
  retell: 2,
  questions: 3,
  done: 3,
};

const TOPICS = ['Animals', 'Football', 'Space', 'Food'];

// Kid mode session screen (PRD 4.1, 4.4), fixture-driven in the MVP
// phase: it follows W2's session protocol exactly (clip_list downloads
// every clip before reading, play answers played/missing, the passage is
// shown and hidden only on the agent's word, reconnecting is an agent
// command). The fixture driver below stands in for the LiveKit data
// channel; LiveKit replaces it without changing this screen's states.
// Children never see a score, timer, percentage or red mark.
export default function SessionPage() {
  const [state, setState] = useState(initialSessionState);
  const [questionIndex, setQuestionIndex] = useState(0);
  const acksRef = useRef<ClientMessage[]>([]);

  // Fixture clips are simulated locally; with the LiveKit driver the same
  // cache loads each clip URL in full before reading starts (clipCache.ts).
  const clipCache = useMemo(
    () =>
      createClipCache({
        load: async () => true,
        playClip: () => undefined,
      }),
    [],
  );

  function dispatch(raw: unknown, toldWord: string | null = null) {
    const message = parseAgentMessage(raw);
    if (!message) return;
    if (message.cmd === 'play') {
      const ack = clipCache.play(message.clip_id);
      acksRef.current.push(ack);
      setState((current) => recordAck(current, ack, toldWord));
      return;
    }
    setState((current) => applyAgentMessage(current, message));
  }

  async function startStory() {
    setState((current) => ({ ...current, phase: 'getting_story' }));
    const missing = await clipCache.downloadAll(sampleClips);
    for (const clip_id of missing) {
      acksRef.current.push({ schema_version: 1, cmd: 'missing', clip_id });
    }
    dispatch({ schema_version: 1, cmd: 'clip_list', clips: sampleClips });
    dispatch({ schema_version: 1, cmd: 'show_passage', passage_id: sampleStory.passageId });
  }

  return (
    <main className="app-main">
      <MoonProgress
        steps={['Say hello', 'Read', 'Tell', 'Answer']}
        current={PHASE_STEP[state.phase]}
      />

      {state.reconnecting ? (
        <SpeechBubble>Hold on, I&apos;m still listening.</SpeechBubble>
      ) : null}

      {state.phase === 'welcome' ? (
        <section className="stack">
          <SpeechBubble tone="call">Àlọ́ o!</SpeechBubble>
          <Japa pose="happy" />
          <Button
            variant="call"
            size="kid"
            onClick={() => setState((s) => ({ ...s, phase: 'interests' }))}
          >
            Ààlọ̀!
          </Button>
        </section>
      ) : null}

      {state.phase === 'interests' ? (
        <section className="stack">
          <SpeechBubble>What kind of stories do you like?</SpeechBubble>
          <Japa pose="listening" />
          <div className="row">
            {TOPICS.map((topic) => (
              <Button
                key={topic}
                variant="secondary"
                size="kid"
                onClick={() => setState((s) => ({ ...s, phase: 'mic_check' }))}
              >
                {topic}
              </Button>
            ))}
          </div>
        </section>
      ) : null}

      {state.phase === 'mic_check' ? (
        <section className="stack">
          <SpeechBubble>Count with me: one, two, three, four, five.</SpeechBubble>
          <MicButton state="listening" />
          <Button variant="primary" size="kid" icon="check" onClick={startStory}>
            I counted
          </Button>
        </section>
      ) : null}

      {state.phase === 'getting_story' ? (
        <section className="stack">
          <SpeechBubble>Your story is almost ready!</SpeechBubble>
          <Japa pose="thinking" />
        </section>
      ) : null}

      {state.phase === 'reading' && state.passageVisible ? (
        <section className="stack">
          <ReadingPanel title={sampleStory.title} level="p3" text={sampleStory.sentences} />
          {state.toldWord ? (
            <SpeechBubble>That word is {state.toldWord}. Keep going!</SpeechBubble>
          ) : (
            <SpeechBubble>Read the story aloud for me.</SpeechBubble>
          )}
          <MicButton state="listening" />
          <div className="row">
            <Button
              variant="call"
              size="kid"
              icon="replay"
              onClick={() =>
                dispatch({ schema_version: 1, cmd: 'play', clip_id: 'word_market' }, 'market')
              }
            >
              Help with a word
            </Button>
            <Button
              variant="primary"
              size="kid"
              icon="check"
              onClick={() => {
                dispatch({ schema_version: 1, cmd: 'hide_passage' });
                setState((s) => ({ ...s, phase: 'retell' }));
              }}
            >
              I have finished
            </Button>
          </div>
        </section>
      ) : null}

      {state.phase === 'retell' ? (
        <section className="stack">
          <SpeechBubble>Tell me the story in your own words.</SpeechBubble>
          <Japa pose="listening" />
          <MicButton state="listening" />
          <Button
            variant="primary"
            size="kid"
            icon="check"
            onClick={() => setState((s) => ({ ...s, phase: 'questions' }))}
          >
            I have finished
          </Button>
        </section>
      ) : null}

      {state.phase === 'questions' ? (
        <section className="stack">
          <SpeechBubble>{sampleStory.questions[questionIndex]}</SpeechBubble>
          <MicButton state="listening" />
          {questionIndex + 1 < sampleStory.questions.length ? (
            <Button
              variant="primary"
              size="kid"
              icon="check"
              onClick={() => setQuestionIndex((i) => i + 1)}
            >
              Next question
            </Button>
          ) : (
            <Button
              variant="primary"
              size="kid"
              icon="star"
              onClick={() => setState((s) => ({ ...s, phase: 'done' }))}
            >
              Finish
            </Button>
          )}
        </section>
      ) : null}

      {state.phase === 'done' ? (
        <section className="stack">
          <SpeechBubble>You did a great job today!</SpeechBubble>
          <Japa pose="cheer" />
          <RewardBadge kind="teller" earned />
          <Link to="/reports">
            <Button variant="reward" size="kid" icon="star">
              Collect stars
            </Button>
          </Link>
        </section>
      ) : null}
    </main>
  );
}
