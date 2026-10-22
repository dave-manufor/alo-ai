import type { AgentMessageSink, SessionDriver } from './driver';
import type { AgentMessage } from './protocol';

// The fixture driver stands in for the Session Agent in the sample build.
// It emits real protocol v2 messages in the agent's order; the screen only
// ever follows those messages (step, clip_list, play, show_passage,
// hide_passage). The screen has no buttons for the child to press (the
// design shows none): the real agent hears the child and moves on, so this
// driver paces itself with timers and moves on after a while, exactly as the
// agent would after it hears the child finish. `send('child_spoke')` moves
// it on at once (tests, and the live driver's contract). INTEREST_CHAT is
// off by default (INTEREST_CHAT=false: the session opens at the mic check);
// it remains a valid protocol step.
//
// Clip ids and texts copied from PR #24's
// services/session_agent/clips/prompts.py and catalog.py, so the fixture
// exercises the real ids (including question:0 / question:1) before LiveKit
// lands: the screen-reader text shows the playing clip's exact words; the
// listening story (not used here) would carry null.
const v2 = { schema_version: 2 as const };

export const fixtureClips = [
  {
    clip_id: 'interest_prompt',
    url: '/clips/interest_prompt.mp3',
    text: 'Before we read, tell me: what kind of stories do you like?',
  },
  {
    clip_id: 'mic_check_prompt',
    url: '/clips/mic_check_prompt.mp3',
    text: "Let's count together. Say one, two, three, four, five.",
  },
  {
    clip_id: 'story_almost_ready',
    url: '/clips/story_almost_ready.mp3',
    text: 'Your story is almost ready!',
  },
  {
    clip_id: 'word_market',
    url: '/clips/words/market.mp3',
    text: 'That word is market.',
  },
  {
    clip_id: 'retell_prompt',
    url: '/clips/retell_prompt.mp3',
    text: 'In your own words, tell me everything you remember from the story.',
  },
  {
    clip_id: 'question:0',
    url: '/clips/question_0.mp3',
    text: 'What did Ada choose at the market?',
  },
  {
    clip_id: 'question:1',
    url: '/clips/question_1.mp3',
    text: 'Why did Ada smile at the end?',
  },
  {
    clip_id: 'question:2',
    url: '/clips/question_2.mp3',
    text: 'Who went to the market with Ada?',
  },
  {
    clip_id: 'close_praise',
    url: '/clips/close_praise.mp3',
    text: 'You did a great job today!',
  },
];

/** The v2 fixture story (fixtures/contracts/session_protocol.json in #24). */
export const fixturePassage = {
  passage_id: 'bank_p3_market_day',
  title: 'Market Day',
  sentences: [
    'Ada and Mama went to the market.',
    'The market was full of people and bright colours.',
    'Ada saw a red hat.',
    'It cost too much.',
    'Mama said they could look at more hats.',
    'They walked past the fruit sellers and the cloth sellers.',
    'At the last stall there was a blue hat.',
    'It was soft, and the price was small.',
    'Ada tried it on and laughed out loud.',
    'Ada smiled and chose a blue hat.',
    'Mama paid, and they walked home together.',
    'On the way, a girl called out to them from a small shop.',
    'She sold sweet bread, and the smell was warm and good.',
    'Mama bought two pieces, one for Ada and one for her.',
    'Ada ate her bread and wore her new hat all the way home.',
  ],
  arl: 3,
};

export const QUESTION_COUNT = 3;

export type DriverEvent =
  | 'session_started'
  | 'call_over'
  | 'topic_chosen'
  | 'child_spoke'
  | 'reading_pause';

/** Messages the agent sends in reply to one driver event. */
export function messagesFor(
  event: DriverEvent,
  step: string | null,
  opening: 'MIC_CHECK' | 'INTEREST_CHAT' = 'MIC_CHECK',
): AgentMessage[] {
  switch (event) {
    case 'session_started':
      return [{ ...v2, cmd: 'clip_list', clips: fixtureClips }];
    case 'call_over':
      return opening === 'INTEREST_CHAT'
        ? [
            { ...v2, cmd: 'step', step: 'INTEREST_CHAT' },
            { ...v2, cmd: 'play', clip_id: 'interest_prompt' },
          ]
        : [
            { ...v2, cmd: 'step', step: 'MIC_CHECK' },
            { ...v2, cmd: 'play', clip_id: 'mic_check_prompt' },
          ];
    case 'topic_chosen':
      return [
        { ...v2, cmd: 'step', step: 'MIC_CHECK' },
        { ...v2, cmd: 'play', clip_id: 'mic_check_prompt' },
      ];
    case 'reading_pause':
      // The agent's told-word decision after a pause on a word (PRD 4.1).
      return [{ ...v2, cmd: 'play', clip_id: 'word_market' }];
    case 'child_spoke':
      switch (step) {
        case 'MIC_CHECK':
          return [
            { ...v2, cmd: 'play', clip_id: 'story_almost_ready' },
            { ...v2, cmd: 'step', step: 'READING' },
            { ...v2, cmd: 'show_passage', ...fixturePassage },
          ];
        case 'READING':
          return [
            { ...v2, cmd: 'hide_passage' },
            { ...v2, cmd: 'step', step: 'RETELL' },
            { ...v2, cmd: 'play', clip_id: 'retell_prompt' },
          ];
        case 'RETELL':
          return [
            { ...v2, cmd: 'step', step: 'QUESTIONS' },
            { ...v2, cmd: 'play', clip_id: 'question:0' },
          ];
        default:
          return [];
      }
    default:
      return [];
  }
}

