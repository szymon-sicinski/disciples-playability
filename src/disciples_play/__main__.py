"""Entry point for ``disciples-play`` and ``python -m disciples_play``.

This is a stub. It exists so the console script, the packaging metadata and
the CI matrix are exercised from the first commit; it does not touch a game
installation and rewrites nothing. The real subcommands arrive in:

* M1 - the INI model and rewrite core (``disciples_play.ini``)
* M2 - ``disciples-play --game-dir DIR [--dry-run] [--print-command]``
* M3 - the ``cnc-ddraw`` preset and its pinned fetch
* M4 - ``disciples-play doctor --game-dir DIR``

See ``docs/plans/00-playability-plan.md`` for the full specification.
"""

from __future__ import annotations

import sys

from . import __version__

USAGE = """\
usage: disciples-play [-h] [--version]

Portability and comfort wrapper for Disciples: Sacred Lands Gold (1999).

This build is a scaffold: the launcher, the INI rewriter and the cnc-ddraw
preset are not implemented yet. See docs/plans/00-playability-plan.md.

options:
  -h, --help     show this message and exit
  --version      show the version and exit
"""


def main(argv: list[str] | None = None) -> int:
    """Print usage/version and return a process exit code.

    Exit codes so far: 0 on success, 2 on an unrecognised argument (the
    convention ``argparse`` uses, so it stays consistent once the real parser
    replaces this stub).
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or args[0] in {"-h", "--help"}:
        print(USAGE, end="")
        return 0

    if args[0] == "--version":
        print(f"disciples-play {__version__}")
        return 0

    print(f"disciples-play: unrecognised argument {args[0]!r}", file=sys.stderr)
    print("try 'disciples-play --help'", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
