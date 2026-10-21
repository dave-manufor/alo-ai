import NavButton from '../design-system/NavButton';

// Grown-up mode placeholder for Paystack checkout (PRD 11.1). The real
// checkout opens Paystack's inline popup from a transaction the Account
// and Payments service initializes on the server; amounts and plan codes
// are never set in the browser. That lands with feat/payments-paystack-checkout.
export default function CheckoutPlaceholderPage() {
  return (
    <main className="app-main">
      <section className="card">
        <h1 className="title">Get the weekly reading plan</h1>
        <p className="body">
          The plan gives your child a short activity each day, new stories
          every week, and a new reading check to see how things are growing.
        </p>
        <p className="body muted">
          Payment is handled by Paystack. Checkout opens here as soon as the
          payments service is connected.
        </p>
        <NavButton variant="secondary" size="grown" to="/reports">
          Back to reports
        </NavButton>
      </section>
    </main>
  );
}