/** After the last question answer, the agent closes the session. */
export function closingMessages(): AgentMessage[] {
  return [
    { ...v2, cmd: 'step', step: 'CLOSE' },
    { ...v2, cmd: 'play', clip_id: 'close_praise' },
  ];
}

/** How long the fixture waits before it "hears" the child finish each step (ms). */
export const PACE = {
  call: 2600,
  micCheck: 9000,
  toldWord: 7000,
  reading: 20000,
  retell: 7000,
  answer: 6000,
  close: 9000,
} as const;

export interface FixtureOptions {
  /** Move on by itself, as the agent does when it hears the child (default true). */
  autoAdvance?: boolean;
  /** Where the session opens after the call (default MIC_CHECK: INTEREST_CHAT=false). */
  opening?: 'MIC_CHECK' | 'INTEREST_CHAT';
}

/** The first SessionDriver: replays the fixture session in the agent's order. */
export function createFixtureDriver(options: FixtureOptions = {}): SessionDriver {
  const autoAdvance = options.autoAdvance ?? true;
  const opening = options.opening ?? 'MIC_CHECK';
  let sink: AgentMessageSink | null = null;
  let step: string | null = null;
  let answers = 0;
  let stopped = false;
  const timers = new Set<number>();
  let paceTimer: number | null = null;
  // Messages are delivered one at a time, in order, even across events.
  let queue: Promise<void> = Promise.resolve();

  function later(ms: number, fn: () => void) {
    const id = window.setTimeout(() => {
      timers.delete(id);
      if (!stopped) fn();
    }, ms);
    timers.add(id);
    return id;
  }

  function deliver(messages: AgentMessage[]) {
    for (const message of messages) {
      // The driver's own notion of the step moves when it decides, so a
      // quick second tap is answered for the right step.
      if (message.cmd === 'step') step = message.step;
      queue = queue.then(async () => {
        if (stopped || !sink) return;
        await sink(message);
      });
    }
  }

  function schedulePace() {
    if (!autoAdvance) return;
    if (paceTimer !== null) {
      window.clearTimeout(paceTimer);
      timers.delete(paceTimer);
      paceTimer = null;
    }
    const wait =
      step === 'MIC_CHECK'
        ? PACE.micCheck
        : step === 'READING'
          ? PACE.reading
          : step === 'RETELL'
            ? PACE.retell
            : step === 'QUESTIONS'
              ? PACE.answer
              : step === 'CLOSE'
                ? PACE.close
                : null;
    if (wait === null) return;
    paceTimer = later(wait, () => {
      paceTimer = null;
      if (step === 'CLOSE') {
        deliver([{ ...v2, cmd: 'step', step: 'ENDED' }]);
        step = 'ENDED';
      } else api.send('child_spoke');
    });
  }

  const api: SessionDriver = {
    start(next) {
      sink = next;
      stopped = false;
      deliver(messagesFor('session_started', null));
      later(PACE.call, () => {
        deliver(messagesFor('call_over', null, opening));
        schedulePace();
      });
    },
    send(event) {
      if (event === 'topic_chosen') {
        deliver(messagesFor('topic_chosen', step));
        schedulePace();
        return;
      }
      if (step === 'QUESTIONS') {
        answers += 1;
        if (answers >= QUESTION_COUNT) {
          deliver(closingMessages());
        } else {
          deliver([{ ...v2, cmd: 'play', clip_id: `question:${answers}` }]);
        }
        schedulePace();
        return;
      }
      const before = step;
      deliver(messagesFor('child_spoke', step));
      if (before === 'MIC_CHECK' && autoAdvance) {
        // During reading, the agent tells a word after a pause (PRD 4.1).
        later(PACE.toldWord, () => deliver(messagesFor('reading_pause', 'READING')));
      }
      schedulePace();
    },
    stop() {
      stopped = true;
      timers.forEach((id) => window.clearTimeout(id));
      timers.clear();
    },
  };
  return api;
}
