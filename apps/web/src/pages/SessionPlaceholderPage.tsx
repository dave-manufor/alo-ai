import {
  Button,
  Japa,
  MicButton,
  MoonProgress,
  ReadingPanel,
  SpeechBubble,
} from '../design-system/alo';

// Kid mode scaffold for the session screen (PRD 4.1). The real screen joins
// a LiveKit room and follows W2's session protocol (clip_list, play,
// show_passage, hide_passage, reconnecting); that arrives in its own branch.
// Sample story text is fictional. No score, timer or percentage is ever
// shown to a child.
export default function SessionPlaceholderPage() {
  return (
    <main className="app-main">
      <SpeechBubble tone="call">Àlọ́ o!</SpeechBubble>

      <section className="stack" aria-label="Your story">
        <Japa pose="happy" />
        <MoonProgress steps={['Say hello', 'Read', 'Tell', 'Answer']} current={1} />
        <ReadingPanel
          title="Ada and the Small Goat"
          level="p3"
          text={[
            'Ada had a small brown goat.',
            'The goat loved to eat green leaves.',
            'One day, the goat ran to the market.',
            'Ada laughed and ran after it.',
          ]}
        />
      </section>

      <section className="stack" aria-label="Your turn">
        <SpeechBubble>Read the story aloud for me.</SpeechBubble>
        <MicButton state="idle" />
        <Button variant="primary" size="kid" icon="mic">
          Start reading
        </Button>
      </section>
    </main>
  );
}
