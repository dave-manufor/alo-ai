// The web app's side of W2's session protocol, schema_version 3 (2 is
// still accepted; schemas/session_protocol.schema.json, producer: Session
// Agent). Agent to web app: clip_list, play, step, show_passage,
// hide_passage, reconnecting, child_speaking. Web app to agent, only
// in reply to a play: played (the clip FINISHED playing), missing (not
// cached and could not be played). The agent decides every step; the
// client only follows these messages. Nothing may carry a score, timer
// or red mark, and show_passage carries display text only.

export interface ClipEntry {
  clip_id: string;
  url: string;
  /** Exactly what Auntie Kemi says, for the speech bubble. null for the
   *  listening story, which must stay audio-only. */
  text: string | null;
}

export type SessionStep =
  | 'INTEREST_CHAT'
  | 'MIC_CHECK'
  | 'READING'
  | 'RETELL'
  | 'QUESTIONS'
  | 'LISTENING'
  | 'CLOSE'
  | 'ENDED';

/** The agent sends 3 (3 adds child_speaking); 2 is still accepted so an older
 *  agent or a recorded session keeps working. */
export type ProtocolVersion = 2 | 3;
const CLIENT_VERSION: ProtocolVersion = 3;

export type AgentMessage =
  | { schema_version: ProtocolVersion; cmd: 'clip_list'; clips: ClipEntry[] }
  | { schema_version: ProtocolVersion; cmd: 'play'; clip_id: string }
  | { schema_version: ProtocolVersion; cmd: 'step'; step: SessionStep }
  | {
      schema_version: ProtocolVersion;
      cmd: 'show_passage';
      passage_id: string;
      title: string;
      sentences: string[];
      arl: number;
    }
  | { schema_version: ProtocolVersion; cmd: 'hide_passage' }
  | { schema_version: ProtocolVersion; cmd: 'reconnecting' }
  /** The child is heard speaking (true) or stopped (false): only for the
   *  stage's light. No words, no level. */
  | { schema_version: ProtocolVersion; cmd: 'child_speaking'; speaking: boolean };

export type ClientMessage =
  | {
      schema_version: ProtocolVersion;
      cmd: 'played' | 'missing';
      clip_id: string;
    }
  /** The story is on the child's screen (and its word clips are ready, or we stopped waiting
   *  for them): the agent starts the reading clock from here. */
  | { schema_version: ProtocolVersion; cmd: 'shown'; passage_id: string };

/** The reply to a `play`: the clip finished, or could not be played. */
export type ClipAckMessage = Extract<ClientMessage, { cmd: 'played' | 'missing' }>;

const AGENT_COMMANDS = [
  'clip_list',
  'play',
  'step',
  'show_passage',
  'hide_passage',
  'reconnecting',
  'child_speaking',
];
const STEPS: SessionStep[] = [
  'INTEREST_CHAT',
  'MIC_CHECK',
  'READING',
  'RETELL',
  'QUESTIONS',
  'LISTENING',
  'CLOSE',
  'ENDED',
];

/** Parse and validate one agent message; anything off-contract is dropped. */
export function parseAgentMessage(raw: unknown): AgentMessage | null {
  let message: unknown = raw;
  if (typeof raw === 'string') {
    try {
      message = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (typeof message !== 'object' || message === null) return null;
  const m = message as Record<string, unknown>;
  const version = m.schema_version;
  if ((version !== 2 && version !== 3) || typeof m.cmd !== 'string') return null;
  if (!AGENT_COMMANDS.includes(m.cmd)) return null;

  switch (m.cmd) {
    case 'clip_list': {
      if (!Array.isArray(m.clips)) return null;
      const valid = (clip: unknown): clip is ClipEntry =>
        typeof clip === 'object' &&
        clip !== null &&
        typeof (clip as ClipEntry).clip_id === 'string' &&
        (clip as ClipEntry).clip_id.length > 0 &&
        typeof (clip as ClipEntry).url === 'string' &&
        ((clip as ClipEntry).text === null || typeof (clip as ClipEntry).text === 'string');
      return m.clips.every(valid)
        ? { schema_version: version, cmd: 'clip_list', clips: m.clips as ClipEntry[] }
        : null;
    }
    case 'play':
      return typeof m.clip_id === 'string' && m.clip_id
        ? { schema_version: version, cmd: 'play', clip_id: m.clip_id }
        : null;
    case 'step':
      return typeof m.step === 'string' && STEPS.includes(m.step as SessionStep)
        ? { schema_version: version, cmd: 'step', step: m.step as SessionStep }
        : null;
    case 'show_passage':
      return typeof m.passage_id === 'string' &&
        m.passage_id &&
        typeof m.title === 'string' &&
        Array.isArray(m.sentences) &&
        m.sentences.length > 0 &&
        m.sentences.every((s) => typeof s === 'string' && s.length > 0) &&
        typeof m.arl === 'number' &&
        m.arl >= 1 &&
        m.arl <= 12
        ? {
            schema_version: version,
            cmd: 'show_passage',
            passage_id: m.passage_id,
            title: m.title,
            sentences: m.sentences as string[],
            arl: m.arl,
          }
        : null;
    case 'child_speaking':
      return typeof m.speaking === 'boolean'
        ? { schema_version: version, cmd: 'child_speaking', speaking: m.speaking }
        : null;
    default:
      return { schema_version: version, cmd: m.cmd as 'hide_passage' | 'reconnecting' };
  }
}

export function playedAck(clip_id: string): ClipAckMessage {
  return { schema_version: CLIENT_VERSION, cmd: 'played', clip_id };
}

export function missingAck(clip_id: string): ClipAckMessage {
  return { schema_version: CLIENT_VERSION, cmd: 'missing', clip_id };
}

export function shownAck(passage_id: string): ClientMessage {
  return { schema_version: CLIENT_VERSION, cmd: 'shown', passage_id };
}

/** The data-channel topic shared with the Session Agent (services/session_agent/livekit_worker.py). */
export const SESSION_TOPIC = 'aloai.session';

/** JSON bytes for a client message, as the agent expects on the data channel. */
export function encodeClientMessage(message: ClientMessage): Uint8Array<ArrayBuffer> {
  return new TextEncoder().encode(JSON.stringify(message));
}

/** Bytes from the data channel -> a validated agent message, or null if off-contract. */
export function decodeAgentData(payload: Uint8Array): AgentMessage | null {
  try {
    return parseAgentMessage(new TextDecoder().decode(payload));
  } catch {
    return null;
  }
}
