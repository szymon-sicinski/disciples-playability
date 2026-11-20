"""Scaffold smoke tests: the package installs, imports and answers ``--help``.

Nothing here touches a game installation, and no fixture contains game bytes.
The INI model, launcher and wrapper tests arrive with their milestones.
"""

import disciples_play
from disciples_play.__main__ import main


def test_version_is_a_non_empty_string() -> None:
    assert isinstance(disciples_play.__version__, str)
    assert disciples_play.__version__.strip()


def test_help_exits_zero(capsys) -> None:
    assert main(["--help"]) == 0
    assert "usage: disciples-play" in capsys.readouterr().out


def test_unknown_argument_exits_two(capsys) -> None:
    assert main(["--not-a-flag"]) == 2
    assert "unrecognised argument" in capsys.readouterr().err
