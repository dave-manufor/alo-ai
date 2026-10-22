import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, ParentReportCard, ProfilePill } from '../design-system/alo';
import { practicePlanByProfile, previewClass, samplePassage } from '../preview/teacherFixture';
import { BackLink, Card, Notice } from '../ui/primitives';

// Child page of the teacher view PREVIEW (PRD 4.7): a sample report, the sample passage
// with misreadings marked at their token positions, and the practice plan. Listening to a
// word and changing the plan say "Coming soon" instead of working. Misreadings are marked
// with an underline and listed in words, never by colour alone. The sample-data banner is
// on the school layout.
export default function SchoolChildPage() {
  const { childId } = useParams();
  const child = previewClass.find((item) => item.id === childId);
  const [notice, setNotice] = useState<string | null>(null);

  if (!child) {
    return (
      <>
        <BackLink to="/schools">Back to the class</BackLink>
        <Card>
          <h1 className="title">We could not find that child</h1>
          <p className="body">This preview only has the sample class, P3B.</p>
        </Card>
      </>
    );
  }

  const misreadAt = new Map(child.misreadings.map((m) => [m.token_index, m]));
  let tokenIndex = -1;

  return (
    <>
      <BackLink to="/schools">Back to the class</BackLink>
      <div className="step">
        <h1 className="display-m">{child.name}</h1>
        <div>
          <ProfilePill profile={child.profile} provisional={child.provisional} />
        </div>
        <p className="body muted">
          Last check {child.lastCheck} · Reading level {child.readingLevel}
          {child.assisted ? ' · assisted check' : ''}
        </p>
      </div>

      <div className="page-grid">
        <ParentReportCard
          title={`${child.name.split(' ')[0]}'s reading`}
          date={`Sample check · ${child.lastCheck}`}
          summary={practicePlanByProfile[child.profile]}
          stats={[
            { label: 'Accuracy', value: child.accuracyPct === null ? '—' : `${child.accuracyPct}%` },
            { label: 'Words a minute', value: child.wcpm === null ? '—' : child.wcpm },
          ]}
          workingOn={practicePlanByProfile[child.profile]}
        />

        <section className="card" aria-labelledby="passage-heading">
          <h2 id="passage-heading" className="title">
            {samplePassage.title} (sample story)
          </h2>
          <p className="body muted">Words read differently are underlined and listed below the story.</p>
          {samplePassage.sentences.map((sentence) => (
            <p key={sentence} className="reading-p3">
              {sentence.split(' ').map((token) => {
                tokenIndex += 1;
                const atThisToken = tokenIndex;
                return misreadAt.has(atThisToken) ? (
                  <mark key={atThisToken} className="misread">
                    {token}{' '}
                  </mark>
                ) : (
                  <span key={atThisToken}>{token} </span>
                );
              })}
            </p>
          ))}
          {child.misreadings.length > 0 ? (
            <ul className="body">
              {child.misreadings.map((item) => (
                <li key={item.token_index}>
                  “{item.word}” was read as “{item.heard}”.
                </li>
              ))}
            </ul>
          ) : (
            <p className="body">No words were read differently in this sample.</p>
          )}
          <div className="ui-actions">
            <Button variant="secondary" size="grown" onClick={() => setNotice('Listening to a word is coming soon.')}>
              Hear a word
            </Button>
            <Button variant="secondary" size="grown" onClick={() => setNotice('Changing the plan is coming soon.')}>
              Change the plan
            </Button>
          </div>
          {notice ? (
            <Notice tone="night" role="status">
              {notice}
            </Notice>
          ) : null}
        </section>
      </div>
    </>
  );
}
