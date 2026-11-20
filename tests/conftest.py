"""Test bootstrap.

Makes ``src/`` importable without an install, so ``pytest`` works from a fresh
checkout as well as from ``pip install -e .``. CI installs the package, so this
is a local-development convenience only; it never affects the installed layout.

It also provides an exec-allowed scratch root for the fake-``wine`` shim used
by the launcher tests. CI runs on an exec-allowed ``/tmp``, but the
maintainer's sandbox mounts ``/tmp`` ``noexec``; a script the tests must exec
cannot live there, so the root is probed and a repo-local fallback is used
when ``/tmp`` refuses execution.
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
