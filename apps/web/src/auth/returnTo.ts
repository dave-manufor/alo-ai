// Where to go after sign-in. Entra sends the browser away and back to /signin, so the screen
// the guardian was on (a report link, a screen open when the sign-in expired) is kept in this
// tab's session storage and used once they are back. It is a path in this app, never a full
// address, and it expires quickly so an old one cannot send a later sign-in somewhere odd.

const KEY = 'alo.returnTo';
const LIFETIME_MS = 15 * 60 * 1000;

function store(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function saveReturnTo(path: string, now = Date.now()): void {
  if (!path.startsWith('/') || path.startsWith('//') || path.startsWith('/signin')) return;
  try {
    store()?.setItem(KEY, JSON.stringify({ path, at: now }));
  } catch {
    // Private mode: the guardian just lands on Home.
  }
}

/** The saved path if there is a fresh one. It stays until the sign-in ends (clearReturnTo), so a
 *  re-render cannot lose it. */
export function peekReturnTo(now = Date.now()): string | null {
  try {
    const raw = store()?.getItem(KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as { path?: unknown; at?: unknown };
    if (typeof saved.path !== 'string' || typeof saved.at !== 'number') return null;
    if (now - saved.at > LIFETIME_MS) return null;
    if (!saved.path.startsWith('/') || saved.path.startsWith('//')) return null;
    return saved.path;
  } catch {
    return null;
  }
}

export function clearReturnTo(): void {
  try {
    store()?.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}
