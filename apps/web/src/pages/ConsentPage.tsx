import { Link, useNavigate } from 'react-router-dom';
import { consentDraft, useConsentDraft } from '../onboarding/draft';
import { Button } from '../design-system/alo';
import { BackLink, Card, CheckRow, SectionLabel } from '../ui/primitives';

// Onboarding step 1 (PRD 12): what we record and keep, and the guardian's yes. The yes is
// written per child, naming the child and their age, when the child is added on the next
// step (the attestation is spelled out there). Nothing is saved here.
export default function ConsentPage() {
  const navigate = useNavigate();
  const draft = useConsentDraft();

  return (
    <div className="page">
      <BackLink to="/" />
      <div className="page-stack">
        <div className="step">
          <p className="label ui-steps">Step 1 of 2</p>
          <h1 className="display-m">Before your child reads</h1>
          <p className="body">
            Alo.ai records your child&apos;s voice while they read and answer, so it can make their
            reading report. Recordings are deleted after 90 days.
          </p>
        </div>

        <Card>
          <CheckRow
            checked={draft.attested}
            onChange={(attested) => consentDraft.set({ ...draft, attested })}
            title="I am the parent or guardian of this child."
            hint="Required. You will confirm it for each child you add."
          />
          <CheckRow
            checked={draft.trainingOptIn}
            onChange={(trainingOptIn) => consentDraft.set({ ...draft, trainingOptIn })}
            title="Recordings may be used to improve Alo.ai."
            hint="Optional. You can change this any time in your account."
          />
        </Card>

        <div className="step">
          <SectionLabel>What we keep</SectionLabel>
          <p className="body">
            Your child&apos;s first name, class and birth year. Nothing your child says in the chat
            goes into their story, and our payment partner never sees anything about your child.
          </p>
          <Link to="/privacy" className="body">
            Read the full privacy notice
          </Link>
        </div>

        <Button
          variant="primary"
          size="grown"
          disabled={!draft.attested}
          onClick={() => navigate('/onboarding/child')}
          style={{ width: '100%' }}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
