// Local shortcuts stay local (root AGENTS.md rule 8): only an explicit
// `VITE_ALO_ENV=local` talks to the Firebase/emulator stack. The default
// is non-local, so a production build that forgets the variable can never
// mistake itself for a local one. The browser never chooses VOICE_MODE or
// SESSION_PROFILE — those are server settings (Terraform).
export const aloEnv = import.meta.env.VITE_ALO_ENV ?? 'cloud';
export const isLocal = aloEnv === 'local';
