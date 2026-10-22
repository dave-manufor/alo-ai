import { clamp, computeLayout, lerp, type Layout, type Rect } from './layout';

// The Night session screen's animation: a port of `render(t)`, `paginate()`
// and `relayout()` from the "Alo Night Session V" design artifact. The
// artifact plays a script; here the same picture is driven by the session's
// state (a `mode` plus a few flags) and eases between modes over 1.1 s, with
// the artifact's own formulas. DOM updates are direct (opacity and
// transform only), as in the artifact, so a phone is not asked to
// re-render React 60 times a second.

export type Mode =
  | 'start'
  | 'call'
  | 'seeds'
  | 'count'
  | 'think'
  | 'reading'
  | 'reconnect'
  | 'retell'
  | 'questions'
  | 'listen'
  | 'end'
  | 'hand';

export interface StageInput {
  mode: Mode;
  /** Auntie Kemi's clip is playing: her light pulses with rings. */
  speaking: boolean;
  /** The child is heard speaking: green light flows up into hers. Not sent by the driver yet. */
  childSpeaking: boolean;
  /** The child is counting (mic check): a light for each number. */
  counting: boolean;
  /** How many of the three question points are lit (0 to 3). */
  questionsLit: number;
  /** How many seed drawings (0 to 2) orbit the light. Not sent by the driver yet. */
  seeds: number;
  /** Japa peeks in beside the words (the child is stuck on a word). */
  peek: boolean;
  /** Japa nods at the bottom (a quiet child). Not sent by the driver yet. */
  nod: boolean;
  /** A story page is available while reconnecting. */
  pageVisible: boolean;
  /** The Start overlay (greeting and the microphone explainer) is up. */
  showStart: boolean;
}

export const defaultInput: StageInput = {
  mode: 'start',
  speaking: false,
  childSpeaking: false,
  counting: false,
  questionsLit: 0,
  seeds: 0,
  peek: false,
  nod: false,
  pageVisible: false,
  showStart: true,
};

const FS_MIN = 22;
const FS_MAX = 28;
const FS_FLOOR = 16;
const BLEND = 1.1;
const ease = (u: number) => {
  u = clamp(u);
  return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
};
const win = (t: number, a: number, b: number, c: number, d: number) =>
  t < a || t > d ? 0 : t < b ? (t - a) / (b - a) : t <= c ? 1 : 1 - (t - c) / (d - c);
const pulse = (t: number, a: number, len: number) =>
  t >= a && t < a + len ? Math.sin((Math.PI * (t - a)) / len) : 0;
const px = (n: number) => n.toFixed(1) + 'px';

const CLINES = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [4, 5],
  [1, 5],
  [1, 6],
  [5, 7],
];
const CBASE = [
  [110, 312],
  [124, 300],
  [140, 264],
  [182, 248],
  [224, 264],
  [240, 300],
  [136, 326],
  [230, 326],
  [270, 286],
];

const orbTarget = (L: Layout, mo: Mode): number[] => {
  const c = L.center;
  const R = L.R0;
  const k = L.corner;
  switch (mo) {
    case 'start':
      return [c.x, c.y, R * 0.15, 0];
    case 'reading':
      return [k.x, k.y, k.R, 1];
    case 'reconnect':
      return [k.x, k.y, k.R, 0.35];
    case 'listen':
      return [c.x, c.y, R * 1.2, 1];
    case 'end':
    case 'hand':
      return [L.moon.x, L.moon.y, R * 0.5, 1];
    default:
      return [c.x, c.y, R, 1];
  }
};
const paletteTarget = (mo: Mode): number[] =>
  mo === 'start' || mo === 'call'
    ? [1, 0, 0, 0]
    : mo === 'listen'
      ? [0, 0, 1, 0]
      : mo === 'end' || mo === 'hand'
        ? [0, 0, 0, 1]
        : [0, 1, 0, 0];

