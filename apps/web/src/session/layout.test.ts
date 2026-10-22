import { describe, expect, it } from 'vitest';
import { computeLayout } from './layout';

// Positions are the design artifact's `layout(w, h)`, so the numbers below
// are what the artifact computes for the same screen.
describe('computeLayout (the artifact layout, per screen size)', () => {
  it('phone portrait: story card under a 78 px top bar, light in the corner', () => {
    const L = computeLayout(390, 844);
    expect(L.phone).toBe(true);
    expect(L.portrait).toBe(true);
    expect(L.card).toEqual({ x: 14, y: 78, w: 362, h: 752 });
    expect(L.corner).toEqual({ x: 38, y: 45, R: 17 });
    expect(L.center.y).toBeCloseTo(337.6, 1);
    expect(L.moon.x).toBeCloseTo(296.4, 1);
  });

  it('tablet portrait uses the larger pad and light', () => {
    const L = computeLayout(768, 1024);
    expect(L.phone).toBe(false);
    expect(L.portrait).toBe(true);
    expect(L.pad).toBe(27);
    expect(L.R0).toBeCloseTo(112, 0);
  });

  it('landscape phone: card centred, Japa peeks at the side or the top bar', () => {
    const L = computeLayout(915, 412);
    expect(L.portrait).toBe(false);
    expect(L.card.x).toBeGreaterThan(0);
    expect(L.card.x + L.card.w).toBeLessThanOrEqual(915);
    expect(L.card.y + L.card.h).toBeLessThanOrEqual(412);
    expect(L.moon.x).toBeCloseTo(915 * 0.82, 5);
  });

  it('never puts the card outside the screen at any size', () => {
    for (const [w, h] of [
      [320, 480],
      [360, 640],
      [412, 915],
      [820, 1180],
      [1280, 800],
    ]) {
      const L = computeLayout(w, h);
      expect(L.card.x).toBeGreaterThanOrEqual(0);
      expect(L.card.x + L.card.w).toBeLessThanOrEqual(w);
      expect(L.card.y + L.card.h).toBeLessThanOrEqual(h);
    }
  });
});
