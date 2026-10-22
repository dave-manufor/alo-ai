import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { accountStore, useAccount, type ChildProfile } from '../account/store';
import { dataMode } from '../api';
import { auth, authMode } from '../auth';
import { Button } from '../design-system/alo';
import NavButton from '../design-system/NavButton';
import { PLAN_PRICE, PLAN_PRICE_PERIOD } from '../plan/price';
import { Avatar, Card, Notice, SectionLabel, Switch } from '../ui/primitives';

// Account and privacy (wireframe 22): the children, the choices about their recordings, the
// plan, and sign out. Changing or deleting a child needs Account API calls that do not exist
// yet, so in the live build those controls say so instead of pretending to save.
export default function AccountPage() {
  const navigate = useNavigate();
  const { guardian, children } = useAccount();
  const subscribed = accountStore.hasActiveSubscription();
  const canChange = dataMode !== 'live';
  const [signingOut, setSigningOut] = useState(false);

  async function signOut() {
    setSigningOut(true);
    accountStore.signOut();
    if (authMode === 'entra') {
      try {
        await (await auth()).signOut();
      } catch {
        // Already signed out on this phone; nothing more to end.
      }
    }
    navigate('/');
  }

  return (
    <div className="page page--mid">
      <h1 className="display-m">Account</h1>

      <section className="step" aria-labelledby="children-heading">
        <SectionLabel id="children-heading">Children</SectionLabel>
        {children.map((child) => (
          <Card key={child.child_id}>
            <div className="account-row">
              <div className="child-card__head">
                <Avatar name={child.first_name} />
                <span className="account-row__text">
                  <span className="body card-title">{child.first_name}</span>
                  <span className="caption muted">
                    Primary {child.primary_class} · born {child.birth_year}
                  </span>
                </span>
              </div>
              {canChange ? (
                <Link to={`/children/${child.child_id}/edit`} className="body card-title ui-tap" aria-label={`Edit ${child.first_name}`}>
                  Edit
                </Link>
              ) : null}
            </div>
          </Card>
        ))}
        <NavButton variant="ghost" size="grown" to="/children/new" style={{ alignSelf: 'flex-start' }}>
          Add another child
        </NavButton>
      </section>

      <section className="step" aria-labelledby="privacy-heading">
        <SectionLabel id="privacy-heading">Privacy</SectionLabel>
        {!canChange ? (
          <Notice tone="sky" role="note">
            Changing these choices and deleting a child&apos;s data from here is coming soon.
          </Notice>
        ) : null}
        {children.map((child) => (
          <ChildPrivacy key={child.child_id} child={child} canChange={canChange} showName={children.length > 1} />
        ))}
      </section>

      <section className="step" aria-labelledby="plan-heading">
        <SectionLabel id="plan-heading">Subscription</SectionLabel>
        <Card>
          <div className="account-row">
            <span className="account-row__text">
              <span className="body card-title">{subscribed ? 'Weekly plan' : 'No plan yet'}</span>
              <span className="caption muted">
                {subscribed ? `${PLAN_PRICE} ${PLAN_PRICE_PERIOD} · paid by card` : 'One tip per check is free.'}
              </span>
            </span>
            <Link to={subscribed ? '/plan' : '/upgrade'} className="body card-title ui-tap">
              {subscribed ? 'Open' : 'See the plan'}
            </Link>
          </div>
        </Card>
      </section>

      <section className="step" aria-labelledby="signed-heading">
        <SectionLabel id="signed-heading">Signed in</SectionLabel>
        <Card>
          <div className="account-row">
            <span className="body account-row__text">{guardian?.email}</span>
            <Button variant="secondary" size="grown" disabled={signingOut} onClick={signOut}>
              Sign out
            </Button>
          </div>
        </Card>
        <p className="caption muted">
          <Link to="/terms">Terms</Link> · <Link to="/privacy">Privacy notice</Link>
        </p>
      </section>
    </div>
  );
}

function ChildPrivacy({ child, canChange, showName }: { child: ChildProfile; canChange: boolean; showName: boolean }) {
  const navigate = useNavigate();
  const consent = accountStore.consentFor(child.child_id);
  const [confirming, setConfirming] = useState(false);
  const optIn = consent?.training_opt_in ?? false;

  function remove() {
    accountStore.removeChild(child.child_id);
    if (accountStore.getState().children.length === 0) navigate('/onboarding/consent');
  }

  return (
    <Card>
      {showName ? <p className="body card-title">{child.first_name}</p> : null}
      <Switch
        title="Use recordings to improve Alo.ai"
        hint={`${optIn ? 'On' : 'Off'}. Recordings are deleted after 90 days.`}
        checked={optIn}
        onChange={(next) => accountStore.setTrainingOptIn(child.child_id, next)}
        disabled={!canChange}
      />
      {canChange ? (
        <>
          <div className="ui-divider" />
          {confirming ? (
            <div className="confirm" role="alertdialog" aria-labelledby={`del-${child.child_id}`}>
              <p id={`del-${child.child_id}`} className="body card-title">
                Delete {child.first_name}&apos;s data?
              </p>
              <p className="body">
                This removes {child.first_name}&apos;s recordings, reports and plans. It cannot be undone.
              </p>
              <div className="ui-actions">
                <Button variant="secondary" size="grown" onClick={remove}>
                  Yes, delete {child.first_name}&apos;s data
                </Button>
                <Button variant="ghost" size="grown" onClick={() => setConfirming(false)}>
                  Keep it
                </Button>
              </div>
            </div>
          ) : (
            <div className="step">
              <Button variant="secondary" size="grown" onClick={() => setConfirming(true)} style={{ alignSelf: 'flex-start' }}>
                Delete {child.first_name}&apos;s data
              </Button>
              <span className="caption muted">
                Removes {child.first_name}&apos;s recordings, reports and plans. This can&apos;t be undone.
              </span>
            </div>
          )}
        </>
      ) : null}
    </Card>
  );
}