export class StageEngine {
  private els: Record<string, HTMLElement> = {};
  private input: StageInput = { ...defaultInput };
  private prev: Mode = 'start';
  private ms = -99;
  private t = 0;
  private t0 = performance.now();
  private lastT = 0;
  private raf = 0;
  private ro: ResizeObserver | null = null;
  private cache = new Map<string, string>();
  private reduced = false;
  private W = 0;
  private H = 0;
  private L: Layout = computeLayout(393, 851);
  private card: Rect = this.L.card;
  private sentences: string[] = [];
  private title = '';
  private pages: number[][] = [[]];
  private fs = FS_MIN;
  private pi = 0;
  private turnAt = -9;
  private tapAt = -9;
  private shownPage = -1;
  private kemiTalk = 0;
  private childTalk = 0;
  private peekEnv = 0;
  private nodEnv = 0;
  private callAt: number | null = null;
  private countAt: number | null = null;
  private litAt: number[] = [-9, -9, -9];
  private litSeen = 0;
  private seedAt: number[] = [];
  private seedsSeen = 0;
  private endAt: number | null = null;
  private con: number[][] = [];
  private cln: SVGElement[] = [];
  private cpt: SVGElement[] = [];
  private stopped = false;

  constructor(private root: HTMLElement) {
    root.querySelectorAll<HTMLElement>('[data-k]').forEach((el) => {
      this.els[el.dataset.k as string] = el;
    });
    this.reduced =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const measure = () => this.setSize(root.clientWidth || window.innerWidth, root.clientHeight || window.innerHeight);
    measure();
    if (typeof ResizeObserver !== 'undefined') {
      this.ro = new ResizeObserver(measure);
      this.ro.observe(root);
    }
    const fonts = (document as Document & { fonts?: { ready: Promise<unknown> } }).fonts;
    if (fonts?.ready) void fonts.ready.then(() => !this.stopped && this.relayout()).catch(() => undefined);
    if (typeof requestAnimationFrame === 'function') {
      const loop = () => {
        if (this.stopped) return;
        this.render();
        this.raf = requestAnimationFrame(loop);
      };
      this.raf = requestAnimationFrame(loop);
    } else {
      this.render();
    }
  }

  destroy() {
    this.stopped = true;
    if (this.raf && typeof cancelAnimationFrame === 'function') cancelAnimationFrame(this.raf);
    this.ro?.disconnect();
  }

  setInput(next: Partial<StageInput>) {
    const old = this.input;
    this.input = { ...old, ...next };
    this.now();
    const mode = this.input.mode;
    if (mode !== old.mode) {
      this.prev = old.mode;
      this.ms = this.t;
      if (mode === 'call') this.callAt = this.t;
      if (mode === 'start') this.callAt = null;
      if ((mode === 'end' || mode === 'hand') && this.endAt === null) this.endAt = this.t;
      if (mode !== 'count') this.countAt = null;
    }
    if (this.input.counting && this.countAt === null) this.countAt = this.t;
    if (!this.input.counting) this.countAt = null;
    for (let k = this.litSeen; k < this.input.questionsLit && k < 3; k++) this.litAt[k] = this.t;
    this.litSeen = this.input.questionsLit;
    for (let k = this.seedsSeen; k < this.input.seeds && k < 2; k++) this.seedAt[k] = this.t;
    this.seedsSeen = this.input.seeds;
    if (this.input.mode !== 'end' && this.input.mode !== 'hand') this.endAt = null;
    this.render();
  }

  setStory(title: string, sentences: string[]) {
    this.title = title;
    this.sentences = sentences;
    this.pi = 0;
    this.turnAt = -9;
    this.relayout();
  }

  /** The child taps the arrow: the next page. */
  turnPage() {
    if (this.pi >= this.pages.length - 1) return;
    this.now();
    this.tapAt = this.t;
    this.pi += 1;
    this.turnAt = this.t;
  }

  get pageCount() {
    return this.pages.length;
  }

  private now() {
    this.t = (performance.now() - this.t0) / 1000;
  }

  private $(k: string): HTMLElement {
    return this.els[k];
  }

