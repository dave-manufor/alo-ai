import { missingAck, playedAck, type ClientMessage } from './protocol';

// Clip cache (PRD 4.4): every clip for the session is downloaded before
// reading starts and plays on the agent's command, so a slow connection
// never delays a prompt. The web app answers played / missing per clip.

export interface ClipCache {
  /** Download a clip_list; returns the ids that could not be downloaded. */
  downloadAll(clips: { clip_id: string; url: string }[]): Promise<string[]>;
  /** Play a cached clip. Answers with the ack to send back to the agent. */
  play(clip_id: string): ClientMessage;
  has(clip_id: string): boolean;
}

export function createClipCache(deps: {
  load: (url: string) => Promise<boolean>;
  playClip: (clip_id: string) => void;
}): ClipCache {
  const cached = new Set<string>();
  return {
    async downloadAll(clips) {
      const missing: string[] = [];
      await Promise.all(
        clips.map(async (clip) => {
          const ok = await deps.load(clip.url).catch(() => false);
          if (ok) cached.add(clip.clip_id);
          else missing.push(clip.clip_id);
        }),
      );
      return missing;
    },
    play(clip_id) {
      if (!cached.has(clip_id)) return missingAck(clip_id);
      deps.playClip(clip_id);
      return playedAck(clip_id);
    },
    has: (clip_id) => cached.has(clip_id),
  };
}

/** Browser loader: fetch the clip fully, then keep it for playback. */
export async function fetchClip(url: string): Promise<boolean> {
  const response = await fetch(url);
  return response.ok;
}
