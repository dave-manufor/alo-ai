import { useState } from 'react';
import { Button } from '../design-system/alo';
import { assistantQuestions } from './teacherFixture';

/** Assistant panel (PRD 4.7): suggested questions are buttons that reveal
 *  pre-written answers from the fixture. No model is called, and the
 *  free-text box is disabled. */
export default function AssistantPanel() {
  const [openId, setOpenId] = useState<string | null>(null);
  const open = assistantQuestions.find((item) => item.id === openId);

  return (
    <section className="card" aria-labelledby="assistant-heading">
      <h2 id="assistant-heading" className="title">
        Ask about this class
      </h2>
      <div className="row">
        {assistantQuestions.map((item) => (
          <Button
            key={item.id}
            variant="secondary"
            size="grown"
            aria-expanded={openId === item.id}
            onClick={() => setOpenId(openId === item.id ? null : item.id)}
          >
            {item.question}
          </Button>
        ))}
      </div>
      {open ? <p className="body">{open.answer}</p> : null}
      <label className="stack">
        <span className="label">Ask another question</span>
        <input className="preview-input" disabled placeholder="Coming soon" />
      </label>
    </section>
  );
}
