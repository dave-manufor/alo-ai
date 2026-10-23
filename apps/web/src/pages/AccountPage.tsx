import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { changeTrainingOptIn } from '../account/actions';
import { accountStore, useAccount, type ChildProfile } from '../account/store';
import { ApiError, dataMode } from '../api';
import { auth, authMode } from '../auth';
import { Button } from '../design-system/alo';
import NavButton from '../design-system/NavButton';
import { planUnlocked } from '../plan/access';
import { PLAN_PRICE, PLAN_PRICE_PERIOD } from '../plan/price';
import { Avatar, Card, CheckRow, Notice, SectionLabel, Switch } from '../ui/primitives';

// Account and privacy (wireframe 22): the children, the choices about their recordings, the
// plan, and sign out. Editing a child and changing the recordings choice go through the Account
// API in a live build. Deleting a child's data is not an in-app button there: the study team
// does it on request (ops/delete_child.py), and the screen says so. The sample build keeps its
// demo delete.
export default function AccountPage() {
  const navigate = useNavigate();
  const { guardian, children } = useAccount();
  const subscribed = planUnlocked(guardian !== null);
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
              <Link to={`/children/${child.child_id}/edit`} className="body card-title ui-tap" aria-label={`Edit ${child.first_name}`}>
                Edit
              </Link>
            </div>
          </Card>
        ))}
        <NavButton variant="ghost" size="grown" to="/children/new" style={{ alignSelf: 'flex-start' }}>
          Add another child
        </NavButton>
      </section>

      <section className="step" aria-labelledby="privacy-heading">
        <SectionLabel id="privacy-heading">Privacy</SectionLabel>
        {children.map((child) => (
          <ChildPrivacy key={child.child_id} child={child} showName={children.length > 1} />
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
          <Link to="/terms" className="ui-tap ui-tap--flush">Terms</Link> · <Link to="/privacy" className="ui-tap ui-tap--flush">Privacy notice</Link>
        </p>
      </section>
    </div>
  );
}

function ChildPrivacy({ child, showName }: { child: ChildProfile; showName: boolean }) {
  const navigate = useNavigate();
  const live = dataMode === 'live';
  const consent = accountStore.consentFor(child.child_id);
  const [confirming, setConfirming] = useState(false);
  // Live build: a changed choice waits here until the guardian ticks that they are the parent
  // or guardian, because each change is saved as a new record of consent.
  const [pending, setPending] = useState<boolean | null>(null);
  const [attested, setAttested] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const optIn = consent?.training_opt_in ?? false;

  function remove() {
    accountStore.removeChild(child.child_id);
    if (accountStore.getState().children.length === 0) navigate('/onboarding/consent');
  }

  function choose(next: boolean) {
    if (!live) {
      void changeTrainingOptIn(child.child_id, next);
      return;
    }
    setPending(next === optIn ? null : next);
    setAttested(false);
    setError(null);
  }

  async function saveChoice() {
    if (pending === null || !attested) return;
    setSaving(true);
    setError(null);
    try {
      await changeTrainingOptIn(child.child_id, pending);
      setPending(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.plain : 'We could not save that. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      {showName ? <p className="body card-title">{child.first_name}</p> : null}
      <Switch
        title="Use recordings to improve Alo.ai"
        hint={`${optIn ? 'On' : 'Off'}. Recordings are deleted after 90 days.`}
        checked={pending ?? optIn}
        onChange={choose}
      />
      {pending !== null ? (
        <div className="step">
          <p className="body">
            {pending ? 'Turn this on' : 'Turn this off'} for {child.first_name}? Each change is saved as a new record of
            your consent.
          </p>
          <CheckRow
            checked={attested}
            onChange={setAttested}
            title={`I am the parent or guardian of ${child.first_name}.`}
          />
          {error ? (
            <Notice tone="sky" role="alert">
              {error}
            </Notice>
          ) : null}
          <div className="ui-actions">
            <Button variant="primary" size="grown" disabled={!attested || saving} onClick={saveChoice}>
              Save
            </Button>
            <Button variant="ghost" size="grown" disabled={saving} onClick={() => setPending(null)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
      {live ? (
        <>
          <div className="ui-divider" />
          <div className="step">
            <p className="body card-title">Delete {child.first_name}&apos;s data</p>
            <span className="caption muted">
              To have {child.first_name}&apos;s recordings, reports and plans deleted, ask the study team who gave you
              Alo.ai, and we will delete them.
            </span>
          </div>
        </>
      ) : (
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
      )}
    </Card>
  );
}
