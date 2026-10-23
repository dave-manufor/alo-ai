import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { payForPlan, syncSubscription } from '../account/actions';
import { accountStore } from '../account/store';
import { ApiError } from '../api';
import { Button } from '../design-system/alo';
import { PLAN_PRICE, PLAN_PRICE_PERIOD } from '../plan/price';
import type { OpenPopup } from '../plan/paystackPopup';
import { useActiveChild } from '../shell/activeChildContext';
import { BackLink, Card, Notice } from '../ui/primitives';

// Paystack checkout in the live build (PRD 11.1). The Account service starts the transaction
// and sets the plan and amount; Paystack's own popup takes the card; the server then confirms
// the payment with Paystack before the plan opens. Nothing about the child goes to Paystack.
type Step = 'ready' | 'working' | 'cancelled' | 'pending' | 'error';

export default function CheckoutPage({ popup }: { popup?: OpenPopup }) {
  const navigate = useNavigate();
  const { child } = useActiveChild();
  const name = child?.first_name ?? 'your child';
  const [step, setStep] = useState<Step>('ready');
  const [problem, setProblem] = useState('');

  async function pay() {
    setStep('working');
    try {
      const outcome = await payForPlan(popup);
      if (outcome === 'paid') {
        navigate('/plan', { replace: true });
        return;
      }
      setStep(outcome);
    } catch (error) {
      setProblem(
        error instanceof ApiError ? error.plain : 'The payment page could not open. Please try again.',
      );
      setStep('error');
    }
  }

  async function checkAgain() {
    setStep('working');
    await syncSubscription();
    if (accountStore.hasActiveSubscription()) {
      navigate('/plan', { replace: true });
      return;
    }
    setStep('pending');
  }

  return (
    <div className="page page--mid">
      <BackLink to="/upgrade" />
      <Card>
        <h1 className="title">Pay for {name}&apos;s weekly plan</h1>
        <p className="body">
          {PLAN_PRICE} {PLAN_PRICE_PERIOD}, by card on Paystack&apos;s secure page. It renews each month.
        </p>
        <p className="caption muted">Test mode: no real money is taken.</p>
        {step === 'cancelled' ? (
          <Notice tone="sky" role="status">
            The payment was not finished. Nothing was charged.
          </Notice>
        ) : null}
        {step === 'pending' ? (
          <Notice tone="sky" role="status">
            Paystack is still confirming your payment. The plan opens as soon as it is confirmed.
          </Notice>
        ) : null}
        {step === 'error' ? (
          <Notice tone="plain" role="alert">
            {problem}
          </Notice>
        ) : null}
        {step === 'pending' ? (
          <Button variant="primary" size="grown" onClick={checkAgain}>
            Check again
          </Button>
        ) : (
          <Button variant="primary" size="grown" onClick={pay} disabled={step === 'working'}>
            {step === 'working' ? 'Opening Paystack…' : 'Pay with Paystack'}
          </Button>
        )}
        <Notice tone="sky" role="note">
          Payment is handled by Paystack. Paystack never receives anything about {name}.
        </Notice>
      </Card>
    </div>
  );
}
