import type { AgentMessage, ClientMessage } from './protocol';

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
  /** Send the clip ack (`played` / `missing`) the screen produced. Live drivers only. */
  ack?(message: ClientMessage): void;
  /** Register a listener for a session that cannot start or cannot continue.
   *  `plain` is a sentence for a grown-up. Live drivers only. */
  onFailed?(listener: (plain: string) => void): void;
  /** The id of the session this driver started, once it has one. Live drivers only. */
  sessionId?(): string | null;
}
