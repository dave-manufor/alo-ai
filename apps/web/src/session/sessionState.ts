import type { AgentMessage, ClientMessage } from './protocol';

// What the session screen shows, decided only by agent messages (W2's
// protocol) and the phase the child is in. The web app never shows a
// score, timer, percentage or red mark, in any state.

export type SessionPhase =
  | 'welcome'
  | 'interests'
  | 'mic_check'
  | 'getting_story'
  | 'reading'
  | 'retell'
  | 'questions'
  | 'done';

export interface SessionViewState {
  phase: SessionPhase;
  passageVisible: boolean;
  passageId: string | null;
  reconnecting: boolean;
  clipsReady: boolean;
  toldWord: string | null;
  acksSent: ClientMessage[];
}

export const initialSessionState: SessionViewState = {
  phase: 'welcome',
  passageVisible: false,
  passageId: null,
  reconnecting: false,
  clipsReady: false,
  toldWord: null,
  acksSent: [],
};

export function applyAgentMessage(
  state: SessionViewState,
  message: AgentMessage,
): SessionViewState {
  switch (message.cmd) {
    case 'clip_list':
      return { ...state, clipsReady: true, reconnecting: false };
    case 'show_passage':
      return {
        ...state,
        phase: 'reading',
        passageVisible: true,
        passageId: message.passage_id,
        reconnecting: false,
      };
    case 'hide_passage':
      return { ...state, passageVisible: false };
    case 'reconnecting':
      return { ...state, reconnecting: true };
    case 'play':
      return state;
  }
}

export function recordAck(
  state: SessionViewState,
  ack: ClientMessage,
  toldWord: string | null = state.toldWord,
): SessionViewState {
  return { ...state, acksSent: [...state.acksSent, ack], toldWord };
}

/** The sample story used until the Passage Generator is connected. */
export const sampleStory = {
  passageId: 'bank_p3_market_day',
  title: 'The Market Day',
  sentences: [
    'Ada had a small brown goat.',
    'The goat loved to eat green leaves.',
    'One morning, Ada took a basket to the market.',
    'The goat ran quickly, and Ada chased it past the farm.',
    'Ada laughed and gave the goat some grass to eat.',
  ],
  questions: [
    'What did Ada take to the market?',
    'Why did Ada chase the goat?',
  ],
};

export const sampleClips = [
  { clip_id: 'greeting_1', url: '/clips/greeting_1.mp3' },
  { clip_id: 'word_market', url: '/clips/words/market.mp3' },
  { clip_id: 'question_1', url: '/clips/question_1.mp3' },
];
