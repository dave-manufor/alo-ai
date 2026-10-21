import type { AgentMessage } from './protocol';

// The fixture driver stands in for the Session Agent in the MVP phase.
// It emits real protocol v2 messages in the agent's order; the screen
// only ever follows those messages (step, clip_list, play, show_passage,
// hide_passage). A child's tap on the mic means "the child has spoken" —
// the agent (here, this driver) decides what happens next, exactly as
// the live driver will when it detects the end of a turn. The told word
// is the driver's decision during reading, never a button.
//
// Clip texts mirror PR #24's clips: the bubble shows the playing clip's
// exact words; the listening story (not used here) would carry null.
const v2 = { schema_version: 2 as const };

export const fixtureClips = [
  {
    clip_id: 'interest_prompt',
    url: '/clips/interest_prompt.mp3',
    text: 'Before we read, tell me: what kind of stories do you like?',
  },
  {
    clip_id: 'count_prompt',
    url: '/clips/count_prompt.mp3',
    text: 'Count with me: one, two, three, four, five.',
  },
  {
    clip_id: 'story_ready',
    url: '/clips/story_ready.mp3',
    text: 'Your story is almost ready!',
  },
  {
    clip_id: 'word_market',
    url: '/clips/words/market.mp3',
    text: 'That word is market.',
  },
  {
    clip_id: 'retell_prompt',
    url: '/clips/retell_prompt.mp3',
    text: 'In your own words, tell me everything you remember from the story.',
  },
  {
    clip_id: 'question_1',
    url: '/clips/question_1.mp3',
    text: 'What did Ada choose at the market?',
  },
  {
    clip_id: 'question_2',
    url: '/clips/question_2.mp3',
    text: 'Why did Ada smile at the end?',
  },
  {
    clip_id: 'close_prompt',
    url: '/clips/close_prompt.mp3',
    text: 'You did a great job today!',
  },
];

/** The v2 fixture story (fixtures/contracts/session_protocol.json in #24). */
export const fixturePassage = {
  passage_id: 'bank_p3_market_day',
  title: 'Market Day',
  sentences: [
    'Ada and Mama went to the market.',
    'Ada saw a red hat.',
    'It cost too much.',
    'Ada smiled and chose a blue hat.',
  ],
  arl: 3,
};

export type DriverEvent =
  | 'session_started'
  | 'topic_chosen'
  | 'child_spoke'
  | 'reading_pause';

/** Messages the agent sends in reply to one driver event. */
export function messagesFor(event: DriverEvent, step: string | null): AgentMessage[] {
  switch (event) {
    case 'session_started':
      return [
        { ...v2, cmd: 'clip_list', clips: fixtureClips },
        { ...v2, cmd: 'step', step: 'INTEREST_CHAT' },
        { ...v2, cmd: 'play', clip_id: 'interest_prompt' },
      ];
    case 'topic_chosen':
      return [
        { ...v2, cmd: 'step', step: 'MIC_CHECK' },
        { ...v2, cmd: 'play', clip_id: 'count_prompt' },
      ];
    case 'reading_pause':
      // The agent's told-word decision after a pause on a word (PRD 4.1).
      return [{ ...v2, cmd: 'play', clip_id: 'word_market' }];
    case 'child_spoke':
      switch (step) {
        case 'MIC_CHECK':
          return [
            { ...v2, cmd: 'play', clip_id: 'story_ready' },
            { ...v2, cmd: 'step', step: 'READING' },
            { ...v2, cmd: 'show_passage', ...fixturePassage },
          ];
        case 'READING':
          return [
            { ...v2, cmd: 'hide_passage' },
            { ...v2, cmd: 'step', step: 'RETELL' },
            { ...v2, cmd: 'play', clip_id: 'retell_prompt' },
          ];
        case 'RETELL':
          return [
            { ...v2, cmd: 'step', step: 'QUESTIONS' },
            { ...v2, cmd: 'play', clip_id: 'question_1' },
          ];
        case 'QUESTIONS':
          return [{ ...v2, cmd: 'play', clip_id: 'question_2' }];
        default:
          return [];
      }
  }
}

/** After the second question answer, the agent closes the session. */
export function closingMessages(): AgentMessage[] {
  return [
    { ...v2, cmd: 'step', step: 'CLOSE' },
    { ...v2, cmd: 'play', clip_id: 'close_prompt' },
  ];
}
