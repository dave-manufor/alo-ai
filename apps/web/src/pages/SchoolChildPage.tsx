import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Button, ParentReportCard, ProfilePill } from '../design-system/alo';
import {
  practicePlanByProfile,
  previewBannerText,
  previewClass,
  samplePassage,
} from '../preview/teacherFixture';

// Child page of the teacher view PREVIEW (PRD 4.7): a sample report, the
// sample passage with misreadings marked, and the practice plan. Listening
// to a word and changing the plan say "Coming soon" instead of working.
// Misreadings are marked with a word and a shape, never colour alone.
export default function SchoolChildPage() {
  const { childId } = useParams();
  const child = previewClass.find((item) => item.id === childId);
  const [notice, setNotice] = useState<string | null>(null);

  if (!child) {
    return (
      <main className="app-main">
        <p className="preview-banner body" role="note">
          {previewBannerText}
        </p>
        <section className="stack">
          <h1 className="title">We could not find that child</h1>
          <p className="body">This preview only has the sample class, P3B.</p>
          <Link to="/schools/preview">
            <Button variant="secondary" size="grown">
              Back to the class
            </Button>
          </Link>
        </section>
      </main>
    );
  }

  const misreadWords = new Map(child.misreadings.map((m) => [m.word, m.heard]));

  return (
    <main className="app-main">
      <p className="preview-banner body" role="note">
        {previewBannerText}
      </p>

      <section className="stack">
        <h1 className="title">{child.name}</h1>
        <ProfilePill profile={child.profile} provisional={child.provisional} />
        <p className="body muted">
          Last check {child.lastCheck} · Reading level {child.readingLevel}
          {child.assisted ? ' · assisted check' : ''}
        </p>
      </section>

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
        <p className="body muted">
          Words read differently are underlined and listed below the story.
        </p>
        {samplePassage.sentences.map((sentence) => (
          <p key={sentence} className="reading-p3">
            {sentence.split(' ').map((token, index) => {
              const word = token.replace(/[^A-Za-zÀ-ÿ'-]/g, '');
              const heard = misreadWords.get(word);
              return heard ? (
                <mark key={`${token}-${index}`} className="misread">
                  {token}{' '}
                </mark>
              ) : (
                <span key={`${token}-${index}`}>{token} </span>
              );
            })}
          </p>
        ))}
        {child.misreadings.length > 0 ? (
          <ul className="body">
            {child.misreadings.map((item) => (
              <li key={item.word}>
                “{item.word}” was read as “{item.heard}”.
              </li>
            ))}
          </ul>
        ) : (
          <p className="body">No words were read differently in this sample.</p>
        )}
        <div className="row">
          <Button
            variant="secondary"
            size="grown"
            onClick={() => setNotice('Listening to a word is coming soon.')}
          >
            Hear a word
          </Button>
          <Button
            variant="secondary"
            size="grown"
            onClick={() => setNotice('Changing the plan is coming soon.')}
          >
            Change the plan
          </Button>
        </div>
        {notice ? (
          <p className="body" role="status">
            {notice}
          </p>
        ) : null}
      </section>

      <Link to="/schools/preview">
        <Button variant="secondary" size="grown">
          Back to the class
        </Button>
      </Link>
    </main>
  );
}
