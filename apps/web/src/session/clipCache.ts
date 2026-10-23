import { dataMode } from '../api/mode';
import { missingAck, playedAck, type ClipEntry, type ClientMessage } from './protocol';

// Clip cache (PRD 4.4, protocol v2): the clips are downloaded into the phone before they
// are played, so a slow connection never delays a prompt — most of all a told word, which
// must start at once, every time.
//   - Downloads run in the background, a few at a time, in the order the agent listed them
//     (it lists what the session needs first). Nothing waits for the whole list: a clip is
//     played as soon as ITS download is done.
//   - A `play` for a clip that has not started downloading jumps the queue, and WAITS for
//     that one download before answering, so the two sides cannot loop on missing.
//   - `missing` is only ever a reply to a `play`, never sent at download time (the agent
//     answers a download-time missing by streaming clips out of order). A download that
//     fails twice is forgotten, so a later clip_list for the same clip (the agent's stream
//     retry) tries again instead of being handed the old failure.
//   - `played` is sent when playback FINISHES (the audio's ended event),
//     because the agent starts the child's answer window from that ack.

export interface ClipPlayer {
  /** Plays a downloaded clip; resolves when it has finished. */
  play(clip_id: string, objectUrl: string | undefined): Promise<void>;
}

export interface ClipCache {
  /** Queues a clip_list for download (retrying failures quietly). Never acks. The promise
   *  resolves when THESE clips are done; callers should not wait on it before playing. */
  downloadAll(clips: ClipEntry[]): Promise<void>;
  /** Plays in reply to an agent `play`; resolves with the ack to send. */
  play(clip_id: string): Promise<ClientMessage>;
  /** Resolves when every clip listed so far that matches `filter` has finished downloading
   *  (or failed), or after `timeoutMs`, whichever is first. */
  settled(filter: (clip_id: string) => boolean, timeoutMs: number): Promise<void>;
  has(clip_id: string): boolean;
  textFor(clip_id: string): string | null;
}

/** How many clips download at once. A phone on mobile data does better with a few. */
export const MAX_PARALLEL_DOWNLOADS = 4;

export function createClipCache(deps: {
  load: (url: string) => Promise<string | undefined>;
  player: ClipPlayer;
  parallel?: number;
}): ClipCache {
  const parallel = deps.parallel ?? MAX_PARALLEL_DOWNLOADS;
  const downloads = new Map<string, Promise<boolean>>();
  const objectUrls = new Map<string, string>();
  const texts = new Map<string, string | null>();
  const finish = new Map<string, (ok: boolean) => void>();
  const waiting: ClipEntry[] = []; // queued, not started
  let active = 0;

  async function fetchClip(clip: ClipEntry): Promise<void> {
    let ok = false;
    for (let attempt = 0; attempt < 2 && !ok; attempt += 1) {
      try {
        const objectUrl = await deps.load(clip.url);
        if (objectUrl) {
          objectUrls.set(clip.clip_id, objectUrl);
          ok = true;
        }
      } catch {
        // Retry quietly; never answer missing outside a play.
      }
    }
    // A failure is forgotten before anyone is told, so the next clip_list tries again.
    if (!ok) downloads.delete(clip.clip_id);
    finish.get(clip.clip_id)?.(ok);
    finish.delete(clip.clip_id);
  }

  function pump(): void {
    while (active < parallel && waiting.length > 0) {
      const clip = waiting.shift() as ClipEntry;
      active += 1;
      void fetchClip(clip).finally(() => {
        active -= 1;
        pump();
      });
    }
  }

  function startDownload(clip: ClipEntry): Promise<boolean> {
    const existing = downloads.get(clip.clip_id);
    if (existing) return existing;
    if (objectUrls.has(clip.clip_id)) return Promise.resolve(true);
    const promise = new Promise<boolean>((resolve) => finish.set(clip.clip_id, resolve));
    downloads.set(clip.clip_id, promise);
    waiting.push(clip);
    pump();
    return promise;
  }

  /** A clip about to be played goes to the front of the queue. */
  function prioritise(clip_id: string): void {
    const at = waiting.findIndex((clip) => clip.clip_id === clip_id);
    if (at > 0) waiting.unshift(...waiting.splice(at, 1));
  }

  return {
    async downloadAll(clips) {
      for (const clip of clips) texts.set(clip.clip_id, clip.text);
      await Promise.all(clips.map((clip) => startDownload(clip)));
    },
    async play(clip_id) {
      if (!objectUrls.has(clip_id)) {
        const inFlight = downloads.get(clip_id);
        if (!inFlight) return missingAck(clip_id); // never listed, or it failed
        prioritise(clip_id);
        if (!(await inFlight)) return missingAck(clip_id);
      }
      try {
        await deps.player.play(clip_id, objectUrls.get(clip_id));
        return playedAck(clip_id);
      } catch {
        return missingAck(clip_id);
      }
    },
    async settled(filter, timeoutMs) {
      const open = [...downloads.entries()].filter(([id]) => filter(id)).map(([, promise]) => promise);
      if (open.length === 0) return;
      let timer: ReturnType<typeof setTimeout> | undefined;
      const timeout = new Promise<void>((resolve) => {
        timer = setTimeout(resolve, timeoutMs);
      });
      await Promise.race([Promise.all(open).then(() => undefined), timeout]);
      clearTimeout(timer);
    },
    has: (clip_id) => objectUrls.has(clip_id),
    textFor: (clip_id) => texts.get(clip_id) ?? null,
  };
}

