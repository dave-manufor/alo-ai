// The web app's side of W2's session protocol (schemas/session_protocol
// .schema.json, producer: Session Agent). Agent to web app: clip_list,
// play, show_passage, hide_passage, reconnecting. Web app to agent:
// played, missing. Nothing here may carry a score, timer or red mark.

export type AgentMessage =
  | { schema_version: 1; cmd: 'clip_list'; clips: { clip_id: string; url: string }[] }
  | { schema_version: 1; cmd: 'play'; clip_id: string }
  | { schema_version: 1; cmd: 'show_passage'; passage_id: string }
  | { schema_version: 1; cmd: 'hide_passage' }
  | { schema_version: 1; cmd: 'reconnecting' };

export type ClientMessage = {
  schema_version: 1;
  cmd: 'played' | 'missing';
  clip_id: string;
};

const AGENT_COMMANDS = ['clip_list', 'play', 'show_passage', 'hide_passage', 'reconnecting'];

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
  if (m.schema_version !== 1 || typeof m.cmd !== 'string') return null;
  if (!AGENT_COMMANDS.includes(m.cmd)) return null;

  switch (m.cmd) {
    case 'clip_list': {
      if (!Array.isArray(m.clips)) return null;
      const clips = m.clips.filter(
        (clip): clip is { clip_id: string; url: string } =>
          typeof clip === 'object' &&
          clip !== null &&
          typeof (clip as { clip_id?: unknown }).clip_id === 'string' &&
          typeof (clip as { url?: unknown }).url === 'string',
      );
      return clips.length === m.clips.length
        ? { schema_version: 1, cmd: 'clip_list', clips }
        : null;
    }
    case 'play':
      return typeof m.clip_id === 'string' && m.clip_id
        ? { schema_version: 1, cmd: 'play', clip_id: m.clip_id }
        : null;
    case 'show_passage':
      return typeof m.passage_id === 'string' && m.passage_id
        ? { schema_version: 1, cmd: 'show_passage', passage_id: m.passage_id }
        : null;
    default:
      return { schema_version: 1, cmd: m.cmd as 'hide_passage' | 'reconnecting' };
  }
}

export function playedAck(clip_id: string): ClientMessage {
  return { schema_version: 1, cmd: 'played', clip_id };
}

export function missingAck(clip_id: string): ClientMessage {
  return { schema_version: 1, cmd: 'missing', clip_id };
}
