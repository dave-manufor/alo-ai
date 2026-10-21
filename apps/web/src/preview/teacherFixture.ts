// Teacher view PREVIEW fixture (PRD 4.7). This is the one bundled data file
// for the preview: a fictional class, "P3B (sample)", of 23 invented
// children with sample results across all 7 profiles. No real child's name,
// audio or report ever appears here, and nothing in the preview reads real
// data or calls a service.

export type ProfileId =
  | 'ON_TRACK'
  | 'UNDERSTANDS_BUILDING_WORD_READING'
  | 'DECODING_LIMITED'
  | 'FLUENT_NEEDS_LANGUAGE_SUPPORT'
  | 'NEEDS_SUPPORT_IN_BOTH'
  | 'COMPREHENSION_STRATEGY_GAP'
  | 'INSUFFICIENT_EVIDENCE';

export interface PreviewChild {
  id: string;
  name: string;
  /** Display date of the last reading check. */
  lastCheck: string;
  /** Sortable ISO date for the last check. */
  lastCheckIso: string;
  readingLevel: string;
  profile: ProfileId;
  accuracyPct: number | null;
  wcpm: number | null;
  provisional: boolean;
  assisted: boolean;
  dueForCheck: boolean;
  findsWhyQuestionsHard: boolean;
  /** Misreadings at a token position in the sample story (token_index
   *  counts words across the story from 0), as the real telemetry does. */
  misreadings: { word: string; heard: string; token_index: number }[];
}

export const previewBannerText =
  'Preview with sample data. Coming soon for schools.';

/** Practice plan per profile (PRD section 8), in plain teacher words. */
export const practicePlanByProfile: Record<ProfileId, string> = {
  ON_TRACK: 'Longer stories at the next level, with fewer pictures.',
  UNDERSTANDS_BUILDING_WORD_READING:
    'Short word-building practice on the sounds missed, with questions at class level.',
  DECODING_LIMITED:
    'Targeted sound practice, plus grade-level books read aloud so stories are not held back.',
  FLUENT_NEEDS_LANGUAGE_SUPPORT:
    'Same story level, with talk about the story: vocabulary, who did what, and why.',
  NEEDS_SUPPORT_IN_BOTH:
    'Echo reading together and high-frequency words, with lots of talking about words.',
  COMPREHENSION_STRATEGY_GAP:
    'Short stories with a stop-and-tell after each paragraph. Check again within two weeks.',
  INSUFFICIENT_EVIDENCE: 'Check again, with the audio tips shown first.',
};

const misreadings = (
  ...pairs: [string, string, number][]
): { word: string; heard: string; token_index: number }[] =>
  pairs.map(([word, heard, token_index]) => ({ word, heard, token_index }));

// Sample results are consistent with the profile rules (PRD 6.2/6.6): for
// this P3 class, word reading counts as going well only at accuracy 95%+
// and 79+ words a minute, which ON_TRACK, FLUENT_NEEDS_LANGUAGE_SUPPORT
// and COMPREHENSION_STRATEGY_GAP all need. (Once #15 lands, generate these
// rows with aloai_scoring.assign_profile so they cannot drift.)

