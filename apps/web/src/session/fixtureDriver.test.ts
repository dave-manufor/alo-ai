import { describe, expect, it } from 'vitest';
import type { AgentMessage } from './protocol';
import { createFixtureDriver } from './fixtureDriver';

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('fixtureDriver as a SessionDriver', () => {
  it('opens with clip_list, step and the first play, in order', async () => {
    const seen: AgentMessage[] = [];
    const driver = createFixtureDriver();
    driver.start((message) => {
      seen.push(message);
    });
    await settle();
    expect(seen.map((m) => m.cmd)).toEqual(['clip_list', 'step', 'play']);
    driver.stop();
  });

  it('moves on only when the child acts, and closes after two answers', async () => {
    const seen: AgentMessage[] = [];
    const driver = createFixtureDriver();
    driver.start((message) => {
      seen.push(message);
    });
    // The session opens at MIC_CHECK (no interest buttons, as in the design).
    driver.send('child_spoke'); // -> READING
    driver.send('child_spoke'); // -> RETELL
    driver.send('child_spoke'); // -> QUESTIONS
    driver.send('child_spoke'); // answer 1
    driver.send('child_spoke'); // answer 2 -> CLOSE
    await settle();
    const steps = seen.filter((m) => m.cmd === 'step').map((m) => (m as { step: string }).step);
    expect(steps).toEqual(['MIC_CHECK', 'READING', 'RETELL', 'QUESTIONS', 'CLOSE']);
    driver.stop();
  });

  it('delivers nothing after stop()', async () => {
    const seen: AgentMessage[] = [];
    const driver = createFixtureDriver();
    driver.start((message) => {
      seen.push(message);
    });
    driver.stop();
    driver.send('topic_chosen');
    await settle();
    expect(seen.length).toBeLessThanOrEqual(3);
    expect(seen.some((m) => m.cmd === 'step' && m.step === 'MIC_CHECK')).toBe(false);
  });
});
