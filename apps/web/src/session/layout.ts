// Where everything on the Night session screen sits, computed from the
// screen's width and height. A line-for-line port of `layout(w, h)` in the
// "Àlọ́ Night Session V" design artifact (the source of truth for this
// screen); the numbers are the artifact's, not ours.

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Layout {
  w: number;
  h: number;
  m: number;
  portrait: boolean;
  phone: boolean;
  pad: number;
  R0: number;
  center: { x: number; y: number };
  card: Rect;
  corner: { x: number; y: number; R: number };
  peek: { x0: number; x1: number; y0: number; y1: number; w: number };
  jw: number;
  moon: { x: number; y: number };
  bottom: { x: number; y: number };
  cheer: { x: number; y: number };
  con: { x: number; y: number; s: number };
  callY: number;
  callFs: number;
}

export const clamp = (x: number, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const lerp = (a: number, b: number, u: number) => a + (b - a) * u;

export function computeLayout(w: number, h: number): Layout {
  const m = Math.min(w, h);
  const portrait = h >= w * 1.12;
  const phone = portrait && w <= 500;
  const pad = m < 400 ? 14 : Math.round(clamp(m * 0.035, 16, 36));
  const R0 = clamp(m * 0.17, 46, 112);
  const center = { x: w / 2, y: portrait ? h * 0.4 : h * 0.42 };
  let card: Rect;
  let corner: Layout['corner'];
  let peek: Layout['peek'];
  if (portrait) {
    const topBar = phone ? 78 : Math.max(72, h * 0.075);
    card = { x: pad, y: topBar, w: w - 2 * pad, h: h - topBar - pad };
    corner = { x: pad + 24, y: topBar / 2 + (phone ? 6 : 0), R: 17 };
    const jSmall = Math.min(84, (topBar - 10) / 0.734);
    const py = (topBar - jSmall * 0.734) / 2 + (phone ? 6 : 0);
    peek = { x0: w + 10, x1: w - jSmall - pad, y0: py, y1: py, w: jSmall };
  } else {
    const cw = Math.min(w - 2 * pad - 150, Math.max(560, w * 0.6));
    const ch = h - Math.max(56, h * 0.08) - Math.max(24, h * 0.05);
    card = { x: (w - cw) / 2, y: Math.max(56, h * 0.08), w: cw, h: ch };
    corner = { x: Math.max(pad + 26, card.x / 2), y: card.y + 32, R: 20 };
    const side = w - (card.x + card.w);
    const jw = clamp(side - 2 * pad, 90, 150);
    if (side >= jw + pad) {
      peek = {
        x0: card.x + card.w + (side - jw) / 2,
        x1: card.x + card.w + (side - jw) / 2,
        y0: h + 10,
        y1: card.y + card.h - jw * 0.734,
        w: jw,
      };
    } else {
      const jSmall = Math.min(80, (card.y - 8) / 0.734);
      const py = (card.y - jSmall * 0.734) / 2;
      peek = { x0: w + 10, x1: w - jSmall - pad, y0: py, y1: py, w: jSmall };
    }
  }
  const jw = clamp(m * 0.3, 96, 170);
  return {
    w,
    h,
    m,
    portrait,
    phone,
    pad,
    R0,
    center,
    card,
    corner,
    peek,
    jw,
    moon: { x: w * (portrait ? 0.76 : 0.82), y: h * (portrait ? 0.13 : 0.17) },
    bottom: { x: w / 2 - jw / 2, y: h - jw * 0.734 - Math.max(pad * 2, h * 0.06) },
    cheer: { x: w / 2 - jw / 2, y: h * (portrait ? 0.7 : 0.68) },
    con: { x: w / 2, y: h * (portrait ? 0.38 : 0.42), s: clamp(m * 0.0046, 1.4, 3.6) },
    callY: center.y + R0 * 1.75,
    callFs: Math.round(R0 * 0.95),
  };
}
