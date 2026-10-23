import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { accountStore } from '../account/store';
import SessionPage from '../pages/SessionPage';

import type { SessionDriver } from './driver';
import { createClipCache } from './clipCache';
import {
  createLiveDriver,
  type LiveRoom,
  type RoomEvent,
  type SessionJoin,
} from './liveDriver';
import { decodeAgentData, encodeClientMessage, playedAck, SESSION_TOPIC } from './protocol';
import type { AgentMessage } from './protocol';

vi.mock('../api', () => ({ dataMode: 'live', liveApi: () => ({}) }));

// Written to work with or without the mic explainer screen (B7) in front of Start.
function stubMic() {
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: {
      getUserMedia: async () => ({ getTracks: () => [{ stop: () => undefined }] }),
    },
  });
}

function startSessionScreen() {
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  const ready = screen.queryByRole('button', { name: /ready/i });
  if (ready) fireEvent.click(ready);
}

const join: SessionJoin = { session_id: 's1', livekit_url: 'wss://lk.example.test', token: 't' };

function fakeRoom() {
  let data: (payload: Uint8Array, topic: string | undefined) => void = () => undefined;
  let conn: (event: RoomEvent) => void = () => undefined;
  const room: LiveRoom & { sent: { payload: Uint8Array; topic: string }[]; closed: boolean } = {
    sent: [],
    closed: false,
    onData: (l) => void (data = l),
    onConnection: (l) => void (conn = l),
    publishData: async (payload, topic) => void room.sent.push({ payload, topic }),
    enableMicrophone: vi.fn(async () => undefined),
    disconnect: () => void (room.closed = true),
  };
  return {
    room,
    push: (message: unknown, topic: string | undefined = SESSION_TOPIC) =>
      data(new TextEncoder().encode(JSON.stringify(message)), topic),
    event: (e: RoomEvent) => conn(e),
  };
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const v2 = { schema_version: 2 as const };
const v3 = { schema_version: 3 as const };

describe('LiveKit driver (D3), against the documented protocol v2 with a fake room', () => {
  it('joins with the session token, publishes the mic, and delivers agent messages in order', async () => {
    const fake = fakeRoom();
    const openRoom = vi.fn(async () => fake.room);
    const seen: AgentMessage[] = [];
    const driver = createLiveDriver({ startSession: async () => join, openRoom });
    driver.start((m) => void seen.push(m));
    await tick();
    expect(openRoom).toHaveBeenCalledWith('wss://lk.example.test', 't');
    expect(fake.room.enableMicrophone).toHaveBeenCalled();

    fake.push({ ...v2, cmd: 'step', step: 'INTEREST_CHAT' });
    fake.push({ ...v2, cmd: 'play', clip_id: 'interest_prompt' });
    await tick();
    expect(seen.map((m) => m.cmd)).toEqual(['step', 'play']);
  });

  it('drops other topics and off-contract messages', async () => {
    const fake = fakeRoom();
    const seen: AgentMessage[] = [];
    const driver = createLiveDriver({ startSession: async () => join, openRoom: async () => fake.room });
    driver.start((m) => void seen.push(m));
    await tick();
    fake.push({ ...v2, cmd: 'step', step: 'READING' }, 'other.topic');
    fake.push({ schema_version: 1, cmd: 'step', step: 'READING' });
    fake.push({ ...v2, cmd: 'step', step: 'NOT_A_STEP' });
    await tick();
    expect(seen).toEqual([]);
  });

  it('sends played and missing acks on the aloai.session topic, and not child taps', async () => {
    const fake = fakeRoom();
    const driver = createLiveDriver({ startSession: async () => join, openRoom: async () => fake.room });
    driver.start(() => undefined);
    await tick();
    driver.send('child_spoke'); // not a protocol message
    driver.ack?.(playedAck('interest_prompt'));
    driver.ack?.({ ...v2, cmd: 'missing', clip_id: 'word_market' });
    await tick();
    expect(fake.room.sent.map((s) => s.topic)).toEqual([SESSION_TOPIC, SESSION_TOPIC]);
    expect(JSON.parse(new TextDecoder().decode(fake.room.sent[0].payload))).toEqual({
      ...v3,
      cmd: 'played',
      clip_id: 'interest_prompt',
    });
    expect(decodeAgentData(encodeClientMessage(playedAck('x')))).toBeNull(); // acks are not agent messages
  });

  it('passes the agent’s child_speaking on to the screen', async () => {
    const fake = fakeRoom();
    const seen: AgentMessage[] = [];
    const driver = createLiveDriver({ startSession: async () => join, openRoom: async () => fake.room });
    driver.start((m) => void seen.push(m));
    await tick();
    fake.push({ ...v3, cmd: 'child_speaking', speaking: true });
    fake.push({ ...v3, cmd: 'child_speaking', speaking: false });
    await tick();
    expect(seen.map((m) => (m.cmd === 'child_speaking' ? m.speaking : null))).toEqual([true, false]);
  });

  it('shows reconnecting on a dropped connection, then follows the agent’s resend', async () => {
    const fake = fakeRoom();
    const seen: AgentMessage[] = [];
    const driver = createLiveDriver({ startSession: async () => join, openRoom: async () => fake.room });
    driver.start((m) => void seen.push(m));
    await tick();
    fake.event('reconnecting');
    fake.event('reconnected');
    fake.push({ ...v2, cmd: 'step', step: 'READING' });
    await tick();
    expect(seen.map((m) => m.cmd)).toEqual(['reconnecting', 'step']);
  });

  it('rejoins the SAME session when the room is lost, then gives up with a plain message', async () => {
    const rooms = [fakeRoom(), fakeRoom(), fakeRoom()];
    let n = 0;
    const startSession = vi.fn(async () => join);
    const failures: string[] = [];
    const driver = createLiveDriver({
      startSession,
      openRoom: async () => rooms[n++].room,
      maxRejoins: 2,
      rejoinDelayMs: 0,
    });
    driver.onFailed?.((plain) => failures.push(plain));
    driver.start(() => undefined);
    await tick();
    rooms[0].event('disconnected');
    await tick();
    await tick();
    // Back into the room already made: asking for a session again would leave the agent
    // waiting in the first room and give the child a second, empty one.
    expect(startSession).toHaveBeenCalledTimes(1);
    expect(n).toBe(2);
    rooms[1].event('disconnected');
    await tick();
    await tick();
    rooms[2].event('disconnected');
    await tick();
    await tick();
    expect(failures).toEqual(['The connection was lost and could not come back. Please try again.']);
  });

  it('does not go back in once the agent has ended the session, and knows the session id', async () => {
    const fake = fakeRoom();
    const openRoom = vi.fn(async () => fake.room);
    const failures: string[] = [];
    const driver = createLiveDriver({
      startSession: async () => join,
      openRoom,
      rejoinDelayMs: 0,
    });
    driver.onFailed?.((plain) => failures.push(plain));
    expect(driver.sessionId?.()).toBeNull();
    driver.start(() => undefined);
    await tick();
    expect(driver.sessionId?.()).toBe('s1');
    fake.push({ ...v3, cmd: 'step', step: 'ENDED' });
    await tick();
    fake.event('disconnected');
    await tick();
    await tick();
    expect(openRoom).toHaveBeenCalledTimes(1);
    expect(failures).toEqual([]);
  });

  it('reports a plain failure when the session cannot start, and when stopped does nothing', async () => {
    const failures: string[] = [];
    const driver = createLiveDriver({
      startSession: async () => {
        throw new Error('503');
      },
    });
    driver.onFailed?.((plain) => failures.push(plain));
    driver.start(() => undefined);
    await tick();
    expect(failures[0]).toMatch(/could not start the reading check/);

    const fake = fakeRoom();
    const stopped = createLiveDriver({ startSession: async () => join, openRoom: async () => fake.room });
    stopped.start(() => undefined);
    await tick();
    stopped.stop();
    expect(fake.room.closed).toBe(true);
    stopped.ack?.(playedAck('x'));
    expect(fake.room.sent).toEqual([]);
  });
});

describe('clip cache from the live clip_list (D4)', () => {
  const clips = [
    { clip_id: 'a', url: '/a.mp3', text: 'Hello.' },
    { clip_id: 'b', url: '/b.mp3', text: 'Bye.' },
  ];

  it('downloads every clip before resolving, and answers missing for one that failed', async () => {
    const loaded: string[] = [];
    const cache = createClipCache({
      load: async (url) => {
        if (url === '/b.mp3') throw new Error('offline');
        loaded.push(url);
        return `blob:${url}`;
      },
      player: { play: async () => undefined },
    });
    await cache.downloadAll(clips);
    expect(loaded).toEqual(['/a.mp3']);
    expect(await cache.play('a')).toMatchObject({ cmd: 'played', clip_id: 'a' });
    expect(await cache.play('b')).toMatchObject({ cmd: 'missing', clip_id: 'b' });
    expect(await cache.play('never_listed')).toMatchObject({ cmd: 'missing' });
  });

  it('retries a failed download once before giving up', async () => {
    let tries = 0;
    const cache = createClipCache({
      load: async () => {
        tries += 1;
        if (tries === 1) throw new Error('blip');
        return 'blob:x';
      },
      player: { play: async () => undefined },
    });
    await cache.downloadAll([clips[0]]);
    expect(await cache.play('a')).toMatchObject({ cmd: 'played' });
  });
});

describe('live session screen', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
    stubMic();
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
  });

  function renderLive(createDriver?: () => SessionDriver) {
    accountStore.signIn('google');
    const { child } = accountStore.addChildWithConsent({
      firstName: 'Adaeze',
      primaryClass: 3,
      birthYear: 2017,
      attested: true,
      trainingOptIn: false,
    });
    return render(
      <MemoryRouter initialEntries={[`/session/${child.child_id}`]}>
        <Routes>
          <Route path="/session/:childId" element={<SessionPage createDriver={createDriver} />} />
          <Route path="/children" element={<p>children page</p>} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it('refuses to start offline, cleanly, without creating a session', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false });
    const create = vi.fn();
    renderLive(create);
    startSessionScreen();
    expect(await screen.findByText('We could not start')).toBeInTheDocument();
    expect(screen.getByText(/needs the internet to start/)).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it('shows the driver’s plain failure to a grown-up, and Try again starts a new driver', async () => {
    let listener: (plain: string) => void = () => undefined;
    const create = vi.fn(
      (): SessionDriver => ({
        start: () => undefined,
        send: () => undefined,
        stop: () => undefined,
        onFailed: (l) => void (listener = l),
      }),
    );
    renderLive(create);
    startSessionScreen();
    await screen.findByRole('status'); // session screen is up
    listener('We could not start the reading check. Please check the internet and try again.');
    expect(await screen.findByText(/Please check the internet and try again/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    // Try again opens the microphone afresh (stopping a driver ends the track it published),
    // so the new driver comes a moment later.
    await waitFor(() => expect(create).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('We could not start')).not.toBeInTheDocument();
  });
});
