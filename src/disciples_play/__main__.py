"""Entry point for ``disciples-play`` and ``python -m disciples_play``.

Both the console script (``disciples_play.__main__:main``) and ``python -m
disciples_play`` resolve to :func:`disciples_play.cli.main`, so the two behave
identically. The CLI itself lives in :mod:`disciples_play.cli`; the install
resolution and launch live in :mod:`disciples_play.launch`; the read-only data
report lives in :mod:`disciples_play.data`.
"""

from __future__ import annotations

from .cli import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
