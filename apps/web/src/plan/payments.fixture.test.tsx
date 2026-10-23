import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { payForPlan } from '../account/actions';
import { accountStore } from '../account/store';
import CheckoutPage from '../pages/CheckoutPage';

// Fixture build (the default when no Entra / API URL is baked in): the same
// checkout screen, with a sample payment that never calls the Account API or
// Paystack. The live path is covered in payments.test.tsx.

beforeEach(() => {
  accountStore.resetForTests();
  accountStore.signInVerified({ id: 'g1', email: 'e@example.com', method: 'email_link' });
});

describe('sample build: paying', () => {
  it('unlocks the plan locally after the sample popup, and never talks to the API', async () => {
    const popup = vi.fn().mockResolvedValue('success');
    expect(await payForPlan(popup)).toBe('paid');
    expect(popup).toHaveBeenCalledWith('fixture');
    expect(accountStore.hasActiveSubscription()).toBe(true);
  });

  it('asks nothing more when the sample popup is closed', async () => {
    expect(await payForPlan(vi.fn().mockResolvedValue('cancelled'))).toBe('cancelled');
    expect(accountStore.hasActiveSubscription()).toBe(false);
  });
});

describe('sample build: the checkout screen', () => {
  it('says it is a sample payment, then opens the plan', async () => {
    render(
      <MemoryRouter initialEntries={['/plan/checkout']}>
        <Routes>
          <Route path="/plan/checkout" element={<CheckoutPage />} />
          <Route path="/plan" element={<p>The plan</p>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(/Sample build: the payment is simulated/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Continue with sample payment' }));
    expect(await screen.findByText('The plan')).toBeInTheDocument();
    expect(accountStore.hasActiveSubscription()).toBe(true);
  });
});
