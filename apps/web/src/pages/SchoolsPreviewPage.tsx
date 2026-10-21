import { useState } from 'react';
import { Button } from '../design-system/alo';
import AssistantPanel from '../preview/AssistantPanel';
import ClassTable from '../preview/ClassTable';
import GroupsPanel from '../preview/GroupsPanel';
import { previewBannerText, previewClass } from '../preview/teacherFixture';

// Teacher view PREVIEW (PRD 4.7): front-end only, fictional sample data,
// no sign-in, and no network calls to Firestore, the agents or any other
// data service (a test checks this). Actions that would change something
// say "Coming soon" instead of working.
export default function SchoolsPreviewPage() {
  const [notice, setNotice] = useState<string | null>(null);

  function comingSoon(action: string) {
    setNotice(`${action} is coming soon. This preview only shows sample data.`);
  }

  return (
    <main className="app-main">
      <p className="preview-banner body" role="note">
        {previewBannerText}
      </p>

      <section className="stack">
        <h1 className="title">P3B reading checks</h1>
        <p className="body muted">
          Sample class only. Numbers come from the sample checks shown here.
        </p>
        <div className="row">
          <Button variant="primary" size="grown" onClick={() => comingSoon('Run a check')}>
            Run a check
          </Button>
          <Button variant="secondary" size="grown" onClick={() => comingSoon('Export')}>
            Export
          </Button>
        </div>
        {notice ? (
          <p className="body" role="status">
            {notice}
          </p>
        ) : null}
      </section>

      <ClassTable children={previewClass} />
      <GroupsPanel children={previewClass} />
      <AssistantPanel />
    </main>
  );
}
