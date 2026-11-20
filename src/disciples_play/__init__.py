"""Disciples: Sacred Lands Gold playability pack.

A wrapper for a game the user already owns: it makes the installation
portable, applies a curated ``cnc-ddraw`` preset and reports what it finds.
It contains no game data and never reads game content as data -- only paths,
sizes and an INI file it rewrites.

The public surface is deliberately tiny while the scaffold is in place; the
INI model (``disciples_play.ini``), the launcher and the wrapper preset land
in milestones M1-M3 of ``docs/plans/00-playability-plan.md``.
"""

from __future__ import annotations

__version__ = "0.1.0.dev0"

__all__ = ["__version__"]
