// Local shortcuts stay local (root AGENTS.md rule 8): `VITE_ALO_ENV=local`
// talks to the Firebase/emulator stack. The browser never chooses
// VOICE_MODE or SESSION_PROFILE — those are server settings (Terraform).
export const aloEnv = import.meta.env.VITE_ALO_ENV ?? 'local';
export const isLocal = aloEnv === 'local';
