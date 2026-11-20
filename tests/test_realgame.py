"""Optional tests that run against a real install.

These are marked ``realgame`` and are skipped unless ``DISCIPLES_GAME_DIR``
points at a real install.  The normal CI run (``pytest -q`` with the variable
unset) skips them cleanly; a maintainer with a copy of the game can run them
with::

    DISCIPLES_GAME_DIR=/path/to/game pytest -m realgame
"""

from __future__ import annotations

import os

import pytest

from disciples_play.data import build_report

GAME_DIR = os.environ.get("DISCIPLES_GAME_DIR")


@pytest.mark.realgame
@pytest.mark.skipif(not GAME_DIR, reason="DISCIPLES_GAME_DIR not set")
def test_real_install_reports_structure() -> None:
    report = build_report(GAME_DIR)

    # Every dBase table that is present must close its header arithmetic.
    assert report["inventory"]["total_files"] > 0
    for d in report["dbf"]:
        assert d["arithmetic_ok"], f"{d['path']} does not close"


@pytest.mark.realgame
@pytest.mark.skipif(not GAME_DIR, reason="DISCIPLES_GAME_DIR not set")
def test_real_mqdb_winners_are_little_endian_at_28_size_16() -> None:
    report = build_report(GAME_DIR)
    for m in report["mqdb"]:
        assert m["is_mqdb"], f"{m['path']} is not MQDB"
        assert m["winner"]["start_offset"] == 28
        assert m["winner"]["endian"] == "little"
        assert m["winner"]["size_offset"] == 16
        assert m["winner"]["tiles_exactly"], f"{m['path']} does not tile"
