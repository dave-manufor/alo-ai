import { Notice, BackLink, Card } from '../ui/primitives';

// Placeholder for Paystack checkout (PRD 11.1). The real checkout opens Paystack's inline
// popup from a transaction the Account and Payments service initializes on the server;
// amounts and plan codes are never set in the browser. That lands with
// feat/payments-paystack-checkout.
export default function CheckoutPlaceholderPage() {
  return (
    <div className="page page--mid">
      <BackLink to="/upgrade" />
      <Card>
        <h1 className="title">Payment is almost ready</h1>
        <p className="body">
          Your payment opens on Paystack&apos;s secure page, as soon as the payments service is connected. Nothing
          has been charged.
        </p>
        <Notice tone="sky" role="note">
          Payment is handled by Paystack. Paystack never receives anything about your child.
        </Notice>
      </Card>
    </div>
  );
}
