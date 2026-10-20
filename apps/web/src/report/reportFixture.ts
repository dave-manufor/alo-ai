// Report-screen fixture for the MVP UI (stacked, fixture-backed phase).
// Shape follows W3's ReadingReport contract (PRD 10.4 and the sample in
// PR #15, fixtures/contracts/reading_report.sess_demo_001.json). Every
// number below is sample data standing in for the report document the
// Grader writes to reports/{session_id}; the UI only displays numbers
// from the report, it never works any out. When PR #15 merges and the
// Account service can read reports, this file is replaced by that read.

export interface ReadingReport {
  session_id: string;
  child_display_name: string;
  timestamp_iso: string;
  primary_class: number;
  passage: { title: string; source: 'BANK' | 'GENERATED'; topic_tags: string[] };
  fluency: {
    accuracy_pct: number;
    wcpm: number;
    words_attempted: number;
    reading_seconds: number;
    word_reading_ok: boolean;
  };
  comprehension: {
    reading_comprehension: number;
    listening_module_run: boolean;
    listening_comprehension: number | null;
  };
  level: { reported_arl: number; approx_primary_class: string; confirmed: boolean };
  profile: {
    code:
      | 'ON_TRACK'
      | 'UNDERSTANDS_BUILDING_WORD_READING'
      | 'DECODING_LIMITED'
      | 'FLUENT_NEEDS_LANGUAGE_SUPPORT'
      | 'NEEDS_SUPPORT_IN_BOTH'
      | 'COMPREHENSION_STRATEGY_GAP'
      | 'INSUFFICIENT_EVIDENCE';
    provisional: boolean;
    primary_need: string;
    instructional_focus: string;
  };
  flags: string[];
}

export interface PlanActivity {
  activity_id: string;
  title: string;
  text: string;
}

export const sampleReports: ReadingReport[] = [
  {
    session_id: 'sess_demo_001',
    child_display_name: 'Adaeze',
    timestamp_iso: '2026-01-15T09:09:05Z',
    primary_class: 2,
    passage: { title: 'Market Day', source: 'BANK', topic_tags: ['food'] },
    fluency: {
      accuracy_pct: 90.9,
      wcpm: 68,
      words_attempted: 23,
      reading_seconds: 19.65,
      word_reading_ok: false,
    },
    comprehension: {
      reading_comprehension: 70,
      listening_module_run: true,
      listening_comprehension: 93.3,
    },
    level: {
      reported_arl: 2,
      approx_primary_class: 'Primary 1 (approximate, not normed)',
      confirmed: false,
    },
    profile: {
      code: 'UNDERSTANDS_BUILDING_WORD_READING',
      provisional: true,
      primary_need: 'Understands stories; reading the words is still developing',
      instructional_focus:
        'Practise the sounds in the words that were hard today, and keep story questions at class level.',
    },
    flags: ['DEMO_PROFILE', 'SHORT_READING'],
  },
];

/** Coach plan sample (PR #15 plan fixture shape). Shown after checkout. */
export const samplePlan: PlanActivity[] = [
  {
    activity_id: 'act_sound_hunt',
    title: 'Sound hunt',
    text: "Pick a sound from a word your child found hard today, like the 'ch' in 'chose'. Find three things at home or at the market that start with that sound.",
  },
  {
    activity_id: 'act_word_cards',
    title: 'Word cards',
    text: 'Write five words your child paused on today on small cards. Read them together each day, and put a card away once the word feels easy.',
  },
  {
    activity_id: 'act_class_level_talk',
    title: 'Talk about class-level stories',
    text: "Keep reading stories at your child's class level aloud to them and ask what happened and why. Understanding is a strength, so keep it growing.",
  },
];

/** Sample book suggestions. The real list comes from W2's catalogue
 *  (books/{book_id}, PRD 9) ranked by W3; titles here are UI samples. */
export const sampleBooks = [
  { book_id: 'book_demo_001', title: 'The Goat at the Market', band: 'ARL 1–2' },
  { book_id: 'book_demo_002', title: 'Ada Goes to School', band: 'ARL 1–2' },
  { book_id: 'book_demo_003', title: 'The River Trip', band: 'ARL 2' },
];

export function formatReportDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}
