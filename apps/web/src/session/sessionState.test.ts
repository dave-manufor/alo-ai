import { describe, expect, it } from 'vitest';
import { applyAgentMessage, initialSessionState } from './sessionState';

const v3 = { schema_version: 3 } as const;

describe('the child-speaking light', () => {
  it('follows the agent: on when the child starts speaking, off when they stop', () => {
    const on = applyAgentMessage(initialSessionState, { ...v3, cmd: 'child_speaking', speaking: true });
    expect(on.childSpeaking).toBe(true);
    const off = applyAgentMessage(on, { ...v3, cmd: 'child_speaking', speaking: false });
    expect(off.childSpeaking).toBe(false);
  });

  it('does not move the session on: the step, passage and clip are untouched', () => {
    const before = applyAgentMessage(initialSessionState, { ...v3, cmd: 'step', step: 'READING' });
    const after = applyAgentMessage(before, { ...v3, cmd: 'child_speaking', speaking: true });
    expect(after).toEqual({ ...before, childSpeaking: true });
  });

  it('clears on a reconnect, so a lost "stopped" cannot leave it lit', () => {
    const on = applyAgentMessage(initialSessionState, { ...v3, cmd: 'child_speaking', speaking: true });
    const lost = applyAgentMessage(on, { ...v3, cmd: 'reconnecting' });
    expect(lost.childSpeaking).toBe(false);
    expect(lost.reconnecting).toBe(true);
  });

  it('a child_speaking after a reconnect means the call is back', () => {
    const lost = applyAgentMessage(initialSessionState, { ...v3, cmd: 'reconnecting' });
    expect(applyAgentMessage(lost, { ...v3, cmd: 'child_speaking', speaking: true }).reconnecting).toBe(
      false,
    );
  });
});
