"""Test bootstrap.

Makes ``src/`` importable without an install, so ``pytest`` works from a fresh
checkout as well as from ``pip install -e .``. CI installs the package, so this
is a local-development convenience only; it never affects the installed layout.

It also provides an exec-allowed scratch root for the fake-``wine`` shim used
by the launcher tests. CI runs on an exec-allowed ``/tmp``, but the
maintainer's sandbox mounts ``/tmp`` ``noexec``; a script the tests must exec
cannot live there, so the root is probed and a repo-local fallback is used
when ``/tmp`` refuses execution.

Every test also runs with the developer's environment detached from the
launcher's install lookup (see ``isolated_user_environment`` below): the suite
must stay green when it is run against a real install, because that is how the
wrapper is verified against retail data.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def isolated_user_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Detach the launcher's install lookup from the machine running the tests.

    Resolution order is ``--game-dir`` -> ``$DISCIPLES_GAME_DIR`` -> ``game_dir``
    in the per-user config file (``cli.config_path``). A developer who exports a
    real install -- which is exactly how the wrapper is checked against retail
    data -- would otherwise have that install leak into tests that expect their
    own synthetic tree, or expect no install at all. Drop the variable and point
    every notion of a home/config directory at a throwaway tree, on both
    platforms, so nothing can read the developer's ``config.ini`` either.

    A test that wants an env var or a config file sets one itself; that is then
    the only thing in play.
    """
    monkeypatch.delenv("DISCIPLES_GAME_DIR", raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))  # POSIX ``Path.home()``
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows ``Path.home()``
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))


def _exec_allowed_scratch() -> Path:
    probe_dir = Path(tempfile.mkdtemp(prefix="disciples-execprobe-"))
    probe = probe_dir / "probe.sh"
    probe.write_text("#!/bin/sh\nexit 0\n")
    probe.chmod(0o755)
    try:
        subprocess.run([str(probe)], check=True, capture_output=True)
        exec_ok = True
    except (OSError, subprocess.CalledProcessError):
        exec_ok = False

    if exec_ok:
        # The default temp dir executes; keep it (drop only the probe script)
        # so the returned directory stays alive for the fixtures that write
        # into it. Returning a directory that a ``finally`` then deletes is the
        # bug this branch exists to avoid.
        probe.unlink(missing_ok=True)
        return probe_dir

    shutil.rmtree(probe_dir, ignore_errors=True)
    fallback = Path(__file__).resolve().parent.parent / ".pytest-scratch"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


@pytest.fixture(scope="session")
def exec_tmp_root() -> Path:
    """A writable directory whose files can be executed (see module docstring)."""
    return _exec_allowed_scratch()