/**
 * Browser loader: stores the clip's bytes in Cache Storage (SDD 4) and
 * returns an object URL for playback, so the browser cannot decide to
 * fetch it again at play time.
 */
export async function loadClipIntoCache(url: string): Promise<string | undefined> {
  try {
    const cache = await caches.open('alo-clips');
    await cache.add(url);
    const response = await cache.match(url);
    if (response) return URL.createObjectURL(await response.blob());
  } catch {
    // Cache Storage can be unavailable; fall back to a plain fetch.
  }
  const response = await fetch(url);
  if (!response.ok) return undefined;
  return URL.createObjectURL(await response.blob());
}

// One shared <audio> element for the whole session. iOS Safari only
// unlocks an HTMLAudioElement that has played inside a user gesture —
// unlocking an AudioContext does NOT unlock it — so the element that
// will play the clips is the element primed by the "Ààlọ̀!" tap, and
// every clip reuses it (swap src). A fresh `new Audio()` per clip can
// have its first agent-driven play() rejected on iOS, which would be
// answered `missing` and leave Kemi silent.
let sharedAudio: HTMLAudioElement | null = null;

function getSharedAudio(): HTMLAudioElement {
  if (!sharedAudio) {
    sharedAudio = new Audio();
    sharedAudio.preload = 'auto';
  }
  return sharedAudio;
}

/** A tiny silent WAV (80 samples at 8 kHz), built in code so no asset
 *  ships for it. Played inside the tap gesture to unlock the element. It is a blob: URL,
 *  not a data: URL, because the site's Content-Security-Policy (media-src) allows blob: only:
 *  with data: the unlock was blocked and iOS then refused the agent's later plays. */
function silentClipUrl(): string {
  const sampleRate = 8000;
  const samples = 80;
  const buffer = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(buffer);
  const writeAscii = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
  };
  writeAscii(0, 'RIFF');
  view.setUint32(4, 36 + samples * 2, true);
  writeAscii(8, 'WAVEfmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(36, 'data');
  view.setUint32(40, samples * 2, true); // sample bytes stay zero: silence
  return URL.createObjectURL(new Blob([buffer], { type: 'audio/wav' }));
}

/** Browser player: plays through the shared element and resolves on
 *  its `ended` event, so `played` still means playback finished. */
export const browserPlayer: ClipPlayer = {
  play(_clip_id, objectUrl) {
    return new Promise((resolve, reject) => {
      if (!objectUrl) {
        reject(new Error('clip not downloaded'));
        return;
      }
      const audio = getSharedAudio();
      audio.onended = () => resolve();
      audio.onerror = () => reject(new Error('clip failed to play'));
      audio.pause();
      audio.src = objectUrl;
      void audio.play().catch(reject);
    });
  },
};

/** Called from the "Ààlọ̀!" tap (a user gesture): plays the silent
 *  clip on the shared element so later agent-driven play() calls are
 *  allowed on iOS Safari for the whole session. */
export function unlockAudio(): void {
  try {
    const audio = getSharedAudio();
    const silentUrl = silentClipUrl();
    audio.src = silentUrl;
    void audio
      .play()
      .then(() => {
        // Only pause if a real clip has not already taken over the element.
        if (audio.src === silentUrl) {
          audio.pause();
          audio.currentTime = 0;
        }
        URL.revokeObjectURL(silentUrl);
      })
      .catch(() => undefined);
  } catch {
    // No audio available; playback attempts will surface as missing.
  }
}

/**
 * The cache this build uses (D4). Live build: every clip in the live
 * clip_list is downloaded into Cache Storage and played from there, so a
 * slow connection never delays a prompt, and a clip that could not be
 * downloaded is answered `missing` when the agent plays it. Fixture
 * build: nothing is fetched (the build stays network-free).
 */
export function createSessionClipCache(): ClipCache {
  if (dataMode === 'live') {
    return createClipCache({ load: loadClipIntoCache, player: browserPlayer });
  }
  return createClipCache({
    load: async (url) => `fixture:${url}`,
    // Sample build: no audio, but a clip "plays" for about as long as a short sentence,
    // so the screen can show Auntie Kemi speaking.
    player: {
      play: (clip_id) =>
        new Promise<void>((resolve) =>
          setTimeout(resolve, import.meta.env.MODE === 'test' ? 0 : clip_id.startsWith('word_') ? 1800 : 2800),
        ),
    },
  });
}
