"""Install resolution, INI rewrite orchestration and process launch.

This module has no CLI concerns (no ``argparse``); :mod:`disciples_play.cli`
parses arguments and drives these functions. It resolves the install the user
points at -- tolerating a copied retail folder dropped one or two levels down
-- re-points ``Exe/DISCIPLE.INI`` at the install's actual location via M1's
:mod:`disciples_play.ini`, then launches ``wine Exe/Disciple.exe``.

Nothing here reads game content: only paths, one INI file it rewrites, and the
presence of a ``ddraw.dll`` next to the exe (the cnc-ddraw wrapper, staged by
M3) to decide whether to set ``WINEDLLOVERRIDES=ddraw=n,b``. The exit codes are
a contract shared with :mod:`disciples_play.cli` and ``docs/cli.md``:

* ``2`` -- bad or missing install (handled here, raised as :class:`CliError`)
* ``3`` -- rewrite refused (INI not writable, copy-tree target exists)
* ``4`` -- wine not found (launch only)
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import ini

logger = logging.getLogger(__name__)

#: The INI filename, matched case-insensitively: a retail install may hold
#: ``DISCIPLE.INI`` or ``DISCIPLE.ini`` (or, on the maintainer's install, both).
_INI_NAME = "disciple.ini"

#: The cnc-ddraw wrapper DLL, staged next to the exe by M3. Its presence is
#: what decides the ``WINEDLLOVERRIDES`` value at launch.
_DDRAW_DLL = "ddraw.dll"

#: The WINEDLLOVERRIDES value M3 documents, applied only when the wrapper is staged.
_DDRAW_OVERRIDE = "ddraw=n,b"

#: Name of the Wine virtual desktop the game runs in. A constant, not user input.
VIRTUAL_DESKTOP_NAME = "Disciples"
#: The default virtual-desktop size: the game's fullscreen mode.
DEFAULT_VIRTUAL_DESKTOP = (640, 480)
#: Upper bound for either edge, so a typo cannot ask Wine for a 10-metre desktop.
MAX_VIRTUAL_DESKTOP_EDGE = 16384


class CliError(Exception):
    """A user-facing failure carrying its documented process exit code."""

    def __init__(self, exit_code: int, message: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.message = message


def parse_virtual_desktop(value: str) -> tuple[int, int]:
    """Parse ``WIDTHxHEIGHT`` (ASCII digits, one ``x``/``X``) or raise ``CliError`` (exit 2)."""
    error = CliError(
        2,
        f"--virtual-desktop expects WIDTHxHEIGHT, two whole numbers in "
        f"1..{MAX_VIRTUAL_DESKTOP_EDGE} (e.g. 640x480); got {value!r}",
    )
    parts = value.replace("X", "x").split("x")
    if len(parts) != 2:
        raise error
    for part in parts:
        if not part or not (part.isascii() and part.isdigit()):
            raise error
    width, height = int(parts[0]), int(parts[1])
    if not (1 <= width <= MAX_VIRTUAL_DESKTOP_EDGE and 1 <= height <= MAX_VIRTUAL_DESKTOP_EDGE):
        raise error
    return width, height


@dataclass(frozen=True)
class Install:
    """A resolved game install.

    ``root`` is the directory that holds ``Exe/`` and the data folders
    (``Globals/``, ``Imgs1/``, ...); ``exe_dir`` and ``ini_path`` derive from
    it. ``ini_path`` is the actual file on disk, matched case-insensitively.
    """

    root: Path
    exe_dir: Path
    ini_path: Path

    @property
    def exe_path(self) -> Path:
        return self.exe_dir / "Disciple.exe"


# --------------------------------------------------------------------------
# Install resolution
# --------------------------------------------------------------------------


def find_install_roots(candidate: Path) -> list[Path]:
    """Return every directory under ``candidate`` that holds ``Exe/Disciple.exe``.

    ``candidate`` itself is returned when it holds it; otherwise its children
    and grandchildren are searched (the ``find <dir> -maxdepth 2 -name
    Disciple.exe`` shape from the card, but keyed on the *root* that contains
    ``Exe/`` rather than on ``Exe/`` itself). The result is sorted and
    de-duplicated so the caller can distinguish "none" from "more than one".
    """
    if not candidate.is_dir():
        return []
    if (candidate / "Exe" / "Disciple.exe").is_file():
        return [candidate]
    roots: list[Path] = []
    for pattern in ("*/Exe/Disciple.exe", "*/*/Exe/Disciple.exe"):
        for exe in candidate.glob(pattern):
            roots.append(exe.parent.parent)
    return sorted(set(roots))


def find_ini(exe_dir: Path) -> Path | None:
    """Return the INI file inside ``exe_dir``, matched case-insensitively.

    When more than one case-variant exists (a known retail quirk), the
    canonical ``DISCIPLE.INI`` is preferred and a warning is logged; resolving
    which variant the game actually reads is a later case-shim card, not this
    one.
    """
    candidates = sorted(p for p in exe_dir.iterdir() if p.is_file() and p.name.lower() == _INI_NAME)
    if not candidates:
        return None
    if len(candidates) > 1:
        logger.warning(
            "multiple DISCIPLE.INI case-variants in %s (%s); using the canonical name if present",
            exe_dir,
            ", ".join(p.name for p in candidates),
        )
    for path in candidates:
        if path.name == "DISCIPLE.INI":
            return path
    return candidates[0]


def resolve_install(candidate: Path) -> Install:
    """Resolve ``candidate`` to a game install, or raise ``CliError`` (exit 2).

    The candidate is absolutised first: a relative ``--game-dir`` (``.`` or a
    bare folder name) must resolve to the install's real location, or the
    rewritten Windows paths would point at ``Z:\\.\\Globals`` and the tool would
    report "rewrote 21 keys" against a directory that does not exist.

    The message lists exactly what was searched, so "missing" is never reported
    because of a nesting level the user did not account for.
    """
    candidate = Path(candidate).resolve()
    if not candidate.is_dir():
        raise CliError(2, f"not a directory: {candidate}")

    roots = find_install_roots(candidate)
    if len(roots) == 1:
        root = roots[0]
    elif not roots:
        searched = "Exe/Disciple.exe, */Exe/Disciple.exe, */*/Exe/Disciple.exe"
        raise CliError(
            2,
            f"Disciple.exe not found under {candidate} (searched {searched})",
        )
    else:
        listing = "\n".join(f"  {r}" for r in roots)
        raise CliError(
            2,
            f"multiple installs found under {candidate}; pass the exact folder:\n{listing}",
        )

    exe_dir = root / "Exe"
    ini_path = find_ini(exe_dir)
    if ini_path is None:
        raise CliError(2, f"Exe/DISCIPLE.INI not found in {exe_dir}")

    return Install(root=root, exe_dir=exe_dir, ini_path=ini_path)


# --------------------------------------------------------------------------
# INI rewrite orchestration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Rewrite:
    """The outcome of computing or applying the INI rewrite."""

    install: Install
    before: str
    after: str
    changed: int  # installation keys whose value changed
    backup_path: Path | None


def _copy_install_tree(install: Install) -> Install:
    """Copy the install to a sibling ``<root>.copy`` and return it resolved.

    The copy is the whole point of ``--ini-mode copy-tree``: the original GOG
    folder stays pristine and every write (the INI, and later the game's own
    saves and log) lands in the copy.
    """
    dst = Path(str(install.root) + ".copy")
    if dst.exists():
        raise CliError(3, f"copy-tree destination already exists: {dst}")
    try:
        shutil.copytree(install.root, dst)
    except OSError as exc:
        raise CliError(3, f"failed to copy install tree to {dst}: {exc}") from exc

    copied_ini = find_ini(dst / "Exe")
    if copied_ini is None:
        raise CliError(3, f"copied tree at {dst} has no Exe/DISCIPLE.INI")
    return Install(root=dst, exe_dir=dst / "Exe", ini_path=copied_ini)


def _write_or_refuse(path: Path, text: str, mode: str) -> None:
    """Write the rewritten INI, mapping write/encode failures to exit 3.

    ``write_ini`` encodes cp1252, so a POSIX install path that contains a
    character the game's code page cannot represent (Polish ``\u0142``, Cyrillic,
    ...) raises ``UnicodeEncodeError`` rather than ``OSError``. Both are
    "rewrite refused", the documented exit 3 -- never a traceback.
    """
    try:
        ini.write_ini(path, text, mode=mode)
    except UnicodeEncodeError as exc:
        raise CliError(
            3,
            f"cannot rewrite {path}: the install path contains characters the "
            f"game's cp1252 INI cannot represent ({exc})",
        ) from exc
    except OSError as exc:
        raise CliError(3, f"cannot rewrite {path}: {exc}") from exc


def apply_rewrite(install: Install, path_style: str, ini_mode: str) -> Rewrite:
    """Rewrite the install's INI in place and return the result.

    ``ini_mode`` follows M1's ``write_ini`` contract, except ``copy-tree``,
    which M1 defers here: the install is copied to a sibling, the copy's INI is
    rewritten (with no ``.orig`` -- the pristine original is the backup), and
    the copy becomes the install the launcher runs.
    """
    target = install
    backup_path: Path | None = None

    if ini_mode == "copy-tree":
        target = _copy_install_tree(install)
        before = ini.read_ini(target.ini_path)
        after = ini.rewrite_installation_paths(before, target.root, path_style)
        changed = ini.rewritten_key_count(before, after)
        _write_or_refuse(target.ini_path, after, "inplace")
    else:
        before = ini.read_ini(install.ini_path)
        after = ini.rewrite_installation_paths(before, install.root, path_style)
        changed = ini.rewritten_key_count(before, after)
        if ini_mode == "backup":
            backup_path = Path(str(install.ini_path) + ".orig")
        _write_or_refuse(install.ini_path, after, ini_mode)

    return Rewrite(
        install=target,
        before=before,
        after=after,
        changed=changed,
        backup_path=backup_path,
    )


def compute_rewrite(install: Install, path_style: str) -> Rewrite:
    """Compute the rewrite without writing anything (the ``--dry-run`` path)."""
    before = ini.read_ini(install.ini_path)
    after = ini.rewrite_installation_paths(before, install.root, path_style)
    return Rewrite(
        install=install,
        before=before,
        after=after,
        changed=ini.rewritten_key_count(before, after),
        backup_path=None,
    )


def format_ini_diff(before: str, after: str) -> str:
    """Return a ``- old`` / ``+ new`` diff of the lines that change."""
    pairs: list[str] = []
    for old, new in zip(before.splitlines(), after.splitlines(), strict=True):
        if old != new:
            pairs.append(f"- {old}")
            pairs.append(f"+ {new}")
    return "\n".join(pairs)


def summary_line(result: Rewrite, ini_mode: str) -> str:
    """The one-line rewrite summary shown on success (nothing else is printed)."""
    if result.changed == 0:
        return "already up to date; no rewrite needed"
    if ini_mode == "copy-tree":
        return (
            f"copied install to {result.install.root}; rewrote {result.changed} installation keys"
        )
    if ini_mode == "backup" and result.backup_path is not None:
        return f"rewrote {result.changed} installation keys (backup at {result.backup_path})"
    return f"rewrote {result.changed} installation keys"


# --------------------------------------------------------------------------
# Launch
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LaunchCommand:
    """Everything needed to describe or run the launch."""

    wine_name: str
    wine_path: str | None  # resolved executable; None means "not found"
    exe_path: Path
    cwd: Path
    env: dict[str, str]
    #: ``(width, height)`` of the Wine virtual desktop, or ``None`` to exec wine directly.
    virtual_desktop: tuple[int, int] | None = DEFAULT_VIRTUAL_DESKTOP

    def _tail(self) -> list[str]:
        if self.virtual_desktop is None:
            return [str(self.exe_path)]
        w, h = self.virtual_desktop
        return ["explorer", f"/desktop={VIRTUAL_DESKTOP_NAME},{w}x{h}", str(self.exe_path)]

    @property
    def argv(self) -> list[str]:
        assert self.wine_path is not None, "argv is only defined once wine resolves"
        return [self.wine_path, *self._tail()]

    @property
    def display(self) -> str:
        """The shell-quoted command line a human can copy and paste."""
        return shlex.join([self.wine_name, *self._tail()])


def wrapper_staged(exe_dir: Path) -> bool:
    """True when cnc-ddraw's ``ddraw.dll`` sits next to the executable."""
    return any(p.is_file() and p.name.lower() == _DDRAW_DLL for p in exe_dir.iterdir())


