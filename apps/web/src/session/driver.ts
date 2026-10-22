import type { AgentMessage } from './protocol';

// What the session screen needs from whatever carries the session: the
// fixture driver today, the LiveKit driver (D3) when the backend is
// live. The screen follows the agent's protocol v2 messages only; the
// driver is the only thing that knows where they come from. A child's
// tap is reported as an event ("the child spoke"), never as a step: the
// agent decides what happens next.

/** What the child did on the screen. */
export type ChildEvent = 'topic_chosen' | 'child_spoke';

/** Receives one agent message; resolves when the screen has handled it. */
export type AgentMessageSink = (message: AgentMessage) => Promise<void> | void;

export interface SessionDriver {
  /** Begin the session; every agent message is delivered to `sink` in order. */
  start(sink: AgentMessageSink): void;
  /** Report something the child did. */
  send(event: ChildEvent): void;
  /** Stop timers and connections (screen left or unmounted). */
  stop(): void;
}
