import type { AgentMessageSink, SessionDriver } from './driver';
import {
  decodeAgentData,
  encodeClientMessage,
  SESSION_TOPIC,
  type ClientMessage,
} from './protocol';

// The LiveKit session driver (D3). It carries protocol v2 over the
// `aloai.session` data topic and publishes the child's microphone; the
// screen itself is unchanged. The agent decides every step, so a child's
// taps (topic, "I spoke") are NOT sent: the agent hears the child. The
// only thing the web app sends is the clip ack (`played` / `missing`) in
// reply to a `play`.
//
// CONTRACT (C4, `POST /v1/sessions`, schemas/session_start.schema.json):
// the request is {"child_id": "..."} and the reply is
// {"session_id": "...", "livekit_url": "wss://...", "token": "..."}.
// The caller passes `startSession`, so only that one function changes if
// the contract does. Nothing here holds a secret: the token is a
// short-lived room token for this child's session.

export interface SessionJoin {
  session_id: string;
  livekit_url: string;
  token: string;
}

export type RoomEvent = 'reconnecting' | 'reconnected' | 'disconnected';

/** The few things the driver needs from a room (so tests need no WebRTC). */
export interface LiveRoom {
  onData(listener: (payload: Uint8Array, topic: string | undefined) => void): void;
  onConnection(listener: (event: RoomEvent) => void): void;
  publishData(payload: Uint8Array<ArrayBuffer>, topic: string): Promise<void>;
  /** Publish the microphone: the given live track if there is one, else a fresh capture. */
  enableMicrophone(track?: MediaStreamTrack): Promise<void>;
  disconnect(): void;
}

export type OpenRoom = (url: string, token: string) => Promise<LiveRoom>;

/** The real room, from livekit-client (loaded only when a live session starts). */
export const openLiveKitRoom: OpenRoom = async (url, token) => {
  const { Room, RoomEvent: Events, Track } = await import('livekit-client');
  const room = new Room({ adaptiveStream: false, dynacast: false });
  await room.connect(url, token);
  return {
    onData: (listener) => {
      room.on(Events.DataReceived, (payload, _participant, _kind, topic) =>
        listener(payload, topic),
      );
    },
    onConnection: (listener) => {
      room.on(Events.Reconnecting, () => listener('reconnecting'));
      room.on(Events.Reconnected, () => listener('reconnected'));
      room.on(Events.Disconnected, () => listener('disconnected'));
    },
    publishData: (payload, topic) =>
      room.localParticipant.publishData(payload, { reliable: true, topic }),
    enableMicrophone: async (track) => {
      // The track the app already opened (and the level meter listens to). A room that
      // disconnects stops the tracks it published, so after a rejoin the track may be dead:
      // then ask the browser again.
      if (track && track.readyState === 'live') {
        await room.localParticipant.publishTrack(track, { source: Track.Source.Microphone });
        return;
      }
      await room.localParticipant.setMicrophoneEnabled(true);
    },
    disconnect: () => void room.disconnect(),
  };
};

const START_FAILED = 'We could not start the reading check. Please check the internet and try again.';
const LOST = 'The connection was lost and could not come back. Please try again.';

export function createLiveDriver(options: {
  startSession: () => Promise<SessionJoin>;
  openRoom?: OpenRoom;
  /** How many times to rejoin after the room is lost for good. */
  maxRejoins?: number;
  /** Wait before a rejoin; tests set 0. */
  rejoinDelayMs?: number;
  /** The microphone stream the app already opened; its track is what gets published. */
  micStream?: MediaStream;
}): SessionDriver {
  const openRoom = options.openRoom ?? openLiveKitRoom;
  const maxRejoins = options.maxRejoins ?? 2;
  const rejoinDelayMs = options.rejoinDelayMs ?? 1500;

  let sink: AgentMessageSink | null = null;
  let room: LiveRoom | null = null;
  let stopped = false;
  let joined: SessionJoin | null = null;
  let ended = false;
  let rejoins = 0;
  let failed: ((plain: string) => void) | null = null;
  // Agent messages are handed to the screen one at a time, in order, so
  // the screen can finish downloading a clip_list before the next message.
  let queue: Promise<void> = Promise.resolve();

  function deliver(message: Parameters<AgentMessageSink>[0]) {
    queue = queue.then(async () => {
      if (!stopped && sink) await sink(message);
    });
  }

  function fail(plain: string) {
    if (stopped) return;
    failed?.(plain);
  }

  async function join() {
    try {
      // A rejoin goes back into the SAME session and room with the same token (it lasts an
      // hour); asking again would make a new session and leave the agent waiting in the old one.
      joined ??= await options.startSession();
      room = await openRoom(joined.livekit_url, joined.token);
    } catch {
      fail(START_FAILED);
      return;
    }
    if (stopped) {
      room.disconnect();
      return;
    }
    room.onData((payload, topic) => {
      if (topic !== SESSION_TOPIC) return;
      const message = decodeAgentData(payload);
      if (message?.cmd === 'step' && (message.step === 'CLOSE' || message.step === 'ENDED')) {
        ended = true;
      }
      if (message) deliver(message);
    });
    room.onConnection((event) => {
      if (event === 'reconnecting') deliver({ schema_version: 2, cmd: 'reconnecting' });
      // After 'reconnected' the agent re-sends the step and a play, which clears the overlay.
      // Once the agent has ended the session the room closing is expected: do not go back in.
      if (event === 'disconnected' && !stopped && !ended) void rejoin();
    });
    try {
      await room.enableMicrophone(options.micStream?.getAudioTracks()[0]);
    } catch {
      fail('The microphone could not be used. Please check it is allowed and try again.');
    }
  }

  async function rejoin() {
    if (rejoins >= maxRejoins) {
      fail(LOST);
      return;
    }
    rejoins += 1;
    deliver({ schema_version: 2, cmd: 'reconnecting' });
    await new Promise((resolve) => setTimeout(resolve, rejoinDelayMs));
    if (!stopped) await join();
  }

  return {
    start(next) {
      sink = next;
      stopped = false;
      void join();
    },
    // The agent hears the child; taps are not protocol messages.
    send() {},
    ack(message: ClientMessage) {
      if (!room || stopped) return;
      void room.publishData(encodeClientMessage(message), SESSION_TOPIC).catch(() => {
        // A lost ack is recovered by the agent (it re-sends the play after a reconnect).
      });
    },
    onFailed(listener) {
      failed = listener;
    },
    sessionId: () => joined?.session_id ?? null,
    stop() {
      stopped = true;
      room?.disconnect();
      room = null;
    },
  };
}
