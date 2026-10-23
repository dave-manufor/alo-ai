import { dataMode, liveApi } from '../api';
import { openPaystackPopup, type OpenPopup } from '../plan/paystackPopup';
import {
  addConsent,
  confirmCheckout,
  createChild,
  loadAccount,
  loadSubscription,
  patchChild,
  startCheckout,
} from './remote';
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
  await syncSubscription();
}

/** The subscription and the paywall setting. A failure leaves the last known answer: the plan
 *  route itself still refuses (402) a plan that needs a subscription. */
export async function syncSubscription(): Promise<void> {
  if (dataMode !== 'live') return;
  try {
    accountStore.replaceSubscription(await loadSubscription(liveApi()));
  } catch {
    // Kept as it was; the guardian can try again from the plan or payment screen.
  }
}

export type PaymentOutcome = 'paid' | 'pending' | 'cancelled';

/** Sample-build stand-in for Paystack's popup: nothing is charged, the plan unlocks locally. */
const samplePopup: OpenPopup = async () => 'success';

/** Pays for the weekly plan. Live: the Account service starts the transaction, Paystack's
 *  popup takes the card, then the server confirms with Paystack before the plan opens
 *  ('pending' means the popup said paid but Paystack has not confirmed it yet — the webhook
 *  will). Fixture: the same screen, with a simulated popup and a local sample entitlement
 *  (PRD 11.1: amounts and the plan are never set in the browser either way). */
export async function payForPlan(popup?: OpenPopup): Promise<PaymentOutcome> {
  if (dataMode !== 'live') {
    if ((await (popup ?? samplePopup)('fixture')) === 'cancelled') return 'cancelled';
    accountStore.activateSampleSubscription();
    return accountStore.hasActiveSubscription() ? 'paid' : 'pending';
  }
  const api = liveApi();
  const started = await startCheckout(api);
  if ((await (popup ?? openPaystackPopup)(started.access_code)) === 'cancelled') return 'cancelled';
  const status = await confirmCheckout(api, started.reference);
  accountStore.replaceSubscription(status);
  return status.active ? 'paid' : 'pending';
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
