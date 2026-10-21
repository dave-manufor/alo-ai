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

/** Browser player: resolves on the audio element's `ended` event. */
export const browserPlayer: ClipPlayer = {
  play(_clip_id, objectUrl) {
    return new Promise((resolve, reject) => {
      if (!objectUrl) {
        reject(new Error('clip not downloaded'));
        return;
      }
      const audio = new Audio(objectUrl);
      audio.addEventListener('ended', () => resolve(), { once: true });
      audio.addEventListener('error', () => reject(new Error('clip failed to play')), {
        once: true,
      });
      void audio.play().catch(reject);
    });
  },
};

/** iOS Safari only plays audio after a user gesture; the "Ààlọ̀!" tap
 *  unlocks the shared context for the whole session. */
export function unlockAudio(): void {
  try {
    const Ctor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (Ctor) {
      const context = new Ctor();
      void context.resume().catch(() => undefined);
    }
  } catch {
    // No audio context available; playback attempts will surface as missing.
  }
}