  private set(el: HTMLElement | undefined, prop: 'opacity' | 'transform' | 'visibility', v: string) {
    if (!el) return;
    const key = (el.dataset.k ?? '') + '|' + prop;
    if (this.cache.get(key) === v) return;
    this.cache.set(key, v);
    el.style[prop] = v;
  }
  private op(k: string, v: number) {
    this.set(this.els[k], 'opacity', String(Math.round(clamp(v) * 1000) / 1000));
  }
  private tf(k: string, v: string) {
    this.set(this.els[k], 'transform', v);
  }
  private vis(k: string, on: boolean) {
    this.set(this.els[k], 'visibility', on ? 'visible' : 'hidden');
  }

  // ---------------- layout ----------------
  private setSize(w: number, h: number) {
    if (w === this.W && h === this.H) return;
    this.W = w;
    this.H = h;
    this.relayout();
  }

  private relayout() {
    if (!this.W || !this.H) return;
    const L = computeLayout(this.W, this.H);
    this.L = L;
    this.card = { ...L.card };
    this.cache.clear();
    const call = this.$('call');
    call.style.fontSize = L.callFs + 'px';
    call.style.width = L.w + 'px';
    [
      ['jpeek', L.peek.w],
      ['jnod', L.jw],
      ['jcheer', L.jw],
    ].forEach(([id, w]) => {
      const el = this.$(id as string);
      el.style.width = w + 'px';
      el.style.height = (w as number) * 0.734 + 'px';
    });
    const big = Math.max(L.w, L.h) * 0.9;
    this.root.querySelectorAll<HTMLElement>('.aur').forEach((a, i) => {
      a.style.width = a.style.height = big + 'px';
      a.style.left = (i % 2 ? L.w * 0.45 : -big * 0.3) + 'px';
      a.style.top = (i % 2 ? L.h * 0.25 : -big * 0.25) + 'px';
    });
    const voice = this.$('voice');
    voice.style.left = L.w / 2 + 'px';
    voice.style.top = L.h + 'px';
    voice.style.setProperty('--rise', L.h - L.center.y + 'px');
    voice.querySelectorAll<HTMLElement>('i').forEach((d) => {
      d.style.setProperty('--x', parseFloat(d.dataset.f ?? '0') * L.w * 0.42 + 'px');
    });
    this.paginate();
    this.buildConst();
    this.root.classList.toggle('tight', this.card.h < 560);
  }