def has_native_ddraw_override(env_overrides: str) -> bool:
    """True when a ``WINEDLLOVERRIDES`` value routes ``ddraw`` to native.

    The value is a ``;``-separated list of ``lib=type`` entries, where ``lib``
    may be a comma-separated list and ``type`` a comma-separated list (``n`` =
    native, ``b`` = builtin, ``d`` = disabled). This requires an entry whose
    library is exactly ``ddraw`` and whose type list contains ``n``: ``ddraw=b``
    (builtin only, the wrapper never loads), ``ddraw=d`` (native disabled),
    ``ddraw=`` (empty) and ``notddraw=n`` (a different library) all return
    False, as does a wildcard ``*=n`` (not a specific ``ddraw`` entry).

    The doctor and the launcher share this so the two can never drift apart on
    what "the override is in effect" means.
    """
    for entry in env_overrides.split(";"):
        entry = entry.strip()
        if "=" not in entry:
            continue
        libs, _, types = entry.partition("=")
        if any(lib.strip().lower() == "ddraw" for lib in libs.split(",")):
            type_list = [t.strip().lower() for t in types.split(",")]
            if "n" in type_list:
                return True
    return False


def resolve_wine(wine: str | None) -> str | None:
    """Return the wine executable to run, or ``None`` when it cannot be found.

    A bare name is looked up on ``PATH``; a value containing a path separator
    is taken as given and must exist and be executable.
    """
    name = wine or "wine"
    if os.sep in name or "/" in name or "\\" in name:
        path = Path(name)
        return str(path) if (path.is_file() and os.access(path, os.X_OK)) else None
    return shutil.which(name)


