import { describe, expect, it, vi } from 'vitest';

// The adapter around livekit-client, with the library faked (no WebRTC in jsdom).
const handlers = vi.hoisted(() => ({ map: new Map<string, (...args: unknown[]) => void>() }));
const lk = vi.hoisted(() => ({
  connect: vi.fn(async () => undefined),
  disconnect: vi.fn(async () => undefined),
  publishData: vi.fn(async () => undefined),
  setMicrophoneEnabled: vi.fn(async () => undefined),
  publishTrack: vi.fn(async () => undefined),
}));

vi.mock('livekit-client', () => ({
  Track: { Source: { Microphone: 'microphone' } },
  RoomEvent: {
    DataReceived: 'data',
    Reconnecting: 'reconnecting',
    Reconnected: 'reconnected',
    Disconnected: 'disconnected',
  },
  Room: class {
    localParticipant = {
      publishData: lk.publishData,
      setMicrophoneEnabled: lk.setMicrophoneEnabled,
      publishTrack: lk.publishTrack,
    };
    connect = lk.connect;
    disconnect = lk.disconnect;
    on(event: string, handler: (...args: unknown[]) => void) {
      handlers.map.set(event, handler);
    }
  },
}));

import { openLiveKitRoom } from './liveDriver';

describe('openLiveKitRoom', () => {
  it('connects with the token, maps events, publishes reliably on the topic, enables the mic', async () => {
    const room = await openLiveKitRoom('wss://lk.example.test', 'tok');
    expect(lk.connect).toHaveBeenCalledWith('wss://lk.example.test', 'tok');

    const data = vi.fn();
    const conn = vi.fn();
    room.onData(data);
    room.onConnection(conn);
    const payload = new Uint8Array([1]);
    handlers.map.get('data')?.(payload, undefined, undefined, 'aloai.session');
    handlers.map.get('reconnecting')?.();
    handlers.map.get('reconnected')?.();
    handlers.map.get('disconnected')?.();
    expect(data).toHaveBeenCalledWith(payload, 'aloai.session');
    expect(conn.mock.calls.map((c) => c[0])).toEqual(['reconnecting', 'reconnected', 'disconnected']);

    await room.publishData(payload as Uint8Array<ArrayBuffer>, 'aloai.session');
    expect(lk.publishData).toHaveBeenCalledWith(payload, { reliable: true, topic: 'aloai.session' });
    await room.enableMicrophone();
    expect(lk.setMicrophoneEnabled).toHaveBeenCalledWith(true);
    room.disconnect();
    expect(lk.disconnect).toHaveBeenCalled();
  });

  it('publishes the microphone track the app already opened, and does not ask for another', async () => {
    lk.setMicrophoneEnabled.mockClear();
    const room = await openLiveKitRoom('wss://lk.example.test', 'tok');
    const track = { readyState: 'live' } as MediaStreamTrack;
    await room.enableMicrophone(track);
    expect(lk.publishTrack).toHaveBeenCalledWith(track, { source: 'microphone' });
    expect(lk.setMicrophoneEnabled).not.toHaveBeenCalled();
  });

  it('asks the browser again when there is no track, or the track has ended (after a rejoin)', async () => {
    lk.publishTrack.mockClear();
    lk.setMicrophoneEnabled.mockClear();
    const room = await openLiveKitRoom('wss://lk.example.test', 'tok');
    await room.enableMicrophone();
    await room.enableMicrophone({ readyState: 'ended' } as MediaStreamTrack);
    expect(lk.publishTrack).not.toHaveBeenCalled();
    expect(lk.setMicrophoneEnabled).toHaveBeenCalledTimes(2);
  });
});
