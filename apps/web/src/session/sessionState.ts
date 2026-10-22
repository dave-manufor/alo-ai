import type { AgentMessage, ClientMessage, SessionStep } from './protocol';

// What the session screen shows, decided only by agent messages
// (protocol v2). The client never advances the session itself: the step
// comes from the agent, the passage from show_passage, and the bubble
// text from the playing clip's `text`. Any later agent message clears
// the reconnecting state (after a reconnect the agent re-sends the step
// and a play). No score, timer, percentage or red mark, in any state.

export interface PassageOnScreen {
  passage_id: string;
  title: string;
  sentences: string[];
  arl: number;
}

export interface SessionViewState {
  step: SessionStep | null;
  passage: PassageOnScreen | null;
  passageVisible: boolean;
  reconnecting: boolean;
  /** The exact words of the clip now playing; null = keep last bubble,
   *  and for the listening story there must never be a bubble update. */
  bubbleText: string | null;
  playingClipId: string | null;
  /** The agent hears the child speaking (the stage's light only). */
  childSpeaking: boolean;
  acksSent: ClientMessage[];
}

export const initialSessionState: SessionViewState = {
  step: null,
  passage: null,
  passageVisible: false,
  reconnecting: false,
  bubbleText: null,
  playingClipId: null,
  childSpeaking: false,
  acksSent: [],
};

export function applyAgentMessage(
  state: SessionViewState,
  message: AgentMessage,
  clipText: (clip_id: string) => string | null = () => null,
): SessionViewState {
  // Any agent message after `reconnecting` means we are back.
  const reconnecting = message.cmd === 'reconnecting';
  switch (message.cmd) {
    case 'reconnecting':
      // A "stopped speaking" sent during the break may have been lost.
      return { ...state, reconnecting: true, childSpeaking: false };
    case 'child_speaking':
      return { ...state, reconnecting, childSpeaking: message.speaking };
    case 'clip_list':
      return { ...state, reconnecting };
    case 'step':
      return { ...state, reconnecting, step: message.step };
    case 'show_passage':
      return {
        ...state,
        reconnecting,
        passage: {
          passage_id: message.passage_id,
          title: message.title,
          sentences: message.sentences,
          arl: message.arl,
        },
        passageVisible: true,
      };
    case 'hide_passage':
      return { ...state, reconnecting, passageVisible: false };
    case 'play': {
      const text = clipText(message.clip_id);
      return {
        ...state,
        reconnecting,
        playingClipId: message.clip_id,
        // text null (listening story) leaves the bubble untouched.
        bubbleText: text ?? state.bubbleText,
      };
    }
  }
}

export function recordAck(state: SessionViewState, ack: ClientMessage): SessionViewState {
  return {
    ...state,
    playingClipId: state.playingClipId === ack.clip_id ? null : state.playingClipId,
    acksSent: [...state.acksSent, ack],
  };
}

/** ReadingPanel level from the passage's ARL (never shown to the child). */
export function readingLevelForArl(arl: number): 'p1' | 'p3' | 'p5' {
  if (arl <= 2) return 'p1';
  if (arl <= 6) return 'p3';
  return 'p5';
}

export const STEP_ORDER: SessionStep[] = [
  'INTEREST_CHAT',
  'MIC_CHECK',
  'READING',
  'RETELL',
  'QUESTIONS',
  'LISTENING',
  'CLOSE',
  'ENDED',
];
