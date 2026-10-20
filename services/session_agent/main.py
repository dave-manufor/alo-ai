"""Entry point: python -m services.session_agent.main dev|start|console.

Checks the settings first (ALO_ENV=local is refused on Cloud Run), then hands
over to the LiveKit Agents CLI: `start` in production, `dev` locally with
reload, `console` to talk to the agent from this machine's microphone.
"""

import os
import sys
from collections.abc import Callable, Mapping, Sequence

from . import config

MODES = ("dev", "start", "console")


def _run_worker(args: Sequence[str]) -> None:  # pragma: no cover - starts the worker
    from . import livekit_worker

    sys.argv = [sys.argv[0], *args]
    livekit_worker.run()


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    run: Callable[[Sequence[str]], None] = _run_worker,
) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in MODES:
        print("usage: python -m services.session_agent.main dev|start|console", file=sys.stderr)
        return 2
    try:
        config.load(os.environ if env is None else env)
    except config.ConfigError as error:
        print(f"refusing to start: {error}", file=sys.stderr)
        return 1
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
