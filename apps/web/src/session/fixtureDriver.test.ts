import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AgentMessage } from './protocol';
import { PACE, createFixtureDriver, fixtureClips, QUESTION_COUNT } from './fixtureDriver';

async function settle() {
  await vi.advanceTimersByTimeAsync(0);
}

const stepsOf = (seen: AgentMessage[]) =>
  seen.filter((m) => m.cmd === 'step').map((m) => (m as { step: string }).step);

describe('fixtureDriver as a SessionDriver', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('sends the clip list at once, then opens at the mic check after the call', async () => {
    const seen: AgentMessage[] = [];
    const driver = createFixtureDriver({ autoAdvance: false });
    driver.start((message) => {
      seen.push(message);
    });
    await settle();
    expect(seen.map((m) => m.cmd)).toEqual(['clip_list']);
    await vi.advanceTimersByTimeAsync(PACE.call);
    expect(seen.map((m) => m.cmd)).toEqual(['clip_list', 'step', 'play']);
    expect(stepsOf(seen)).toEqual(['MIC_CHECK']);
    driver.stop();
  });

  it('can still open with the interest chat (a valid protocol step)', async () => {
    const seen: AgentMessage[] = [];
    const driver = createFixtureDriver({ autoAdvance: false, opening: 'INTEREST_CHAT' });
    driver.start((message) => {
      seen.push(message);
    });
    await vi.advanceTimersByTimeAsync(PACE.call);
    expect(stepsOf(seen)).toEqual(['INTEREST_CHAT']);
    driver.send('topic_chosen');
    await settle();
    expect(stepsOf(seen)).toEqual(['INTEREST_CHAT', 'MIC_CHECK']);
    driver.stop();
  });

  it('moves on when the child acts, and closes after the last answer', async () => {
    const seen: AgentMessage[] = [];
    const driver = createFixtureDriver({ autoAdvance: false });
    driver.start((message) => {
      seen.push(message);
    });
    await vi.advanceTimersByTimeAsync(PACE.call);
    driver.send('child_spoke'); // -> READING
    driver.send('child_spoke'); // -> RETELL
    driver.send('child_spoke'); // -> QUESTIONS
    for (let i = 0; i < QUESTION_COUNT; i += 1) driver.send('child_spoke');
    await settle();
    expect(stepsOf(seen)).toEqual(['MIC_CHECK', 'READING', 'RETELL', 'QUESTIONS', 'CLOSE']);
    const played = seen.filter((m) => m.cmd === 'play').map((m) => (m as { clip_id: string }).clip_id);
    expect(played).toContain('question:2');
    expect(fixtureClips.some((c) => c.clip_id === 'question:2')).toBe(true);
    driver.stop();
  });

  it('paces itself like the agent hearing the child: the whole session ends by itself', async () => {
    const seen: AgentMessage[] = [];
    const driver = createFixtureDriver();
    driver.start((message) => {
      seen.push(message);
    });
    await vi.advanceTimersByTimeAsync(120_000);
    expect(stepsOf(seen)).toEqual([
      'MIC_CHECK',
      'READING',
      'RETELL',
      'QUESTIONS',
      'CLOSE',
      'ENDED',
    ]);
    driver.stop();
  });

  it('delivers nothing after stop()', async () => {
    const seen: AgentMessage[] = [];
    const driver = createFixtureDriver();
    driver.start((message) => {
      seen.push(message);
    });
    driver.stop();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(seen.some((m) => m.cmd === 'step')).toBe(false);
  });
});
