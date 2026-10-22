import { Link, useNavigate } from 'react-router-dom';
import { consentDraft, useConsentDraft } from '../onboarding/draft';
import { Button } from '../design-system/alo';
import { BackLink, Card, CheckRow, SectionLabel } from '../ui/primitives';

// Onboarding step 1 (PRD 12): what we record and keep, and the guardian's yes. The yes is
// written per child, naming the child and their age, when the child is added on the next
// step (the attestation is spelled out there, with CONSENT_TEXT in full). Nothing is saved
// here. The wording follows consent_v2 (what is recorded, transcripts, who sees them, where
// they are processed, that the child can stop, that deletion can be asked for).
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
            For each child you add, we ask you to agree that Alo.ai can record them reading aloud and answering
            questions, turn the recording into a written transcript, and use both to make a reading report for you.
            Recordings are kept for up to 90 days and then deleted. Transcripts and the report stay in your account
            until you ask for them to be deleted. Only your family and the Alo.ai study team can see them, and they
            are processed on secure servers in Europe. Alo.ai is a screening tool that helps you practise reading.
          </p>
          <p className="body">
            Your child can stop at any time, and you can ask for everything about your child to be deleted. Letting
            recordings help Alo.ai learn is a separate choice for each child, and it is off unless you turn it on.
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
            Your child&apos;s first name, class and birth year. Nothing your child says in the chat goes into their
            story, and our payment partner never sees anything about your child.
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
