import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import SessionPage from '../pages/SessionPage';
import { createClipCache } from './clipCache';
import { missingAck, parseAgentMessage, playedAck } from './protocol';
import {
  applyAgentMessage,
  initialSessionState,
  sampleStory,
} from './sessionState';

describe('session protocol (schemas/session_protocol.schema.json)', () => {
  it('parses agent messages and drops anything off-contract', () => {
    expect(
      parseAgentMessage('{"schema_version":1,"cmd":"show_passage","passage_id":"p1"}'),
    ).toEqual({ schema_version: 1, cmd: 'show_passage', passage_id: 'p1' });
    expect(parseAgentMessage({ schema_version: 2, cmd: 'show_passage', passage_id: 'p1' })).toBeNull();
    expect(parseAgentMessage({ schema_version: 1, cmd: 'show_score', value: 95 })).toBeNull();
    expect(parseAgentMessage('not json')).toBeNull();
    expect(playedAck('word_market')).toEqual({
      schema_version: 1,
      cmd: 'played',
      clip_id: 'word_market',
    });
    expect(missingAck('word_market').cmd).toBe('missing');
  });

  it('shows and hides the passage only on agent commands, and flags reconnecting', () => {
    let state = applyAgentMessage(initialSessionState, {
      schema_version: 1,
      cmd: 'show_passage',
      passage_id: sampleStory.passageId,
    });
    expect(state.passageVisible).toBe(true);
    state = applyAgentMessage(state, { schema_version: 1, cmd: 'hide_passage' });
    expect(state.passageVisible).toBe(false);
    state = applyAgentMessage(state, { schema_version: 1, cmd: 'reconnecting' });
    expect(state.reconnecting).toBe(true);
  });
});

describe('clip cache (PRD 4.4)', () => {
  it('downloads before reading and answers played or missing honestly', async () => {
    const played: string[] = [];
    const cache = createClipCache({
      load: async (url) => !url.includes('missing'),
      playClip: (clip_id) => played.push(clip_id),
    });
    const missing = await cache.downloadAll([
      { clip_id: 'greeting_1', url: '/clips/greeting_1.mp3' },
      { clip_id: 'missing_1', url: '/clips/missing_1.mp3' },
    ]);
    expect(missing).toEqual(['missing_1']);
    expect(cache.play('greeting_1')).toEqual(playedAck('greeting_1'));
    expect(cache.play('missing_1')).toEqual(missingAck('missing_1'));
    expect(played).toEqual(['greeting_1']);
  });
});

describe('kid session screen (PRD 4.1, fixture-driven)', () => {
  it('walks welcome to reading to done, with no score, timer or percentage', async () => {
    const { container } = render(
      <MemoryRouter>
        <SessionPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Ààlọ̀!' }));
    fireEvent.click(screen.getByRole('button', { name: 'Animals' }));
    fireEvent.click(screen.getByRole('button', { name: /i counted/i }));
    expect(await screen.findByText(/Ada had a small brown goat/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /help with a word/i }));
    expect(screen.getByText(/That word is market\. Keep going!/)).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /i have finished/i })[0]);
    expect(screen.queryByText(/Ada had a small brown goat/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /i have finished/i }));
    expect(screen.getByText('What did Ada take to the market?')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /next question/i }));
    fireEvent.click(screen.getByRole('button', { name: /finish/i }));
    expect(screen.getByText('You did a great job today!')).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\d+\s?%|score|timer/i);
  });
});