def build_env(install: Install, verbose: bool) -> dict[str, str]:
    """The child environment for the game process."""
    env = os.environ.copy()
    if wrapper_staged(install.exe_dir):
        existing = env.get("WINEDLLOVERRIDES", "")
        if not has_native_ddraw_override(existing):
            env["WINEDLLOVERRIDES"] = (
                f"{existing};{_DDRAW_OVERRIDE}" if existing else _DDRAW_OVERRIDE
            )
    if not verbose:
        env["WINEDEBUG"] = "-all"
    return env


def build_launch(
    install: Install,
    wine_name: str,
    verbose: bool,
    virtual_desktop: tuple[int, int] | None = DEFAULT_VIRTUAL_DESKTOP,
) -> LaunchCommand:
    """Assemble the launch command (without running it)."""
    return LaunchCommand(
        virtual_desktop=virtual_desktop,
        wine_name=wine_name,
        wine_path=resolve_wine(wine_name),
        exe_path=install.exe_path,
        # The game resolves fonts and data modules against its working
        # directory (the R1 in-game evidence: a mismatched run failed with
        # "unable to load fonts"); Exe/ is the known-good baseline.
        cwd=install.exe_dir,
        env=build_env(install, verbose),
    )


def env_overrides(cmd: LaunchCommand) -> list[str]:
    """The env entries the launch adds or changes, as ``KEY=VALUE`` strings."""
    return [
        f"{key}={value}" for key, value in sorted(cmd.env.items()) if os.environ.get(key) != value
    ]


def launch(cmd: LaunchCommand) -> int:
    """Run the game and return its exit code (or raise ``CliError``, exit 4)."""
    if cmd.wine_path is None:
        raise CliError(4, f"wine not found (looked for {cmd.wine_name!r} on PATH)")
    try:
        proc = subprocess.run(cmd.argv, env=cmd.env, cwd=str(cmd.cwd))
    except OSError as exc:
        raise CliError(4, f"failed to run wine ({cmd.wine_path}): {exc}") from exc
    return proc.returncode
