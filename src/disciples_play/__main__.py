"""Entry point for ``disciples-play`` and ``python -m disciples_play``.

Subcommands:

* ``data`` (M5) -- a read-only structural report of the game's data layer:
  directory inventory, dBase III table geometry, ``MQDB`` container
  hypothesis votes, and digests of the plain-text formats.  It never decodes
  an image to pixels, never dumps palette entries, and never prints file
  hashes.

The launcher, INI rewriter and cnc-ddraw preset land in M1-M3; see
``docs/plans/00-playability-plan.md`` for the full specification.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__

USAGE = """\
usage: disciples-play [-h] [--version] {data}

Portability and comfort wrapper for Disciples: Sacred Lands Gold (1999).

subcommands:
  data    print a read-only structural report of the game's data files

options:
  -h, --help     show this message and exit
  --version      show the version and exit
"""


def _data_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="disciples-play data",
        description="Read-only structural report of the game's data files.",
    )
    parser.add_argument("--game-dir", required=True, help="path to the game install")
    parser.add_argument(
        "--json", action="store_true", help="emit the report as JSON instead of text"
    )
    args = parser.parse_args(argv)

    from .data import build_report, render_text

    try:
        report = build_report(args.game_dir)
    except NotADirectoryError as exc:
        print(f"disciples-play data: {exc}", file=sys.stderr)
        return 2

    if args.json:
        _emit(json.dumps(report, indent=2))
    else:
        _emit(render_text(report))
    return 0


def _emit(text: str) -> None:
    """Write ``text`` to stdout, tolerating an early-closed pipe (``| head``)."""

    try:
        print(text)
        sys.stdout.flush()
    except BrokenPipeError:
        # stdout was closed by a consumer like `head`; that is not an error.
        try:
            sys.stdout.close()
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    """Dispatch a subcommand and return a process exit code.

    Exit codes: 0 on success, 2 on an unrecognised argument or a bad install
    directory (the convention ``argparse`` uses).
    """

    args = sys.argv[1:] if argv is None else argv

    if not args or args[0] in {"-h", "--help"}:
        print(USAGE, end="")
        return 0

    if args[0] == "--version":
        print(f"disciples-play {__version__}")
        return 0

    if args[0] == "data":
        return _data_main(args[1:])

    print(f"disciples-play: unrecognised argument {args[0]!r}", file=sys.stderr)
    print("try 'disciples-play --help'", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
