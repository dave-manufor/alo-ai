"""Entry point: python -m services.session_agent.main dev|start.

This PR adds the settings check and the state machine only. The LiveKit worker
is wired in the next PR.
"""

import os
import sys
from collections.abc import Mapping, Sequence

from . import config


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("dev", "start"):
        print("usage: python -m services.session_agent.main dev|start", file=sys.stderr)
        return 2
    try:
        config.load(os.environ if env is None else env)
    except config.ConfigError as error:
        print(f"refusing to start: {error}", file=sys.stderr)
        return 1
    print("settings ok; the LiveKit worker is not wired yet", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
