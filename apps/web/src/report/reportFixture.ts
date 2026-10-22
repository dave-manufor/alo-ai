// Report fixtures for the MVP UI (fixture-backed phase). Field names and
// nullability copy W3's ReadingReport contract (PRD 10.4; the schema and
// sample live in PR #15: schemas/reading_report.schema.json and
// fixtures/contracts/reading_report.sess_demo_001.json). Importing those
// fixture files directly has to wait for #15 to merge; until then this
// copy keeps schema_version, child_id and level.at_least so drift shows.
//
// The report carries child_id, never a name (PRD 12: names live only on
// the child document). The screens join report + child, exactly as the
// live read (reports/{session_id} + children/{child_id}) will. Every
// number is sample data from the report; the UI displays, never computes.
//
// Many fields are NULLABLE in the contract: a session that gave no
// evidence (kindness-rule stop, poor audio, INSUFFICIENT_EVIDENCE) has no
// accuracy, no WCPM, no comprehension score and no level. The screens
// must handle that, never print "null%".

export interface ReportChild {
  child_id: string;
  first_name: string;
}

export interface ReadingReport {
  schema_version: 2;
  session_id: string;
  child_id: string;
  timestamp_iso: string;
  primary_class: number;
  passage: { passage_id: string; title: string; source: 'BANK' | 'GENERATED' };
  fluency: {
    accuracy_pct: number | null;
    wcpm: number | null;
    words_attempted: number | null;
    word_reading_ok: boolean | null;
  };
  comprehension: {
    reading_comprehension: number | null;
    listening_module_run: boolean;
    listening_comprehension: number | null;
  };
  level: {
    reported_arl: number | null;
    band: string | null;
    at_least: boolean;
    approx_primary_class: string | null;
    confirmed: boolean;
  };
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
  /** Written by the Reading Coach after the session; null until it runs. */
  parent_reporting: {
    summary_script: string;
    home_practice: string;
  } | null;
  recommendations: { arl_min: number | null; arl_max: number | null; book_ids: string[] };
  flags: string[];
}

export interface Book {
  book_id: string;
  title: string;
  author: string;
  licence: string;
  attribution: string;
  arl: number;
}

/** Sample children (the join target for child_id). */
export const sampleChildren: Record<string, ReportChild> = {
  child_demo_001: { child_id: 'child_demo_001', first_name: 'Adaeze' },
  child_demo_002: { child_id: 'child_demo_002', first_name: 'Tunde' },
};

export const sampleReports: ReadingReport[] = [
  {
    schema_version: 2,
    session_id: 'sess_demo_001',
    child_id: 'child_demo_001',
    timestamp_iso: '2026-01-15T09:09:05Z',
    primary_class: 2,
    passage: { passage_id: 'bank_p3_market_day', title: 'Market Day', source: 'BANK' },
    fluency: { accuracy_pct: 90.9, wcpm: 68, words_attempted: 23, word_reading_ok: false },
    comprehension: {
      reading_comprehension: 70,
      listening_module_run: true,
      listening_comprehension: 93.3,
    },
    level: {
      reported_arl: 2,
      band: 'SUPPORTED',
      at_least: false,
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
    parent_reporting: {
      summary_script:
        'Hello! Auntie Kemi here. Adaeze read 68 words correctly in a minute today, and got most words right. She remembered the main events of the story but found the why question tricky. This was a short check, so think of it as a first look.',
      home_practice:
        'Try a sound hunt: pick a sound from a word Adaeze found hard, and find three things at home that start with it.',
    },
    recommendations: { arl_min: 1, arl_max: 2, book_ids: ['book_demo_001', 'book_demo_002', 'book_demo_003'] },
    flags: ['DEMO_PROFILE', 'SHORT_READING'],
  },
  {
    schema_version: 2,
    session_id: 'sess_demo_002',
    child_id: 'child_demo_002',
    timestamp_iso: '2026-01-16T09:09:05Z',
    primary_class: 3,
    passage: { passage_id: 'bank_p3_market_day', title: 'Market Day', source: 'BANK' },
    fluency: { accuracy_pct: null, wcpm: null, words_attempted: null, word_reading_ok: null },
    comprehension: {
      reading_comprehension: null,
      listening_module_run: false,
      listening_comprehension: null,
    },
    level: {
      reported_arl: null,
      band: null,
      at_least: false,
      approx_primary_class: null,
      confirmed: false,
    },
    profile: {
      code: 'INSUFFICIENT_EVIDENCE',
      provisional: false,
      primary_need: 'Not enough reading to learn from this time',
      instructional_focus: 'Try another check when it is quiet, with the phone close.',
    },
    parent_reporting: null,
    recommendations: { arl_min: null, arl_max: null, book_ids: [] },
    flags: ['LOW_AUDIO'],
  },
];

/** Coach plan activities. Only shown with an active subscription
 *  (subscriptions/{guardian_id}); before that, the report's own
 *  parent_reporting summary and home practice are the free part (PRD 11.1). */
export const samplePlan = [
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

/** Sample catalogue entries (PRD 9.1: the real catalogue holds only real
 *  open-licence titles with author, licence and required attribution per
 *  title — these samples must never ship outside this fixture). */
export const sampleBooks: Record<string, Book> = {
  book_demo_001: {
    book_id: 'book_demo_001',
    title: 'The Goat at the Market (sample)',
    author: 'Sample Author',
    licence: 'CC BY 4.0 (sample)',
    attribution: 'Sample attribution for this fixture only.',
    arl: 1,
  },
  book_demo_002: {
    book_id: 'book_demo_002',
    title: 'Ada Goes to School (sample)',
    author: 'Sample Author',
    licence: 'CC BY 4.0 (sample)',
    attribution: 'Sample attribution for this fixture only.',
    arl: 2,
  },
  book_demo_003: {
    book_id: 'book_demo_003',
    title: 'The River Trip (sample)',
    author: 'Sample Author',
    licence: 'CC BY 4.0 (sample)',
    attribution: 'Sample attribution for this fixture only.',
    arl: 2,
  },
};

export function formatReportDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/** "ARL 2", "ARL 2 or above" (PRD 6.7), or null when there is no level. */
export function levelLabel(report: ReadingReport): string | null {
  if (report.level.reported_arl === null) return null;
  return report.level.at_least
    ? `ARL ${report.level.reported_arl} or above`
    : `About ARL ${report.level.reported_arl}`;
}
