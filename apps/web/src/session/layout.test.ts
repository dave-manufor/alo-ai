import { describe, expect, it } from 'vitest';
import { liveApi } from '../api';

// jsdom has no layout engine, so the breakpoints cannot be exercised by
// resizing. These tests pin the layout CONTRACT in the stylesheet (B4);
// how it actually looks at the presets is the real-browser check (B12).
const nodeFs = 'node:fs';
const { readFileSync } = (await import(/* @vite-ignore */ nodeFs)) as {
  readFileSync(path: string, encoding: string): string;
};
const css = readFileSync('src/styles/session.css', 'utf8');
const appCss = readFileSync('src/styles/app.css', 'utf8');

describe('session.css layout contract (B4, B11)', () => {
  it('uses tokens only: no hex colour anywhere in the app styles', () => {
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(appCss).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('has rules for short screens, landscape phones and tablets', () => {
    expect(css).toMatch(/@media \(max-height: 40rem\)/); // small Android phone
    expect(css).toMatch(/@media \(orientation: landscape\) and \(max-height: 30rem\)/); // landscape
    expect(css).toMatch(/@media \(min-width: 48rem\)/); // tablet
  });

  it('respects safe areas, dynamic viewport height and avoids horizontal scroll', () => {
    expect(css).toMatch(/env\(safe-area-inset-top/);
    expect(css).toMatch(/env\(safe-area-inset-bottom/);
    expect(appCss).toMatch(/100dvh/);
    expect(css).toMatch(/overflow-wrap: anywhere/);
    expect(css).toMatch(/\.night-session \{[^}]*overflow: hidden/);
  });

  it('respects prefers-reduced-motion', () => {
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
  });

  it('keeps the grown-up hold gate at least the kid tap size', () => {
    expect(css).toMatch(/\.hold-to-confirm \{[^}]*min-height: var\(--tap-kid\)/);
  });
});

describe('the API client in a fixture build', () => {
  it('refuses to exist, so the fixture build cannot make API calls', () => {
    expect(() => liveApi()).toThrow(/not configured/);
  });
});
