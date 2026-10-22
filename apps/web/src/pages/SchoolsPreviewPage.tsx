import { useState } from 'react';
import { Button } from '../design-system/alo';
import AssistantPanel from '../preview/AssistantPanel';
import ClassTable from '../preview/ClassTable';
import GroupsPanel from '../preview/GroupsPanel';
import { previewClass, type ProfileId } from '../preview/teacherFixture';
import { Notice } from '../ui/primitives';

// Teacher view PREVIEW (PRD 4.7; wireframe 23): front-end only, fictional sample data, no
// sign-in, and no network calls to Firestore, the agents or any other data service (a test
// checks this). The "sample data" banner is on the school layout, so it is on every screen.
// Actions that would change something say "Coming soon" instead of working.
const NEEDS_UNDERSTANDING_HELP: ProfileId[] = [
  'COMPREHENSION_STRATEGY_GAP',
  'FLUENT_NEEDS_LANGUAGE_SUPPORT',
  'NEEDS_SUPPORT_IN_BOTH',
];

export default function SchoolsPreviewPage() {
  const [notice, setNotice] = useState<string | null>(null);

  function comingSoon(action: string) {
    setNotice(`${action} is coming soon. This preview only shows sample data.`);
  }

  const checked = previewClass.filter((child) => child.lastCheckIso !== '').length;
  const needHelp = previewClass.filter((child) => NEEDS_UNDERSTANDING_HELP.includes(child.profile)).length;
  const provisional = previewClass.filter((child) => child.provisional).length;
  const due = previewClass.filter((child) => child.dueForCheck).length;

  return (
    <>
      <section className="preview-head">
        <div className="step">
          <h1 className="display-m">P3B reading checks</h1>
          <p className="caption muted">
            Sample class · {previewClass.length} children · checks from the last two weeks
          </p>
        </div>
        <div className="ui-actions ui-actions--full preview-actions">
          <Button variant="secondary" size="grown" onClick={() => comingSoon('Download class summary')}>
            Download class summary
          </Button>
          <Button variant="primary" size="grown" onClick={() => comingSoon('Run a check')}>
            Run a check
          </Button>
        </div>
      </section>
      {notice ? (
        <Notice tone="night" role="status">
          {notice}
        </Notice>
      ) : null}

      <section className="preview-tiles" aria-label="Class at a glance">
        <Tile label="Checked" value={`${checked} of ${previewClass.length}`} />
        <Tile label="Need help understanding" value={`${needHelp} children`} />
        <Tile label="Provisional results" value={`${provisional} ${provisional === 1 ? 'child' : 'children'}`} />
        <Tile label="Due a check" value={`${due} ${due === 1 ? 'child' : 'children'}`} />
      </section>

      <ClassTable children={previewClass} />

      <div className="preview-columns">
        <GroupsPanel children={previewClass} />
        <AssistantPanel />
      </div>

      <p className="caption muted">
        Sample numbers for the preview only. In the product, every number comes from a child&apos;s latest check and links
        to its report.
      </p>
    </>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="ui-card preview-tile">
      <span className="label muted">{label}</span>
      <span className="title">{value}</span>
    </div>
  );
}