export const previewClass: PreviewChild[] = [
  { id: 'adaeze-o', name: 'Adaeze O.', lastCheck: '12 Oct', lastCheckIso: '2026-10-12', readingLevel: 'ARL 5', profile: 'ON_TRACK', accuracyPct: 97, wcpm: 82, provisional: false, assisted: false, dueForCheck: false, findsWhyQuestionsHard: false, misreadings: misreadings(['market', 'maket', 21]) },
  { id: 'tunde-a', name: 'Tunde A.', lastCheck: '12 Oct', lastCheckIso: '2026-10-12', readingLevel: 'ARL 4', profile: 'ON_TRACK', accuracyPct: 96, wcpm: 82, provisional: false, assisted: false, dueForCheck: false, findsWhyQuestionsHard: false, misreadings: misreadings(['basket', 'baket', 18]) },
  { id: 'ngozi-e', name: 'Ngozi E.', lastCheck: '10 Oct', lastCheckIso: '2026-10-10', readingLevel: 'ARL 5', profile: 'ON_TRACK', accuracyPct: 98, wcpm: 88, provisional: true, assisted: false, dueForCheck: false, findsWhyQuestionsHard: false, misreadings: misreadings() },
  { id: 'ibrahim-s', name: 'Ibrahim S.', lastCheck: '9 Oct', lastCheckIso: '2026-10-09', readingLevel: 'ARL 4', profile: 'ON_TRACK', accuracyPct: 95, wcpm: 80, provisional: false, assisted: false, dueForCheck: false, findsWhyQuestionsHard: true, misreadings: misreadings(['quickly', 'quick', 25]) },
  { id: 'funmi-l', name: 'Funmi L.', lastCheck: '8 Oct', lastCheckIso: '2026-10-08', readingLevel: 'ARL 6', profile: 'ON_TRACK', accuracyPct: 97, wcpm: 91, provisional: false, assisted: false, dueForCheck: true, findsWhyQuestionsHard: false, misreadings: misreadings() },
  { id: 'chiamaka-n', name: 'Chiamaka N.', lastCheck: '12 Oct', lastCheckIso: '2026-10-12', readingLevel: 'ARL 3', profile: 'UNDERSTANDS_BUILDING_WORD_READING', accuracyPct: 89, wcpm: 48, provisional: false, assisted: false, dueForCheck: false, findsWhyQuestionsHard: false, misreadings: misreadings(['goat', 'got', 5], ['grass', 'gas', 40]) },
  { id: 'emeka-u', name: 'Emeka U.', lastCheck: '11 Oct', lastCheckIso: '2026-10-11', readingLevel: 'ARL 3', profile: 'UNDERSTANDS_BUILDING_WORD_READING', accuracyPct: 88, wcpm: 44, provisional: true, assisted: false, dueForCheck: false, findsWhyQuestionsHard: false, misreadings: misreadings(['farm', 'fam', 32], ['leaves', 'leaf', 12]) },
  { id: 'aisha-b', name: 'Aisha B.', lastCheck: '10 Oct', lastCheckIso: '2026-10-10', readingLevel: 'ARL 4', profile: 'UNDERSTANDS_BUILDING_WORD_READING', accuracyPct: 90, wcpm: 52, provisional: false, assisted: true, dueForCheck: false, findsWhyQuestionsHard: false, misreadings: misreadings(['market', 'maket', 21]) },
  { id: 'oluwaseun-d', name: 'Oluwaseun D.', lastCheck: '7 Oct', lastCheckIso: '2026-10-07', readingLevel: 'ARL 3', profile: 'UNDERSTANDS_BUILDING_WORD_READING', accuracyPct: 87, wcpm: 41, provisional: false, assisted: false, dueForCheck: true, findsWhyQuestionsHard: false, misreadings: misreadings(['chased', 'chase', 28], ['brown', 'bown', 4]) },
  { id: 'bola-k', name: 'Bola K.', lastCheck: '11 Oct', lastCheckIso: '2026-10-11', readingLevel: 'ARL 2', profile: 'DECODING_LIMITED', accuracyPct: 76, wcpm: 28, provisional: false, assisted: true, dueForCheck: false, findsWhyQuestionsHard: false, misreadings: misreadings(['market', 'maket', 21], ['basket', 'baket', 18], ['morning', 'moning', 14]) },
  { id: 'yakubu-m', name: 'Yakubu M.', lastCheck: '10 Oct', lastCheckIso: '2026-10-10', readingLevel: 'ARL 2', profile: 'DECODING_LIMITED', accuracyPct: 74, wcpm: 25, provisional: true, assisted: false, dueForCheck: false, findsWhyQuestionsHard: false, misreadings: misreadings(['goat', 'got', 5], ['leaves', 'leaf', 12]) },
  { id: 'adaeze-w', name: 'Adaeze W.', lastCheck: '6 Oct', lastCheckIso: '2026-10-06', readingLevel: 'ARL 3', profile: 'DECODING_LIMITED', accuracyPct: 78, wcpm: 31, provisional: false, assisted: false, dueForCheck: true, findsWhyQuestionsHard: false, misreadings: misreadings(['quickly', 'quick', 25]) },
  { id: 'kelechi-i', name: 'Kelechi I.', lastCheck: '12 Oct', lastCheckIso: '2026-10-12', readingLevel: 'ARL 5', profile: 'FLUENT_NEEDS_LANGUAGE_SUPPORT', accuracyPct: 96, wcpm: 79, provisional: false, assisted: false, dueForCheck: false, findsWhyQuestionsHard: true, misreadings: misreadings() },
  { id: 'fatima-z', name: 'Fatima Z.', lastCheck: '11 Oct', lastCheckIso: '2026-10-11', readingLevel: 'ARL 4', profile: 'FLUENT_NEEDS_LANGUAGE_SUPPORT', accuracyPct: 95, wcpm: 84, provisional: false, assisted: false, dueForCheck: false, findsWhyQuestionsHard: true, misreadings: misreadings(['chased', 'chase', 28]) },
  { id: 'olamide-r', name: 'Olamide R.', lastCheck: '9 Oct', lastCheckIso: '2026-10-09', readingLevel: 'ARL 5', profile: 'FLUENT_NEEDS_LANGUAGE_SUPPORT', accuracyPct: 97, wcpm: 84, provisional: false, assisted: false, dueForCheck: false, findsWhyQuestionsHard: true, misreadings: misreadings() },
  { id: 'chinedu-p', name: 'Chinedu P.', lastCheck: '8 Oct', lastCheckIso: '2026-10-08', readingLevel: 'ARL 4', profile: 'FLUENT_NEEDS_LANGUAGE_SUPPORT', accuracyPct: 95, wcpm: 80, provisional: false, assisted: false, dueForCheck: true, findsWhyQuestionsHard: false, misreadings: misreadings(['quickly', 'quick', 25]) },
  { id: 'halima-g', name: 'Halima G.', lastCheck: '11 Oct', lastCheckIso: '2026-10-11', readingLevel: 'ARL 2', profile: 'NEEDS_SUPPORT_IN_BOTH', accuracyPct: 72, wcpm: 22, provisional: false, assisted: true, dueForCheck: false, findsWhyQuestionsHard: true, misreadings: misreadings(['goat', 'got', 5], ['small', 'mall', 3], ['brown', 'bown', 4]) },
  { id: 'ifeanyi-j', name: 'Ifeanyi J.', lastCheck: '10 Oct', lastCheckIso: '2026-10-10', readingLevel: 'ARL 2', profile: 'NEEDS_SUPPORT_IN_BOTH', accuracyPct: 70, wcpm: 20, provisional: true, assisted: true, dueForCheck: false, findsWhyQuestionsHard: true, misreadings: misreadings(['farm', 'fam', 32], ['grass', 'gas', 40]) },
  { id: 'yetunde-f', name: 'Yetunde F.', lastCheck: '5 Oct', lastCheckIso: '2026-10-05', readingLevel: 'ARL 3', profile: 'NEEDS_SUPPORT_IN_BOTH', accuracyPct: 75, wcpm: 27, provisional: false, assisted: false, dueForCheck: true, findsWhyQuestionsHard: false, misreadings: misreadings(['basket', 'baket', 18]) },
  { id: 'sade-h', name: 'Sade H.', lastCheck: '12 Oct', lastCheckIso: '2026-10-12', readingLevel: 'ARL 4', profile: 'COMPREHENSION_STRATEGY_GAP', accuracyPct: 95, wcpm: 81, provisional: false, assisted: false, dueForCheck: false, findsWhyQuestionsHard: true, misreadings: misreadings(['basket', 'baket', 18]) },
  { id: 'musa-t', name: 'Musa T.', lastCheck: '11 Oct', lastCheckIso: '2026-10-11', readingLevel: 'ARL 4', profile: 'COMPREHENSION_STRATEGY_GAP', accuracyPct: 96, wcpm: 85, provisional: false, assisted: false, dueForCheck: false, findsWhyQuestionsHard: true, misreadings: misreadings() },
  { id: 'blessing-q', name: 'Blessing Q.', lastCheck: 'Not yet', lastCheckIso: '', readingLevel: '—', profile: 'INSUFFICIENT_EVIDENCE', accuracyPct: null, wcpm: null, provisional: false, assisted: false, dueForCheck: true, findsWhyQuestionsHard: false, misreadings: misreadings() },
  { id: 'segun-v', name: 'Segun V.', lastCheck: 'Not yet', lastCheckIso: '', readingLevel: '—', profile: 'INSUFFICIENT_EVIDENCE', accuracyPct: null, wcpm: null, provisional: false, assisted: false, dueForCheck: true, findsWhyQuestionsHard: false, misreadings: misreadings() },
];

