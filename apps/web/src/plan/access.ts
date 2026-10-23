import { accountStore } from '../account/store';
import { dataMode } from '../api';

/** Whether this guardian sees the weekly plan.
 *
 *  A live build follows the Account service: with its PLANS_NEED_SUBSCRIPTION setting off (the
 *  mini-study) every signed-in guardian sees the plan; on (the demo), only a guardian whose
 *  Paystack payment the server has confirmed. The server's plan route enforces the same rule
 *  (402), so this only decides what the screen offers. The sample build keeps the demo paywall
 *  so the upgrade screens can still be walked. */
export function planUnlocked(signedIn: boolean): boolean {
  if (!signedIn) return false;
  if (dataMode === 'live') {
    return !accountStore.getState().plansNeedSubscription || accountStore.hasActiveSubscription();
  }
  return accountStore.hasActiveSubscription();
}