  private paginate() {
    const L = this.L;
    const c = this.card;
    const mp = this.$('mpage');
    const mt = this.$('mtext');
    const mpt = this.$('mpt');
    const mph = this.$('mph');
    const pd = Math.round(clamp(L.m * 0.055, 18, 46));
    const tight = c.h < 560;
    const TITLE = (fs: number) => Math.round(fs * (tight ? 1 : 1.15));
    Object.assign(mp.style, { width: c.w + 'px', height: c.h + 'px', padding: `${pd}px ${pd}px 8px` });
    this.$('page').style.padding = `${pd}px ${pd}px 8px`;
    this.$('mtitle').textContent = this.title;
    const S = this.sentences;
    const N = S.length;
    this.root.classList.toggle('tight', tight);
    const fits = (idx: number[], fs: number, first: boolean) => {
      mph.style.display = first ? 'block' : 'none';
      this.$('mtitle').style.fontSize = TITLE(fs) + 'px';
      mpt.style.fontSize = fs + 'px';
      mt.textContent = idx.map((i) => S[i]).join(' ');
      return mpt.scrollHeight <= mpt.clientHeight + 1;
    };
    const pack = (fs: number): number[][] | null => {
      const pages: number[][] = [];
      let cur: number[] = [];
      for (let i = 0; i < N; i++) {
        const tryU = cur.concat(i);
        if (fits(tryU, fs, pages.length === 0)) cur = tryU;
        else {
          if (!cur.length) return null;
          pages.push(cur);
          cur = [i];
          if (!fits(cur, fs, pages.length === 0)) return null;
        }
      }
      if (cur.length) pages.push(cur);
      return pages;
    };
    let best: number[][] | null = null;
    let bestFs = FS_MIN;
    if (N === 0) {
      best = [[]];
    } else {
      for (let fs = FS_MAX; fs >= FS_MIN; fs--) {
        const p = pack(fs);
        if (!p) continue;
        if (!best || p.length < best.length || (p.length === best.length && fs > bestFs)) {
          best = p;
          bestFs = fs;
        }
      }
      if (best) {
        const minPages = best.length;
        for (let fs = FS_MAX; fs >= FS_MIN; fs--) {
          const p = pack(fs);
          if (p && p.length === minPages) {
            best = p;
            bestFs = fs;
            break;
          }
        }
      }
      if (!best) {
        for (let fs = FS_MIN - 1; fs >= FS_FLOOR; fs--) {
          const p = pack(fs);
          if (p) {
            best = p;
            bestFs = fs;
            break;
          }
        }
      }
      if (!best) {
        best = [S.map((_, i) => i)];
        bestFs = FS_FLOOR;
      }
      // balance: the same number of pages, the words spread as evenly as the screen allows
      const n = best.length;
      if (n > 1) {
        const W = S.map((s) => s.split(/\s+/).length);
        const wc = (i: number, j: number) => {
          let s = 0;
          for (let k = i; k < j; k++) s += W[k];
          return s;
        };
        const memo: Record<string, boolean> = {};
        const ok = (i: number, j: number, first: boolean) => {
          const key = `${i}-${j}-${first}`;
          if (!(key in memo)) memo[key] = fits(Array.from({ length: j - i }, (_, k) => i + k), bestFs, first);
          return memo[key];
        };
        const D = [...Array(n + 1)].map(() => Array(N + 1).fill(Infinity));
        const C = [...Array(n + 1)].map(() => Array(N + 1).fill(-1));
        D[0][0] = 0;
        for (let k = 1; k <= n; k++)
          for (let j = 1; j <= N; j++)
            for (let i = k - 1; i < j; i++) {
              if (D[k - 1][i] === Infinity || !ok(i, j, k === 1)) continue;
              const v = Math.max(D[k - 1][i], wc(i, j));
              if (v < D[k][j]) {
                D[k][j] = v;
                C[k][j] = i;
              }
            }
        if (D[n][N] < Infinity) {
          const out: number[][] = [];
          let j = N;
          for (let k = n; k >= 1; k--) {
            const i = C[k][j];
            out.unshift(Array.from({ length: j - i }, (_, q) => i + q));
            j = i;
          }
          best = out;
        }
      }
    }
    this.pages = best ?? [[]];
    this.fs = bestFs;
    const pg = this.$('page');
    // A one-page story gets a card only as tall as it needs (the artifact's rule).
    if (this.pages.length === 1 && N > 0) {
      const cur = this.$('mpage');
      this.$('mph').style.display = 'block';
      this.$('mtext').textContent = S.join(' ');
      this.$('mpt').style.fontSize = this.fs + 'px';
      cur.style.height = 'auto';
      this.$('mpt').style.flex = 'none';
      const need = cur.offsetHeight + 64;
      cur.style.height = c.h + 'px';
      this.$('mpt').style.flex = '';
      if (need > 64 + 1 && need < c.h) {
        const top = L.portrait ? (L.phone ? 78 : Math.max(72, this.H * 0.075)) : Math.max(56, this.H * 0.08);
        c.y = Math.max(top, (this.H - need) / 2);
        c.h = need;
        if (!L.portrait) {
          L.corner.y = c.y + 32;
          if (L.peek.y0 > this.H) L.peek.y1 = c.y + c.h - L.peek.w * 0.734;
        }
      }
    }
    pg.style.width = c.w + 'px';
    pg.style.height = c.h + 'px';
    Object.assign(this.$('mpage').style, { transform: `translate(${c.x}px,${c.y}px)` });
    this.$('pt').style.fontSize = this.fs + 'px';
    this.$('ptitle').style.fontSize = TITLE(this.fs) + 'px';
    this.$('pdots').innerHTML = this.pages.length > 1 ? this.pages.map(() => '<i></i>').join('') : '';
    this.shownPage = -1;
    this.pi = Math.min(this.pi, this.pages.length - 1);
  }

