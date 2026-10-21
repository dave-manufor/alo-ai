import { missingAck, playedAck, type ClipEntry, type ClientMessage } from './protocol';

// Clip cache (PRD 4.4, protocol v2): every clip is fully downloaded
// before it is played, so a slow connection never delays a prompt —
// most of all a told word, which must start at once, every time.
//   - `missing` is only ever a reply to a `play`, never sent at download
//     time (the agent answers a download-time missing by streaming clips
//     out of order). Failed downloads retry quietly instead.
//   - A `play` for a clip still downloading WAITS for that download
//     before answering, so the two sides cannot loop on missing.
//   - `played` is sent when playback FINISHES (the audio's ended event),
//     because the agent starts the child's answer window from that ack.

export interface ClipPlayer {
  /** Plays a downloaded clip; resolves when it has finished. */
  play(clip_id: string, objectUrl: string | undefined): Promise<void>;
}

export interface ClipCache {
  /** Fully downloads a clip_list (retrying failures quietly). Never acks. */
  downloadAll(clips: ClipEntry[]): Promise<void>;
  /** Plays in reply to an agent `play`; resolves with the ack to send. */
  play(clip_id: string): Promise<ClientMessage>;
  has(clip_id: string): boolean;
  textFor(clip_id: string): string | null;
}

export function createClipCache(deps: {
  load: (url: string) => Promise<string | undefined>;
  player: ClipPlayer;
}): ClipCache {
  const downloads = new Map<string, Promise<boolean>>();
  const objectUrls = new Map<string, string>();
  const texts = new Map<string, string | null>();

  function startDownload(clip: ClipEntry): Promise<boolean> {
    const existing = downloads.get(clip.clip_id);
    if (existing) return existing;
    const promise = (async () => {
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          const objectUrl = await deps.load(clip.url);
          if (objectUrl) {
            objectUrls.set(clip.clip_id, objectUrl);
            return true;
          }
        } catch {
          // Retry quietly; never answer missing outside a play.
        }
      }
      return false;
    })();
    downloads.set(clip.clip_id, promise);
    return promise;
  }

  return {
    async downloadAll(clips) {
      for (const clip of clips) texts.set(clip.clip_id, clip.text);
      await Promise.all(clips.map((clip) => startDownload(clip)));
    },
    async play(clip_id) {
      const inFlight = downloads.get(clip_id);
      if (inFlight) await inFlight;
      if (!objectUrls.has(clip_id) && !downloads.has(clip_id)) {
        return missingAck(clip_id);
      }
      const downloaded = downloads.has(clip_id) ? await downloads.get(clip_id) : false;
      if (!downloaded && !objectUrls.has(clip_id)) return missingAck(clip_id);
      try {
        await deps.player.play(clip_id, objectUrls.get(clip_id));
        return playedAck(clip_id);
      } catch {
        return missingAck(clip_id);
      }
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
 *  ships for it. Played inside the tap gesture to unlock the element. */
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
  const bytes = new Uint8Array(buffer);
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return `data:audio/wav;base64,${btoa(binary)}`;
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
      })
      .catch(() => undefined);
  } catch {
    // No audio available; playback attempts will surface as missing.
  }
}
