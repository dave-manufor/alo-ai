import { useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { addChild } from '../account/actions';
import { CONSENT_TEXT, accountStore, ageFromBirthYear, attestationFor, useAccount } from '../account/store';
import { dataMode } from '../api';
import { Button } from '../design-system/alo';
import { consentDraft, useConsentDraft } from '../onboarding/draft';
import { BackLink, CheckRow, Field, Notice, Segmented } from '../ui/primitives';

// The visible "P3" is the button's accessible name, with the group label "Class this school
// year" around it (WCAG 2.5.3: the name must contain the visible text).
const CLASSES = [1, 2, 3, 4, 5, 6].map((value) => ({ value, label: `P${value}` }));

// A child of Primary 3 is usually 8: the birth year starts there until the guardian picks one.
const typicalBirthYear = (primaryClass: number, now = new Date()) => now.getFullYear() - (primaryClass + 5);

// Where this form is used: onboarding step 2, adding another child later, or editing one.
export type ChildFormMode = 'onboarding' | 'new' | 'edit';

// Add a child (PRD 4.4, 12). Saving adds the child AND records that child's consent in one
// step. The attestation names the child and their age, so it is shown in full before saving.
// In onboarding the guardian already ticked it on the last step; adding another child asks
// again, because consent is per child.
export default function ChildFormPage({ mode }: { mode: ChildFormMode }) {
  const { childId } = useParams();
  const navigate = useNavigate();
  const { children } = useAccount();
  const draft = useConsentDraft();
  const editing = mode === 'edit' ? children.find((child) => child.child_id === childId) : undefined;

  const [firstName, setFirstName] = useState(editing?.first_name ?? '');
  const [primaryClass, setPrimaryClass] = useState(editing?.primary_class ?? 3);
  const [birthYear, setBirthYear] = useState<number | null>(editing?.birth_year ?? null);
  const [attestedHere, setAttestedHere] = useState(false);
  const [trainingHere, setTrainingHere] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Onboarding without the last step's tick goes back to it: consent comes first.
  if (mode === 'onboarding' && !draft.attested) return <Navigate to="/onboarding/consent" replace />;
  if (mode === 'edit' && !editing) return <Navigate to="/account" replace />;

  const attestedBefore = mode === 'onboarding' && draft.attested;
  const attested = attestedBefore || attestedHere;
  const trainingOptIn = mode === 'onboarding' ? draft.trainingOptIn : trainingHere;
  const year = birthYear ?? typicalBirthYear(primaryClass);
  const trimmed = firstName.trim();
  const thisYear = new Date().getFullYear();
  const years = Array.from({ length: 9 }, (_, index) => thisYear - 4 - index);
  const back = mode === 'onboarding' ? '/onboarding/consent' : mode === 'edit' ? '/account' : '/home';

  // Editing needs an Account API call that does not exist yet; say so rather than pretend.
  if (mode === 'edit' && dataMode === 'live') {
    return (
      <div className="page">
        <BackLink to={back} />
        <Notice tone="sky" role="note">
          Changing a child&apos;s details is coming soon.
        </Notice>
      </div>
    );
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!trimmed) {
      setNameError('Please add your child’s first name.');
      return;
    }
    setNameError(null);
    setError(null);
    setSaving(true);
    try {
      if (mode === 'edit' && editing) {
        accountStore.updateChild(editing.child_id, { firstName: trimmed, primaryClass, birthYear: year });
        navigate('/account');
        return;
      }
      await addChild({ firstName: trimmed, primaryClass, birthYear: year, attested, trainingOptIn });
      consentDraft.clear();
      navigate('/home');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'We could not save that. Please try again.');
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <BackLink to={back} />
      <form className="page-stack" onSubmit={save} noValidate>
        <div className="step">
          {mode === 'onboarding' ? <p className="label ui-steps">Step 2 of 2</p> : null}
          <h1 className="display-m">{mode === 'edit' ? 'Edit your child' : 'Add your child'}</h1>
        </div>

        <Field label="First name" hint="First name only. Kemi uses it to greet your child." error={nameError}>
          {(props) => (
            <input
              {...props}
              className="ui-input"
              value={firstName}
              autoComplete="off"
              onChange={(event) => setFirstName(event.target.value)}
            />
          )}
        </Field>

        <div className="ui-field">
          <Segmented
            label="Class this school year"
            value={primaryClass}
            options={CLASSES}
            onChange={setPrimaryClass}
          />
          <span className="caption muted">
            The class sets the level of the first story. Each September we will ask you to confirm it.
          </span>
        </div>

        <Field label="Birth year">
          {(props) => (
            <select
              {...props}
              className="ui-input"
              value={year}
              onChange={(event) => setBirthYear(Number(event.target.value))}
            >
              {years.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          )}
        </Field>

        {mode !== 'edit' ? (
          <div className="ui-card ui-card--night">
            {attestedBefore ? (
              <p className="body">You agreed on the last step.</p>
            ) : (
              <>
                <CheckRow
                  checked={attestedHere}
                  onChange={setAttestedHere}
                  title="I am the parent or guardian of this child."
                />
                <CheckRow
                  checked={trainingHere}
                  onChange={setTrainingHere}
                  title="Recordings may be used to improve Alo.ai."
                  hint="Optional."
                />
              </>
            )}
            <p className="caption muted">
              {trimmed
                ? attestationFor(trimmed, ageFromBirthYear(year))
                : `I am the parent or guardian of this child. ${CONSENT_TEXT}`}
            </p>
          </div>
        ) : null}

        {error ? (
          <Notice tone="sky" role="alert">
            {error}
          </Notice>
        ) : null}

        <Button
          variant="primary"
          size="grown"
          type="submit"
          disabled={saving || (mode !== 'edit' && !attested)}
          style={{ width: '100%' }}
        >
          {mode === 'edit' ? 'Save changes' : 'Save child'}
        </Button>
      </form>
    </div>
  );
}
