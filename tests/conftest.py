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
    try:
        probe = probe_dir / "probe.sh"
        probe.write_text("#!/bin/sh\nexit 0\n")
        probe.chmod(0o755)
        try:
            subprocess.run([str(probe)], check=True, capture_output=True)
            return probe_dir
        except (OSError, subprocess.CalledProcessError):
            pass
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)

    fallback = Path(__file__).resolve().parent.parent / ".pytest-scratch"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


@pytest.fixture(scope="session")
def exec_tmp_root() -> Path:
    """A writable directory whose files can be executed (see module docstring)."""
    return _exec_allowed_scratch()
