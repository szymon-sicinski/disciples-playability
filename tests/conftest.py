"""Test bootstrap.

Makes ``src/`` importable without an install, so ``pytest`` works from a fresh
checkout as well as from ``pip install -e .``. CI installs the package, so this
is a local-development convenience only; it never affects the installed layout.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
