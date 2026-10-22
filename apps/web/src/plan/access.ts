import { accountStore } from '../account/store';
import { dataMode } from '../api';

/** Whether this guardian sees the weekly plan.
 *
 *  A live build opens it to every signed-in guardian: payments are later work (PRD changelog,
 *  2026-10-22), so the mini-study gives the plan to everyone with a consented child, and the
 *  Account API serves it without a subscription check. The sample build keeps the demo
 *  paywall so the upgrade screens can still be walked. When payments land, this one function
 *  is where the live rule changes. */
export function planUnlocked(signedIn: boolean): boolean {
  return signedIn && (dataMode === 'live' || accountStore.hasActiveSubscription());
}
