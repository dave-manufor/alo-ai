import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { accountStore } from '../account/store';
import ChildrenPage from '../pages/ChildrenPage';
import SessionPage from '../pages/SessionPage';
import { createClipCache } from './clipCache';
import { missingAck, parseAgentMessage, playedAck } from './protocol';
import {
  applyAgentMessage,
  initialSessionState,
  readingLevelForArl,
} from './sessionState';

function signedInChild(): string {
  accountStore.signIn('google');
  const { child } = accountStore.addChildWithConsent({
    firstName: 'Adaeze',
    primaryClass: 3,
    birthYear: 2017,
    attested: true,
    trainingOptIn: false,
  });
  return child.child_id;
}

describe('session protocol v2 (PR #24)', () => {
  it('parses v2 messages and drops v1 and anything off-contract', () => {
    expect(
      parseAgentMessage(
        '{"schema_version":2,"cmd":"show_passage","passage_id":"p1","title":"T","sentences":["Ada ran."],"arl":3}',
      ),
    ).toMatchObject({ cmd: 'show_passage', arl: 3 });
    expect(parseAgentMessage({ schema_version: 1, cmd: 'step', step: 'READING' })).toBeNull();
    expect(parseAgentMessage({ schema_version: 2, cmd: 'show_score', value: 95 })).toBeNull();
    expect(
      parseAgentMessage({
        schema_version: 2,
        cmd: 'show_passage',
        passage_id: 'p1',
        title: 'T',
        sentences: ['Ada ran.'],
        arl: 3,
        items: [],
      }),
    ).not.toBeNull(); // extra keys are tolerated by the parser; the schema forbids them producer-side
    expect(playedAck('word_market')).toEqual({
      schema_version: 2,
      cmd: 'played',
      clip_id: 'word_market',
    });
  });

  it('follows step, shows the story with its level size, clears reconnecting on any message', () => {
    let state = applyAgentMessage(initialSessionState, {
      schema_version: 2,
      cmd: 'reconnecting',
    });
    expect(state.reconnecting).toBe(true);
    state = applyAgentMessage(state, { schema_version: 2, cmd: 'step', step: 'READING' });
    expect(state.reconnecting).toBe(false);
    expect(state.step).toBe('READING');
    state = applyAgentMessage(state, {
      schema_version: 2,
      cmd: 'show_passage',
      passage_id: 'bank_p3_market_day',
      title: 'Market Day',
      sentences: ['Ada and Mama went to the market.'],
      arl: 3,
    });
    expect(state.passageVisible).toBe(true);
    expect(readingLevelForArl(1)).toBe('p1');
    expect(readingLevelForArl(3)).toBe('p3');
    expect(readingLevelForArl(9)).toBe('p5');
    state = applyAgentMessage(state, { schema_version: 2, cmd: 'hide_passage' });
    expect(state.passageVisible).toBe(false);
  });

  it('shows the playing clip text, and never updates the bubble for a null-text clip', () => {
    const withText = applyAgentMessage(
      initialSessionState,
      { schema_version: 2, cmd: 'play', clip_id: 'word_market' },
      () => 'That word is market.',
    );
    expect(withText.bubbleText).toBe('That word is market.');
    const listening = applyAgentMessage(withText, { schema_version: 2, cmd: 'play', clip_id: 'listening_story' }, () => null);
    expect(listening.bubbleText).toBe('That word is market.');
  });
});

describe('clip cache (PRD 4.4, protocol v2)', () => {
  it('acks played only after playback finishes, waits for in-flight downloads, never acks at download time', async () => {
    let finishPlayback: () => void = () => undefined;
    const cache = createClipCache({
      load: async (url) => (url.includes('bad') ? undefined : `blob:${url}`),
      player: {
        play: () =>
          new Promise<void>((resolve) => {
            finishPlayback = resolve;
          }),
      },
    });

    // A failed download produces no ack at all (it retries quietly).
    await cache.downloadAll([
      { clip_id: 'greeting_1', url: '/clips/greeting_1.mp3', text: 'Hello.' },
      { clip_id: 'bad_1', url: '/clips/bad_1.mp3', text: null },
    ]);
    expect(cache.has('greeting_1')).toBe(true);
    expect(cache.has('bad_1')).toBe(false);

    const ackPromise = cache.play('greeting_1');
    let acked = false;
    void ackPromise.then(() => {
      acked = true;
    });
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(acked).toBe(false); // still playing: no played yet
    finishPlayback();
    await expect(ackPromise).resolves.toEqual(playedAck('greeting_1'));

    await expect(cache.play('bad_1')).resolves.toEqual(missingAck('bad_1'));
    await expect(cache.play('never_seen')).resolves.toEqual(missingAck('never_seen'));
  });
});

describe('kid session screen (PRD 4.1, agent-driven)', () => {
  beforeEach(() => {
    localStorage.clear();
    accountStore.resetForTests();
  });

  it('redirects away without a per-child consent record', () => {
    render(
      <MemoryRouter initialEntries={['/session/child_nope']}>
        <Routes>
          <Route path="/session/:childId" element={<SessionPage />} />
          <Route path="/children" element={<ChildrenPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Sign in first' })).toBeInTheDocument();
  });

  it('follows the agent from welcome to close, with no word-help button and no scores', async () => {
    const childId = signedInChild();
    const { container } = render(
      <MemoryRouter initialEntries={[`/session/${childId}`]}>
        <Routes>
          <Route path="/session/:childId" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: /Ààlọ̀/ }));
    // The bubble shows the interest clip's exact text.
    expect(
      await screen.findByText('Before we read, tell me: what kind of stories do you like?'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /help with a word/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Animals/ }));
    fireEvent.click(screen.getByRole('button')); // mic: the child counted
    expect(await screen.findByText(/Ada and Mama went to the market/)).toBeInTheDocument();
    // The agent tells a word during reading; the bubble shows the clip text.
    expect(await screen.findByText('That word is market.')).toBeInTheDocument();

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[buttons.length - 1]); // mic: reading turn ended
    expect(await screen.findByText(/In your own words, tell me/)).toBeInTheDocument();
    expect(screen.queryByText(/Ada and Mama went to the market/)).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button').at(-1)!);
    expect(await screen.findByText('What did Ada choose at the market?')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button').at(-1)!);
    expect(await screen.findByText('Why did Ada smile at the end?')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button').at(-1)!);
    expect(await screen.findByText('You did a great job today!')).toBeInTheDocument();

    // Collect stars stays in kid mode: no route away, no numbers anywhere.
    fireEvent.click(screen.getByRole('button', { name: /Collect stars/ }));
    expect(screen.getByText('You did a great job today!')).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\d+\s?%|score|timer|words a minute/i);
  });
});