/** The sample story every child page shows, with words that can be marked. */
export const samplePassage = {
  title: 'The Market Day',
  sentences: [
    'Ada had a small brown goat.',
    'The goat loved to eat green leaves.',
    'One morning, Ada took a basket to the market.',
    'The goat ran quickly, and Ada chased it past the farm.',
    'Ada laughed and gave the goat some grass to eat.',
  ],
};

export interface AssistantQuestion {
  id: string;
  question: string;
  answer: string;
}

/** Pre-written assistant answers (PRD 4.7). No model is ever called. */
export const assistantQuestions: AssistantQuestion[] = [
  {
    id: 'not-checked',
    question: "Who hasn't been checked this term?",
    answer:
      'Blessing Q. and Segun V. have not been checked yet. Funmi L., Oluwaseun D., Adaeze W., Chinedu P. and Yetunde F. are also due a new check.',
  },
  {
    id: 'why-questions',
    question: "Who struggles with 'why' questions?",
    answer:
      "From the sample checks: Ibrahim S., Kelechi I., Fatima Z., Olamide R., Halima G., Ifeanyi J., Sade H. and Musa T. found 'why' questions hard. Try short stories with a stop-and-talk after each paragraph.",
  },
  {
    id: 'groups',
    question: 'Make reading groups for next week',
    answer:
      'Group by what each child is working on: word building (Chiamaka N., Emeka U., Aisha B., Oluwaseun D.), sounds with stories read aloud (Bola K., Yakubu M., Adaeze W.), talking about stories (Kelechi I., Fatima Z., Olamide R., Chinedu P.), and echo reading together (Halima G., Ifeanyi J., Yetunde F.). Children on track can read longer stories in pairs.',
  },
];