  private buildConst() {
    const svg = this.$('const');
    const NS = 'http://www.w3.org/2000/svg';
    const L = this.L;
    svg.innerHTML = '';
    svg.setAttribute('viewBox', `0 0 ${L.w} ${L.h}`);
    this.con = CBASE.map((p) => [L.con.x + (p[0] - 190) * L.con.s, L.con.y + (p[1] - 287) * L.con.s]);
    this.cln = [];
    this.cpt = [];
    CLINES.concat([[5, 8]]).forEach((ln, i) => {
      const e = document.createElementNS(NS, 'line');
      const A = this.con[ln[0]];
      const B = this.con[ln[1]];
      e.setAttribute('x1', String(A[0]));
      e.setAttribute('y1', String(A[1]));
      e.setAttribute('x2', String(B[0]));
      e.setAttribute('y2', String(B[1]));
      e.setAttribute('pathLength', '1');
      if (i === CLINES.length) e.classList.add('head');
      svg.appendChild(e);
      this.cln.push(e);
    });
    this.con.slice(0, 8).forEach((p) => {
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', String(p[0]));
      c.setAttribute('cy', String(p[1]));
      c.setAttribute('r', '2.2');
      svg.appendChild(c);
      this.cpt.push(c);
    });
  }

  private setPage(i: number) {
    this.shownPage = i;
    const p = this.pages[Math.min(i, this.pages.length - 1)] ?? [];
    this.$('ph').style.display = i === 0 ? 'block' : 'none';
    this.$('ptext').textContent = p.map((k) => this.sentences[k]).join(' ');
    [...this.$('pdots').children].forEach((d, k) => d.classList.toggle('on', k === i));
    this.$('next').style.visibility = i < this.pages.length - 1 ? 'visible' : 'hidden';
  }

