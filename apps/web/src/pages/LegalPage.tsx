import { useNavigate } from 'react-router-dom';
import Icon from '../ui/Icon';

// Plain-words terms and privacy notice, linked from sign-in, consent and the account. These
// summarise what the product does (PRD 12); they are not final legal text and need review
// before a pilot.
export default function LegalPage({ kind }: { kind: 'privacy' | 'terms' }) {
  const navigate = useNavigate();
  return (
    <div className="page page--mid">
      {/* Back to wherever the reader came from; the start page when there is nowhere to go. */}
      <button
        type="button"
        className="ui-back ui-back--button"
        onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/'))}
      >
        <Icon name="back" size={20} />
        Back
      </button>
      {kind === 'privacy' ? <Privacy /> : <Terms />}
    </div>
  );
}

function Privacy() {
  return (
    <div className="legal">
      <h1 className="display-m">Privacy notice</h1>
      <p className="body">
        Alo.ai is a reading screener for children in Primary 1 to 6. This is what we do with your family&apos;s
        information.
      </p>
      <h2 className="title">What we keep</h2>
      <p className="body">
        Your email address, your child&apos;s first name, class and birth year, and the reading reports made from their
        checks.
      </p>
      <h2 className="title">Recordings</h2>
      <p className="body">
        We record your child&apos;s voice while they read and answer, only after you agree for that child. Recordings are
        deleted after 90 days. We use them to improve Alo.ai only if you say yes, and you can change that in your
        account.
      </p>
      <h2 className="title">Where it lives</h2>
      <p className="body">Everything is stored in the European Union. Only you can see your child&apos;s reports.</p>
      <h2 className="title">Payments</h2>
      <p className="body">Paystack takes card payments on its own page. It never receives anything about your child.</p>
      <h2 className="title">Your choices</h2>
      <p className="body">You can ask for your child&apos;s data to be deleted.</p>
    </div>
  );
}

function Terms() {
  return (
    <div className="legal">
      <h1 className="display-m">Terms of use</h1>
      <p className="body">By using Alo.ai you agree to these plain-words terms.</p>
      <h2 className="title">What Alo.ai is</h2>
      <p className="body">
        Alo.ai is a screening tool. It shows you how your child reads today and suggests what to practise next. It is
        not a test that anyone passes or fails.
      </p>
      <h2 className="title">Who can use it</h2>
      <p className="body">
        Parents and guardians, for their own children. You must be the child&apos;s parent or guardian.
      </p>
      <h2 className="title">Plans and payment</h2>
      <p className="body">
        Some features need a paid plan. Prices are shown before you pay, and you pay on Paystack&apos;s secure page.
      </p>
    </div>
  );
}
