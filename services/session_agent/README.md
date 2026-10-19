# Session Agent

LiveKit Agents worker that runs a reading session (PRD 4). Rules for working here are in `AGENTS.md`.

## State machine

`machine/step.py` is a pure function: `step(state, event) -> (state, actions)`. It does no I/O, reads no clock and computes no score. An adapter (next PR) turns LiveKit, speech and timer callbacks into events and runs the actions.

- `machine/types.py`: state, events and actions.
- `machine/profiles.py`: `standard` and `demo` profiles and the protocol timings. No [CAL] values: the listening decision comes from `grade:quick`.
- Timers are named `<kind>:<task_seq>`; a timer from an earlier task is ignored.
- In `live_first` the prompts are `SpeakLive` (with a clip fallback) while Live is healthy. "That word is X." and the listening story are always clips.

## Building blocks (no network; real Cloud clients are wired in with the worker)

- `clips/`: word keys (`keys.py`), the clip store layout and only-if-absent write (`store.py`), and seeding (`seed.py`).
- `position_tracker.py`: follows the child through the passage from speech-to-text partials; reports stalls, progress and the end.
- `protocol.py`: data-channel messages for the web app (`schemas/session_protocol.schema.json`).
- `recording.py`: names each turn's audio object (UUID v4) and keeps the turn list.
- `events.py`, `session_store.py`: build the published events and Firestore records the contracts describe.

## Run the tests

Python 3.11. From the repo root:

```
python3.11 -m venv .venv
.venv/bin/pip install pytest "pytest-cov>=5" "jsonschema[format]" ruff
.venv/bin/python -m pytest -c services/session_agent/pyproject.toml services/session_agent \
  --cov=services.session_agent.machine --cov-fail-under=100
.venv/bin/ruff check services/session_agent
```

The state machine must stay at 100% line coverage.

## Run

`python -m services.session_agent.main dev|start` checks the settings and refuses to start with `ALO_ENV=local` when `K_SERVICE` is set. The worker itself is not wired yet.
