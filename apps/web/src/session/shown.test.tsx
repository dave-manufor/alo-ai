import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { accountStore } from '../account/store';
import SessionPage from '../pages/SessionPage';
import { startSessionScreen, stubMic } from '../test/mic';
import type { SessionDriver } from './driver';
import { fixtureClips, fixturePassage } from './fixtureDriver';
import { encodeClientMessage, shownAck, type ClientMessage } from './protocol';

const v2 = { schema_version: 2 as const };

describe('the shown message', () => {
  it('names the story that is on the screen, at the protocol version', () => {
    expect(shownAck('bank_p3_market_day')).toEqual({
      schema_version: 3,
      cmd: 'shown',
      passage_id: 'bank_p3_market_day',
    });
    const bytes = encodeClientMessage(shownAck('p1'));
    expect(JSON.parse(new TextDecoder().decode(bytes))).toEqual({
      schema_version: 3,
      cmd: 'shown',
      passage_id: 'p1',
    });
  });
});

describe('the session screen tells the agent when the story is up', () => {
  const sent: ClientMessage[] = [];

  beforeEach(() => {
    sent.length = 0;
    stubMic();
    localStorage.clear();
    accountStore.resetForTests();
  });

  function driver(): SessionDriver {
    return {
      start: (sink) => {
        void (async () => {
          await sink({ ...v2, cmd: 'clip_list', clips: fixtureClips });
          await sink({ ...v2, cmd: 'step', step: 'READING' });
          await sink({ ...v2, cmd: 'play', clip_id: 'mic_check_prompt' });
          await sink({ ...v2, cmd: 'show_passage', ...fixturePassage });
        })();
      },
      send: () => undefined,
      stop: () => undefined,
      ack: (message) => void sent.push(message),
    };
  }

  it('sends shown after the story is drawn, and only after the instruction has played', async () => {
    accountStore.signIn('google');
    const { child } = accountStore.addChildWithConsent({
      firstName: 'Adaeze',
      primaryClass: 3,
      birthYear: 2017,
      attested: true,
      trainingOptIn: false,
    });
    render(
      <MemoryRouter initialEntries={[`/session/${child.child_id}`]}>
        <Routes>
          <Route path="/session/:childId" element={<SessionPage createDriver={driver} />} />
        </Routes>
      </MemoryRouter>,
    );
    startSessionScreen();
    await screen.findAllByText(fixturePassage.title);
    await waitFor(() => expect(sent.map((m) => m.cmd)).toEqual(['played', 'shown']));
    expect(sent[1]).toEqual({
      schema_version: 3,
      cmd: 'shown',
      passage_id: fixturePassage.passage_id,
    });
  });
});
