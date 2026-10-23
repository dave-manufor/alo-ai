import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { payForPlan, syncAccount, syncSubscription } from '../account/actions';
import { accountStore } from '../account/store';
import { ApiError, plainMessage } from '../api/client';
import CheckoutPage from '../pages/CheckoutPage';
import { planUnlocked } from './access';

// A live build with the Account API and Paystack's popup faked: no network, no real payment.
const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn() }));
vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { dataMode: 'live', liveApi: () => api, ApiError: actual.ApiError };
});

const start = {
  schema_version: 1,
  reference: 'pay_1',
  access_code: 'code_pay_1',
  authorization_url: 'https://checkout.paystack.com/code_pay_1',
};
const status = (active: boolean, plans_need_subscription = true) => ({
  schema_version: 1,
  active,
  plans_need_subscription,
  current_period_end: active ? '2026-11-23T12:00:00Z' : null,
});

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  api.patch.mockReset();
  accountStore.resetForTests();
  accountStore.signInVerified({ id: 'g1', email: 'e@example.com', method: 'google' });
});

describe('live build: the subscription', () => {
  it('syncs the subscription and the paywall setting with the account', async () => {
    api.get.mockImplementation(async (path: string) =>
      path === '/v1/children' ? { children: [] } : status(false),
    );
    await syncAccount();
    expect(api.get).toHaveBeenCalledWith('/v1/subscription');
    expect(accountStore.getState().plansNeedSubscription).toBe(true);
    expect(planUnlocked(true)).toBe(false);
  });

  it('keeps the last answer when the subscription cannot be loaded', async () => {
    accountStore.replaceSubscription(status(true));
    api.get.mockRejectedValue(new ApiError(503, 'X', true, 'later'));
    await syncSubscription();
    expect(accountStore.hasActiveSubscription()).toBe(true);
  });

  it('opens the plan with the paywall off, or with a confirmed subscription', () => {
    expect(planUnlocked(true)).toBe(true); // the study: paywall off by default
    accountStore.replaceSubscription(status(false));
    expect(planUnlocked(true)).toBe(false);
    accountStore.replaceSubscription(status(true));
    expect(planUnlocked(true)).toBe(true);
    expect(planUnlocked(false)).toBe(false);
  });
});

describe('live build: paying', () => {
  it('starts on the server, pays in the popup, then confirms on the server', async () => {
    api.post.mockImplementation(async (path: string) =>
      path === '/v1/checkout' ? start : status(true),
    );
    const popup = vi.fn().mockResolvedValue('success');
    expect(await payForPlan(popup)).toBe('paid');
    expect(popup).toHaveBeenCalledWith('code_pay_1');
    expect(api.post).toHaveBeenNthCalledWith(1, '/v1/checkout', {});
    expect(api.post).toHaveBeenNthCalledWith(2, '/v1/checkout/pay_1/confirm', {});
    expect(accountStore.hasActiveSubscription()).toBe(true);
  });

  it('asks nothing more when the guardian closes the popup', async () => {
    api.post.mockResolvedValue(start);
    expect(await payForPlan(vi.fn().mockResolvedValue('cancelled'))).toBe('cancelled');
    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it('is pending when Paystack has not confirmed the payment yet', async () => {
    api.post.mockImplementation(async (path: string) =>
      path === '/v1/checkout' ? start : status(false),
    );
    expect(await payForPlan(vi.fn().mockResolvedValue('success'))).toBe('pending');
  });

  it('has plain words for the payment errors', () => {
    expect(plainMessage(402, 'PAYMENT_REQUIRED')).toMatch(/comes with the subscription/);
    expect(plainMessage(503, 'PAYMENTS_UNAVAILABLE')).toMatch(/not open just now/);
    expect(plainMessage(409, 'ALREADY_SUBSCRIBED')).toMatch(/already have/);
  });
});

function renderCheckout(popup: (code: string) => Promise<'success' | 'cancelled'>) {
  render(
    <MemoryRouter initialEntries={['/plan/checkout']}>
      <Routes>
        <Route path="/plan/checkout" element={<CheckoutPage popup={popup} />} />
        <Route path="/plan" element={<p>The plan</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('live build: the checkout screen', () => {
  it('goes to the plan once the server confirms the payment, and says it is test mode', async () => {
    api.post.mockImplementation(async (path: string) =>
      path === '/v1/checkout' ? start : status(true),
    );
    renderCheckout(async () => 'success');
    expect(screen.getByText(/Test mode: no real money is taken/)).toBeInTheDocument();
    expect(screen.getByText(/Paystack never receives anything about/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Pay with Paystack' }));
    expect(await screen.findByText('The plan')).toBeInTheDocument();
  });

  it('says nothing was charged when the popup is closed', async () => {
    api.post.mockResolvedValue(start);
    renderCheckout(async () => 'cancelled');
    fireEvent.click(screen.getByRole('button', { name: 'Pay with Paystack' }));
    expect(await screen.findByText(/Nothing was charged/)).toBeInTheDocument();
  });

  it('shows the plain message when payment cannot start', async () => {
    api.post.mockRejectedValue(
      new ApiError(503, 'PAYMENTS_UNAVAILABLE', true, plainMessage(503, 'PAYMENTS_UNAVAILABLE')),
    );
    renderCheckout(async () => 'success');
    fireEvent.click(screen.getByRole('button', { name: 'Pay with Paystack' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/not open just now/);
  });

  it('can check again while Paystack is confirming', async () => {
    api.post.mockImplementation(async (path: string) =>
      path === '/v1/checkout' ? start : status(false),
    );
    renderCheckout(async () => 'success');
    fireEvent.click(screen.getByRole('button', { name: 'Pay with Paystack' }));
    expect(await screen.findByText(/still confirming/)).toBeInTheDocument();
    api.get.mockResolvedValue(status(true));
    fireEvent.click(screen.getByRole('button', { name: 'Check again' }));
    await waitFor(() => expect(screen.getByText('The plan')).toBeInTheDocument());
  });
});
