import { dataMode, liveApi } from '../api';
import { createChild, loadAccount } from './remote';
import { accountStore } from './store';

// What screens call. The build picks the path (D6): the live build goes
// through the Account API; the fixture build keeps the in-memory/local
// store and makes no network call.

export interface NewChildInput {
  firstName: string;
  primaryClass: number;
  birthYear: number;
  attested: boolean;
  trainingOptIn: boolean;
}

/** After sign-in: fetch this guardian's children and consents (live build only). */
export async function syncAccount(): Promise<void> {
  if (dataMode !== 'live') return;
  const { children, consents } = await loadAccount(liveApi());
  accountStore.replaceFromServer(children, consents);
}

export async function addChild(input: NewChildInput): Promise<void> {
  if (dataMode !== 'live') {
    accountStore.addChildWithConsent(input);
    return;
  }
  if (!input.attested) throw new Error('Consent is needed before adding a child.');
  const { child, consent } = await createChild(liveApi(), input);
  accountStore.adoptServerChild(child, consent);
}
