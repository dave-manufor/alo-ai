# Session Agent

LiveKit Agents worker that runs a reading session (PRD 4). Rules for working here are in `AGENTS.md`.

## State machine

`machine/step.py` is a pure function: `step(state, event) -> (state, actions)`. It does no I/O, reads no clock and computes no score. `driver.py` turns LiveKit, speech and timer callbacks into events and runs the actions.

- `machine/types.py`: state, events and actions.
- `machine/profiles.py`: `standard` and `demo` profiles and the protocol timings. No [CAL] values: the listening decision comes from `grade:quick`.
- Timers are named `<kind>:<task_seq>`; a timer from an earlier task is ignored.
- In `live_first` the prompts are `SpeakLive` (with a clip fallback) while Live is healthy. "That word is X." and the listening story are always clips.

## The worker

- `livekit_worker.py`: one LiveKit job per session room. Microphone audio (16 kHz mono) goes to the recorder, Silero VAD and Chirp 3 streaming STT; their events, data-channel acks (topic `aloai.session`), connection changes and timers go to the driver. No logic here.
- `driver.py`: runs the machine and carries out each action through small ports (data channel, recorder, timers, quick grader, passages, events, records). Tested end to end with fakes in `tests/test_driver.py`.
- `turns.py`: end of a turn from the VAD (an answer ends after a 1.5 s pause, the retell after 4 s; 8 s with no speech is a SILENCE). `mic_check.py`: the count-to-five levels. `intents.py`: "stop" and "say it again" from short utterances, outside the reading.
- `quick_grade.py`: the `grade:quick` client (every item, empty transcript when unanswered; only a complete decision reaches the machine). `passages.py`: the bank, a READ passage with its paired listening passage.
- `recorder.py`: per-turn FLAC. `cloud.py`: Cloud Storage, Firestore and Pub/Sub (emulators locally). `metadata.py`: the session details the room is dispatched with (to agree with W1).
- `clips/catalog.py`: clip ids to clip-store objects and the URLs the web app caches.

Not yet: the Passage Generator (every session uses the bank passage and is flagged `FALLBACK_PASSAGE`), the Gemini Live conductor (`SpeakLive` plays the clip) and LiveKit's turn detector (it runs inside the LLM pipeline, so it comes with the conductor).

## Building blocks

- `clips/`: word keys (`keys.py`), the clip store layout and only-if-absent write (`store.py`), and seeding (`seed.py`).
- `position_tracker.py`: follows the child through the passage from speech-to-text partials; reports stalls, progress and the end.
- `protocol.py`: data-channel messages for the web app (`schemas/session_protocol.schema.json`).
- `recording.py`: names each turn's audio object (UUID v4) and keeps the turn list.
- `events.py`, `session_store.py`: build the published events and Firestore records the contracts describe.

## Run the tests

Python 3.11. From the repo root:

```
uv venv -p 3.11 services/session_agent/.venv
uv pip install --python services/session_agent/.venv/bin/python -r services/session_agent/requirements-dev.txt
services/session_agent/.venv/bin/pytest -c services/session_agent/pyproject.toml services/session_agent \
  --cov=services.session_agent.machine --cov-fail-under=100
ruff check services/session_agent
```

The state machine must stay at 100% line coverage; the service as a whole at 80% or more.

## Run

`python -m services.session_agent.main dev|start|console` checks the settings (it refuses `ALO_ENV=local` when `K_SERVICE` is set), then starts the LiveKit worker. It needs `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`, and the buckets and topic from `docs/LOCAL_DEV.md`. Locally, set `BANK_DIR=fixtures/contracts` to read bank passages from files and `CLIPS_BASE_URL` to where the browser can fetch clips. `AI_MODE=fixtures` has no speech to text, so the reading runs to its cap; `AI_MODE=live` uses Chirp 3 and spends from the shared budget.

The room is dispatched with JSON metadata `{session_id, child_id, context, capture_mode?, passage_id?}` (`metadata.py`).