  // ---------------- render ----------------
  private render() {
    if (!this.W) return;
    this.now();
    const t = this.t;
    const dt = Math.min(0.1, Math.max(0, t - this.lastT));
    this.lastT = t;
    const L = this.L;
    const I = this.input;
    const m = I.mode;
    const pm = this.prev;
    const u = this.reduced ? 1 : ease((t - this.ms) / BLEND);
    const V = (f: (mo: Mode) => number) => lerp(f(pm), f(m), u);
    const VA = (f: (mo: Mode) => number[]) => {
      const a = f(pm);
      const b = f(m);
      return a.map((x, i) => lerp(x, b[i], u));
    };
    const approach = (cur: number, target: number, tc: number) => cur + (target - cur) * (this.reduced ? 1 : Math.min(1, dt / tc));
    this.kemiTalk = approach(this.kemiTalk, I.speaking ? 1 : 0, I.speaking ? 0.15 : 0.25);
    this.childTalk = approach(this.childTalk, I.childSpeaking ? 1 : 0, I.childSpeaking ? 0.15 : 0.25);
    this.peekEnv = approach(this.peekEnv, I.peek ? 1 : 0, 0.3);
    this.nodEnv = approach(this.nodEnv, I.nod ? 1 : 0, 0.3);

    // sky + aurora + palette
    this.op('skyNight', V((mo) => (mo === 'start' || mo === 'call' ? 0 : 1)));
    this.op('skyDeep', V((mo) => (['listen', 'end', 'hand'].includes(mo) ? 1 : 0)));
    const P = VA(paletteTarget);
    const dimA = V((mo) => (mo === 'reading' || mo === 'reconnect' ? 0.35 : 1));
    this.op('aurCoral', P[0]);
    this.op('aurIndigo', P[1] * dimA);
    this.op('aurBlue', P[2]);
    this.op('aurGold', P[3]);
    ['coral', 'indigo', 'blue', 'gold'].forEach((c, i) => this.op('os-' + c, P[i]));
    this.op('stars1', V((mo) => (mo === 'end' || mo === 'hand' ? 1 : ['retell', 'questions', 'listen', 'think'].includes(mo) ? 0.3 : 0)));
    this.op('stars2', V((mo) => (mo === 'end' || mo === 'hand' ? 1 : 0)));
    this.op('rain', V((mo) => (mo === 'listen' ? 1 : 0)));

    // Auntie Kemi's light
    const o = VA((mo) => orbTarget(L, mo));
    this.tf('orb', `translate(${px(o[0])},${px(o[1])}) scale(${(o[2] / 64).toFixed(3)})`);
    this.op('orb', o[3]);
    const level = I.speaking && !this.reduced ? 0.4 + 0.6 * Math.abs(Math.sin(t * 10.7) * Math.sin(t * 4.3 + 1)) : 0;
    this.tf('orbLvl', `scale(${(1 + 0.14 * level).toFixed(3)})`);
    this.op('rings', this.kemiTalk);
    this.op('shim', V((mo) => (mo === 'think' ? 1 : 0)));
    this.op('outline', V((mo) => (mo === 'reconnect' ? 1 : 0)));

    // the child's voice
    const vs = V((mo) => (mo === 'reading' ? 1 : 0));
    this.op('voice', this.childTalk);
    this.tf('voice', `translateY(${px(vs * L.h * 0.42)})`);

    // the call
    const ci = this.callAt;
    const cv = ci !== null ? win(t, ci, ci + 0.9, ci + 1.9, ci + 2.6) : 0;
    this.op('call', cv);
    this.tf('call', `translate(${px(0)},${px(L.callY + (1 - cv) * 12)}) scale(${(0.94 + 0.06 * cv).toFixed(3)})`);

    // seeds
    for (let i = 0; i < 2; i++) {
      const el = this.$('g' + i);
      const a = this.seedAt[i];
      if (a === undefined) {
        this.op('g' + i, 0);
        continue;
      }
      const gw = i ? 70 : 58;
      const gh = i ? 54 : 58;
      const ang = t * 0.55 + i * Math.PI;
      const rad = L.R0 * 2.3;
      const x = L.center.x + Math.cos(ang) * rad;
      const y = L.center.y + Math.sin(ang) * rad * 0.45;
      const depth = 0.85 + 0.15 * Math.sin(ang);
      const s = depth * (L.R0 / 52);
      el.classList.toggle('drawn', t >= a);
      this.tf('g' + i, `translate(${px(x - gw / 2)},${px(y - gh / 2)}) scale(${s.toFixed(3)})`);
      this.op('g' + i, clamp((t - a) * 2) * (0.7 + 0.3 * depth) * V((mo) => (mo === 'seeds' || mo === 'count' ? 1 : 0)));
    }

    // count lights + question points
    const cvis = V((mo) => (mo === 'count' ? 1 : 0));
    for (let k = 0; k < 5; k++) {
      const el = this.$('c' + k);
      const a = ((50 + k * 20) * Math.PI) / 180;
      const c0 = this.countAt !== null ? this.countAt + 0.4 + k * 0.75 : null;
      this.op('c' + k, cvis);
      el.classList.toggle('lit', c0 !== null && t >= c0);
      const pop = c0 !== null ? 1 + 0.5 * pulse(t, c0, 0.4) : 1;
      this.tf('c' + k, `translate(${px(L.center.x + Math.cos(a) * L.R0 * 1.9 - 6)},${px(L.center.y + Math.sin(a) * L.R0 * 1.9 - 6)}) scale(${pop.toFixed(3)})`);
    }
    const qvis = V((mo) => (mo === 'questions' ? 1 : 0));
    for (let k = 0; k < 3; k++) {
      const el = this.$('q' + k);
      const a = ((65 + k * 25) * Math.PI) / 180;
      const lit = k < I.questionsLit;
      el.classList.toggle('lit', lit);
      const s = lit ? 1 + 0.5 * pulse(t, this.litAt[k], 0.45) : 1;
      this.op('q' + k, qvis);
      this.tf('q' + k, `translate(${px(L.center.x + Math.cos(a) * L.R0 * 1.9 - 6)},${px(L.center.y + Math.sin(a) * L.R0 * 1.9 - 6)}) scale(${s.toFixed(3)})`);
    }

    // the page
    const c = this.card;
    const pv = V((mo) => (mo === 'reading' || (mo === 'reconnect' && I.pageVisible) ? 1 : 0));
    const inPage = m === 'reading' || (m === 'reconnect' && I.pageVisible);
    const pOp = pv * V((mo) => (mo === 'reconnect' ? 0.5 : 1));
    this.op('page', pOp);
    this.vis('page', pOp > 0.02);
    this.$('page').classList.toggle('live', pOp > 0.5);
    this.tf('page', `translate(${px(c.x)},${px(c.y + (inPage ? (1 - pv) * 30 : -(1 - pv) * 40))}) scale(${(inPage ? lerp(0.97, 1, pv) : 1 - 0.03 * (1 - pv)).toFixed(3)})`);
    const half = this.reduced ? 0.001 : 0.22;
    const dtp = t - this.turnAt;
    let showIdx = this.pi;
    let pu = 1;
    let dir = 0;
    if (dtp < half) {
      showIdx = Math.max(0, this.pi - 1);
      pu = 1 - dtp / half;
      dir = -1;
    } else if (dtp < 2 * half) {
      pu = (dtp - half) / half;
      dir = 1;
    }
    if (showIdx !== this.shownPage) this.setPage(showIdx);
    this.op('ptext', pu);
    this.tf('ptext', `translateX(${px(dir === -1 ? -(1 - pu) * 28 : dir === 1 ? (1 - pu) * 28 : 0)})`);
    const tapAge = t - this.tapAt;
    this.op('nrip', tapAge < 0.5 ? 1 - tapAge / 0.5 : 0);
    this.tf('nrip', `scale(${(tapAge < 0.5 ? 1 + tapAge * 1.4 : 1).toFixed(3)})`);

    // Japa
    const J = L.peek;
    const pk = Math.max(V((mo) => (mo === 'reconnect' ? 1 : 0)), ease(this.peekEnv));
    this.op('jpeek', pk);
    this.tf('jpeek', `translate(${px(lerp(J.x0, J.x1, pk))},${px(lerp(J.y0, J.y1, pk))}) rotate(${(-8 * pk).toFixed(1)}deg)`);
    const nd = ease(this.nodEnv);
    const nodRot = this.reduced ? 0 : nd * 6 * Math.sin(t * 7);
    this.op('jnod', nd);
    this.tf('jnod', `translate(${px(L.bottom.x)},${px(L.bottom.y + (1 - nd) * 40)}) rotate(${nodRot.toFixed(1)}deg)`);
    const ce = V((mo) => (mo === 'end' ? 1 : 0));
    this.op('jcheer', ce);
    this.tf('jcheer', `translate(${px(L.cheer.x)},${px(L.cheer.y + (1 - ce) * 60 - (ce > 0.9 && !this.reduced ? Math.abs(Math.sin(t * 3.5)) * 6 : 0))})`);

    // constellation + the child's star
    const es = this.endAt ?? 1e9;
    const st = this.endAt !== null ? this.endAt + 4.8 : 1e9;
    this.cln.forEach((e, i) => e.classList.toggle('on', i < CLINES.length ? t >= es + 1.2 + i * 0.3 : t >= st + 1.8));
    this.cpt.forEach((e, i) => e.classList.toggle('on', t >= es + 0.6 + i * 0.12));
    this.op('const', V((mo) => (mo === 'end' ? 1 : mo === 'hand' ? 0.2 : 0)));
    if (t >= st && this.con.length) {
      const uu = ease(clamp((t - st) / 1.8));
      const E = this.con[8];
      const x = lerp(L.w / 2, E[0], uu);
      const y = lerp(L.cheer.y, E[1], uu) - Math.sin(Math.PI * uu) * L.h * 0.12;
      this.op('gstar', 1);
      this.tf('gstar', `translate(${px(x)},${px(y)}) scale(${(0.6 + 0.5 * uu).toFixed(3)})`);
    } else this.op('gstar', 0);

    // start + hand-back overlays
    const sv = I.showStart ? V((mo) => (mo === 'start' ? 1 : 0)) : 0;
    this.op('startov', sv);
    this.vis('startov', sv > 0.02);
    this.$('startov').classList.toggle('live', sv > 0.5);
    const hv = V((mo) => (mo === 'hand' ? 1 : 0));
    this.op('handov', hv);
    this.vis('handov', hv > 0.02);
    this.$('handov').classList.toggle('live', hv > 0.5);
    this.op('vig', V((mo) => (mo === 'reading' || mo === 'reconnect' ? 0.25 : 1)));
  }
}
