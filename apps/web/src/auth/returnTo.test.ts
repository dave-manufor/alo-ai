import { beforeEach, describe, expect, it } from 'vitest';
import { clearReturnTo, peekReturnTo, saveReturnTo } from './returnTo';

describe('the screen to come back to after sign-in', () => {
  beforeEach(() => clearReturnTo());

  it('keeps a path in this app until the sign-in ends', () => {
    saveReturnTo('/reports/sess_1?x=1');
    expect(peekReturnTo()).toBe('/reports/sess_1?x=1');
    expect(peekReturnTo()).toBe('/reports/sess_1?x=1');
    clearReturnTo();
    expect(peekReturnTo()).toBeNull();
  });

  it('refuses anything that is not a path inside the app', () => {
    for (const bad of ['https://evil.example/', '//evil.example', 'reports', '/signin', '/signin?x=1']) {
      saveReturnTo(bad);
      expect(peekReturnTo()).toBeNull();
    }
  });

  it('forgets a path after fifteen minutes', () => {
    saveReturnTo('/plan', 1_000);
    expect(peekReturnTo(1_000 + 14 * 60 * 1000)).toBe('/plan');
    expect(peekReturnTo(1_000 + 16 * 60 * 1000)).toBeNull();
  });

  it('ignores a damaged value', () => {
    window.sessionStorage.setItem('alo.returnTo', '{not json');
    expect(peekReturnTo()).toBeNull();
    window.sessionStorage.setItem('alo.returnTo', JSON.stringify({ path: 'https://x', at: Date.now() }));
    expect(peekReturnTo()).toBeNull();
  });
});
