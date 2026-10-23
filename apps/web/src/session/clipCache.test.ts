import { afterEach, describe, expect, it, vi } from 'vitest';
import { createClipCache, unlockAudio } from './clipCache';
import type { ClipEntry } from './protocol';

const clip = (id: string): ClipEntry => ({ clip_id: id, url: `https://clips.example/${id}.mp3`, text: `say ${id}` });
const ids = (n: number, prefix = 'c') => Array.from({ length: n }, (_, i) => clip(`${prefix}${i}`));

/** A loader whose downloads finish only when the test says so, to see what runs at once. */
function manualLoader() {
  const started: string[] = [];
  const open = new Map<string, (url: string | undefined) => void>();
  const load = (url: string) =>
    new Promise<string | undefined>((resolve) => {
      const id = url.split('/').pop()!.replace('.mp3', '');
      started.push(id);
      open.set(id, resolve);
    });
  const done = async (id: string, url: string | undefined = `blob:${id}`) => {
    open.get(id)?.(url);
    open.delete(id);
    await Promise.resolve();
    await Promise.resolve();
  };
  return { load, started, open, done };
}

const player = () => ({ play: vi.fn(async () => undefined) });
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('the clip cache', () => {
  it('downloads a few clips at a time, in the order the agent listed them', async () => {
    const loader = manualLoader();
    const cache = createClipCache({ load: loader.load, player: player(), parallel: 3 });
    void cache.downloadAll(ids(8));
    await flush();
    expect(loader.started).toEqual(['c0', 'c1', 'c2']); // not all eight at once
    await loader.done('c0');
    expect(loader.started).toEqual(['c0', 'c1', 'c2', 'c3']); // the next in line, in order
    await loader.done('c1');
    await loader.done('c2');
    expect(loader.started.slice(4)).toEqual(['c4', 'c5']);
  });

  it('a clip is played as soon as ITS download is done, not the whole list', async () => {
    const loader = manualLoader();
    const p = player();
    const cache = createClipCache({ load: loader.load, player: p, parallel: 4 });
    void cache.downloadAll(ids(10));
    await flush();
    const acked = cache.play('c1');
    await loader.done('c1');
    expect(await acked).toEqual({ schema_version: 3, cmd: 'played', clip_id: 'c1' });
    expect(p.play).toHaveBeenCalledWith('c1', 'blob:c1');
    expect(loader.open.has('c1')).toBe(false);
    expect(loader.open.size).toBe(4); // the rest are still going: the next in line took its place
  });

  it('a play for a clip that is still queued jumps the queue', async () => {
    const loader = manualLoader();
    const cache = createClipCache({ load: loader.load, player: player(), parallel: 2 });
    void cache.downloadAll(ids(6));
    await flush();
    expect(loader.started).toEqual(['c0', 'c1']);
    const acked = cache.play('c5'); // the agent wants the last one now
    await loader.done('c0');
    expect(loader.started[2]).toBe('c5'); // next, ahead of c2, c3, c4
    await loader.done('c5');
    expect((await acked).cmd).toBe('played');
  });

  it('a clip that cannot be downloaded is missing only when it is played, and is tried again later', async () => {
    const attempts: string[] = [];
    const cache = createClipCache({
      load: async (url) => {
        attempts.push(url);
        return attempts.length > 2 ? 'blob:ok' : undefined; // fails twice, then works
      },
      player: player(),
    });
    await cache.downloadAll([clip('a')]);
    expect(attempts).toHaveLength(2); // two quiet tries, no ack from the download
    expect(cache.has('a')).toBe(false);
    expect((await cache.play('a')).cmd).toBe('missing'); // forgotten, so unknown now
    await cache.downloadAll([clip('a')]); // the agent's stream retry lists it again
    expect(attempts).toHaveLength(3);
    expect(cache.has('a')).toBe(true);
    expect((await cache.play('a')).cmd).toBe('played');
  });

  it('a clip the agent never listed is missing', async () => {
    const cache = createClipCache({ load: async () => 'blob:x', player: player() });
    expect(await cache.play('nope')).toEqual({ schema_version: 3, cmd: 'missing', clip_id: 'nope' });
  });

  it('a clip that downloads but will not play is missing', async () => {
    const cache = createClipCache({
      load: async () => 'blob:x',
      player: { play: async () => Promise.reject(new Error('blocked')) },
    });
    await cache.downloadAll([clip('a')]);
    expect((await cache.play('a')).cmd).toBe('missing');
  });

  it('a clip listed twice is downloaded once, and its text is known at once', async () => {
    const load = vi.fn(async () => 'blob:x');
    const cache = createClipCache({ load, player: player() });
    void cache.downloadAll([clip('a')]);
    expect(cache.textFor('a')).toBe('say a'); // before any download finishes
    await cache.downloadAll([clip('a')]);
    await cache.downloadAll([clip('a')]); // already downloaded
    expect(load).toHaveBeenCalledTimes(1);
    expect(cache.textFor('missing')).toBeNull();
  });

  it('settled waits for the matching clips, and gives up after the timeout', async () => {
    const loader = manualLoader();
    const cache = createClipCache({ load: loader.load, player: player(), parallel: 8 });
    void cache.downloadAll([clip('word_a'), clip('word_b'), clip('story')]);
    await flush();
    let words = false;
    void cache.settled((id) => id.startsWith('word_'), 10_000).then(() => (words = true));
    await loader.done('word_a');
    expect(words).toBe(false);
    await loader.done('word_b'); // the story is still going: not waited for
    await flush();
    expect(words).toBe(true);

    vi.useFakeTimers();
    let gaveUp = false;
    void cache.settled((id) => id === 'story', 8_000).then(() => (gaveUp = true));
    await vi.advanceTimersByTimeAsync(7_999);
    expect(gaveUp).toBe(false);
    await vi.advanceTimersByTimeAsync(2);
    expect(gaveUp).toBe(true);
    vi.useRealTimers();
  });

  it('settled returns at once when nothing matches', async () => {
    const cache = createClipCache({ load: async () => 'blob:x', player: player() });
    await cache.settled((id) => id.startsWith('word_'), 8_000);
  });
});

describe('unlocking the audio element', () => {
  const realCreate = URL.createObjectURL;
  const realRevoke = URL.revokeObjectURL;
  afterEach(() => {
    URL.createObjectURL = realCreate;
    URL.revokeObjectURL = realRevoke;
    vi.restoreAllMocks();
  });

  it('plays a blob: URL, which the site policy allows, never a data: URL', async () => {
    const made: Blob[] = [];
    URL.createObjectURL = vi.fn((blob: Blob | MediaSource) => {
      made.push(blob as Blob);
      return 'blob:silent';
    });
    URL.revokeObjectURL = vi.fn();
    const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined);
    unlockAudio();
    await flush();
    expect(play).toHaveBeenCalled();
    expect(made).toHaveLength(1);
    expect(made[0].type).toBe('audio/wav');
    const audio = play.mock.contexts[0] as HTMLAudioElement;
    expect(audio.src.startsWith('data:')).toBe(false);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:silent');
  });
});
