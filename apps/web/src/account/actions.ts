import { dataMode, liveApi } from '../api';
import { addConsent, createChild, loadAccount, patchChild } from './remote';
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

export interface ChildEditInput {
  firstName: string;
  primaryClass: number;
  birthYear: number;
}

/** Saves a changed name, class or birth year. Consent is not touched. */
export async function editChild(childId: string, input: ChildEditInput): Promise<void> {
  if (dataMode !== 'live') {
    accountStore.updateChild(childId, input);
    return;
  }
  accountStore.replaceChild(await patchChild(liveApi(), childId, input));
}

/** Saves a changed "recordings may help Alo.ai learn" choice. In a live build consent is
 *  append-only, so this is a new consent record; the caller has the guardian tick that they
 *  are the child's parent or guardian first. */
export async function changeTrainingOptIn(childId: string, trainingOptIn: boolean): Promise<void> {
  if (dataMode !== 'live') {
    accountStore.setTrainingOptIn(childId, trainingOptIn);
    return;
  }
  accountStore.adoptServerConsent(await addConsent(liveApi(), childId, trainingOptIn));
}
