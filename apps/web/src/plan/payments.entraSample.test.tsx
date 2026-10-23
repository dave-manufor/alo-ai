import { describe, expect, it, vi } from 'vitest';
import { payForPlan } from '../account/actions';
import { accountStore } from '../account/store';
import { dataMode } from '../api';

// A build with Entra sign-in but no API address (or a local run with Entra) is still a sample
// build for data: there is no Account API to confirm a payment, so the sample payment must
// unlock the plan rather than wait on a Paystack confirmation that never comes.
vi.mock('../auth', () => ({
  authMode: 'entra',
  auth: vi.fn(),
  signInFailed: vi.fn(() => false),
}));

describe('sample payment with Entra sign-in and no Account API', () => {
  it('unlocks the plan', async () => {
    expect(dataMode).toBe('fixture');
    accountStore.resetForTests();
    accountStore.signInVerified({ id: 'g1', email: 'e@example.com', method: 'email_link' });
    expect(await payForPlan(vi.fn().mockResolvedValue('success'))).toBe('paid');
    expect(accountStore.hasActiveSubscription()).toBe(true);
  });
});
