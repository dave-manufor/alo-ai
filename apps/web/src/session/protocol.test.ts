import { describe, expect, it } from 'vitest';
import {
  decodeAgentData,
  encodeClientMessage,
  missingAck,
  parseAgentMessage,
  playedAck,
} from './protocol';

const v2 = { schema_version: 2 };

describe('protocol v2 parsing', () => {
  it('accepts every agent command in its valid shape (as an object or a JSON string)', () => {
    const clip = { clip_id: 'a', url: '/a.mp3', text: null };
    expect(parseAgentMessage({ ...v2, cmd: 'clip_list', clips: [clip] })?.cmd).toBe('clip_list');
    expect(parseAgentMessage(JSON.stringify({ ...v2, cmd: 'play', clip_id: 'a' }))?.cmd).toBe('play');
    expect(parseAgentMessage({ ...v2, cmd: 'step', step: 'READING' })?.cmd).toBe('step');
    expect(
      parseAgentMessage({
        ...v2,
        cmd: 'show_passage',
        passage_id: 'p',
        title: 'T',
        sentences: ['One.'],
        arl: 3,
      })?.cmd,
    ).toBe('show_passage');
    expect(parseAgentMessage({ ...v2, cmd: 'hide_passage' })?.cmd).toBe('hide_passage');
    expect(parseAgentMessage({ ...v2, cmd: 'reconnecting' })?.cmd).toBe('reconnecting');
  });

  it('drops anything off-contract', () => {
    const bad: unknown[] = [
      null,
      42,
      'not json',
      { schema_version: 1, cmd: 'step', step: 'READING' },
      { ...v2, cmd: 7 },
      { ...v2, cmd: 'score_now' },
      { ...v2, cmd: 'clip_list', clips: 'nope' },
      { ...v2, cmd: 'clip_list', clips: [{ clip_id: '', url: '/a', text: null }] },
      { ...v2, cmd: 'clip_list', clips: [{ clip_id: 'a', url: 1, text: null }] },
      { ...v2, cmd: 'clip_list', clips: [{ clip_id: 'a', url: '/a', text: 5 }] },
      { ...v2, cmd: 'play', clip_id: '' },
      { ...v2, cmd: 'step', step: 'DANCING' },
      { ...v2, cmd: 'show_passage', passage_id: 'p', title: 'T', sentences: [], arl: 3 },
      { ...v2, cmd: 'show_passage', passage_id: 'p', title: 'T', sentences: ['x'], arl: 13 },
      { ...v2, cmd: 'show_passage', passage_id: 'p', title: 'T', sentences: [''], arl: 3 },
    ];
    for (const raw of bad) expect(parseAgentMessage(raw)).toBeNull();
  });

  it('encodes acks and decodes data-channel bytes', () => {
    const bytes = encodeClientMessage(playedAck('a'));
    expect(JSON.parse(new TextDecoder().decode(bytes))).toEqual({ ...v2, cmd: 'played', clip_id: 'a' });
    expect(missingAck('b')).toEqual({ ...v2, cmd: 'missing', clip_id: 'b' });
    const step = new TextEncoder().encode(JSON.stringify({ ...v2, cmd: 'step', step: 'RETELL' }));
    expect(decodeAgentData(step)?.cmd).toBe('step');
    expect(decodeAgentData(new TextEncoder().encode('{not json'))).toBeNull();
  });
});
