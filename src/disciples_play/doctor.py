"""The ``doctor`` subcommand: checkable pass/fail lines for a Disciples install.

``disciples-play doctor`` turns "does this machine have what the pack needs"
into one line per check -- ``PASS``/``FAIL``/``WARN``/``INFO`` with a one-line
fix hint -- instead of prose the user has to trust. It closes the last defect of
the brief ("no reproducible setup"): a second machine is a set of checkable
lines, not a hand-made prefix.

Nothing here reads game content. It reports paths, sizes, counts, versions and
existence -- and **never** a hash of a game binary, never file content, and
never the cnc-ddraw DLL digest it compares against the marker. The one digest
it does compute (SHA-256 of the staged ``ddraw.dll``, to compare with the
marker file written by :mod:`disciples_play.wrapper`) is reduced to a
matches/does-not-match verdict before it reaches a report, so a 64-hex string
can never leak into a transcript.

Exit codes (documented in ``docs/cli.md``):

* ``0`` -- no check failed (WARN and INFO lines do not fail the run)
* ``1`` -- at least one check failed
* ``2`` -- bad arguments (no install source specified, or an argparse error)

The checks, in output order:

===============  ==============================================================
``install``      install dir resolves to exactly one ``Exe/Disciple.exe``
``ini``          ``Exe/DISCIPLE.INI`` present and writable
``ini-paths``    all 15 ``[Installation]`` + 6 ``[InstallationClient]`` keys
                 present, each holding an absolute Windows path that resolves
                 to this install (relative/empty values are a FAIL -- plan R1)
``wine``         ``wine`` present and reports a ``--version`` (FAIL on POSIX
                 when absent: the launcher cannot run without it); when found,
                 the detail states what was measured: plain Wine crashed this
                 title on the maintainer's machine, the same command in a Wine
                 virtual desktop reached the menu, and a Proton runner also worked
``ddraw-override`` reports whether a native-ddraw route is configured (env or
                 wrapper); always INFO -- the renderer uses COM
                 (``CoCreateInstance``), so the override is inert for it
``wrapper``      cnc-ddraw staged with a marker matching the DLL's digest
``ini-window``   ``[Disciple] InWindow`` -- the game's own display mode. ``0`` is
                 the fullscreen baseline; ``1`` always WARNs, because this title's
                 renderer never loads a wrapper, so the key cannot buy a window.
                 The wording follows the ``wrapper`` line's verdict. The doctor never
                 writes the key (it is the user's choice)
``music``        25 ``.wav`` files in ``Music/``
``video``        41 ``.smk`` cutscenes (6 ``Video/`` + 35 ``Briefing/``)
``display``      an X display is available to verify windowing
``gamescope``    ``gamescope`` on PATH or not -- always INFO: only ``--scale``
                 needs it, so its absence blocks nothing
===============  ==============================================================
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import ini, launch, wrapper

__all__ = ["Check", "Report", "run_doctor"]

PASS = "pass"
FAIL = "fail"
WARN = "warn"
INFO = "info"

#: The folder names the two installation sections point at, keyed by INI key
#: (lowercase). This is the same canonical table the INI rewriter uses; the
#: doctor reuses it rather than re-deriving the ``scenarios`` -> ``Scens``
#: special cases by hand.
_INSTALLATION_FOLDERS = ini._INSTALLATION_FOLDERS

#: The six keys in ``[InstallationClient]``. They are a subset of the fifteen
#: ``[Installation]`` keys (measured on the install: globals, imgs1, sounds1,
#: music, imgdata, briefing), so a complete INI has 15 + 6 = 21 assignments.
_INSTALLATION_CLIENT_KEYS = ("globals", "imgs1", "sounds1", "music", "imgdata", "briefing")

#: The number of ``.wav`` files a complete install ships in ``Music/``.
_EXPECTED_MUSIC_WAVS = 25

#: The number of ``.smk`` cutscenes a complete install ships: 6 in ``Video/``
#: plus 35 in ``Briefing/``.
_EXPECTED_VIDEO_SMKS = 41

#: What every ``InWindow`` warning uses: the title's renderer never loads a
#: wrapper, so no value of the key can produce a wrapper-presented window, and
#: the launcher deliberately does not rewrite it -- it is the user's choice,
#: unlike the 21 installation paths. This is a configuration statement only: the
#: start-up crash at ``0059559E`` happens with ``InWindow=0`` as well, so the key
#: is not its cause and this check makes no claim about crashing.
_WINDOWED_NEEDS_WRAPPER = (
    "windowed presentation is not delivered by this pack for this title: "
    "the renderer never loads cnc-ddraw (the game asks COM for system32\\ddraw.dll)"
)

#: Values of ``[Disciple] InWindow`` read as "the game makes its own window" and
#: as "the game is fullscreen". The game writes ``0``/``1``; the words are
#: accepted so a hand-edited INI is classified rather than called unrecognised.
_TRUTHY = ("1", "true", "yes", "on")
_FALSY = ("0", "false", "no", "off")


@dataclass(frozen=True)
class Check:
    """One doctor check: a stable id, a pass/fail/warn/info status and a detail line."""

    id: str
    status: str
    detail: str


@dataclass(frozen=True)
class Report:
    """The ordered list of checks and the derived pass/fail verdict."""

    checks: tuple[Check, ...]

    @property
    def ok(self) -> bool:
        """True when no check failed (warnings and info do not fail the run)."""
        return all(check.status != FAIL for check in self.checks)

    def exit_code(self) -> int:
        """The process exit code: 0 when ``ok``, else 1."""
        return 0 if self.ok else 1

    def to_dict(self) -> dict:
        """The stable JSON schema: ``{"checks": [...], "ok": bool}``."""
        return {
            "checks": [{"id": c.id, "status": c.status, "detail": c.detail} for c in self.checks],
            "ok": self.ok,
        }


def run_doctor(candidate: str | os.PathLike[str], wine_name: str = "wine") -> Report:
    """Run every check against ``candidate`` and return the :class:`Report`.

    ``candidate`` is the ``--game-dir`` value (or its env/config fallback); it
    is absolutised and searched the way :func:`disciples_play.launch.resolve_install`
    does -- but tolerantly, so a missing or ambiguous install is a ``FAIL``
    check (exit 1), not a raised ``CliError``. Nothing is written anywhere.
    """
    candidate = Path(candidate).resolve()
    root: Path | None = None
    exe_dir: Path | None = None
    ini_path: Path | None = None
    checks: list[Check] = []

    # --- install ----------------------------------------------------------
    if not candidate.is_dir():
        checks.append(
            Check(
                "install",
                FAIL,
                f"not a directory: {candidate} (pass the folder that holds Exe/Disciple.exe)",
            )
        )
    else:
        roots = launch.find_install_roots(candidate)
        if len(roots) == 1:
            root = roots[0]
            exe_dir = root / "Exe"
            checks.append(Check("install", PASS, f"{root} (exe dir: {exe_dir})"))
        elif not roots:
            checks.append(
                Check(
                    "install",
                    FAIL,
                    f"Disciple.exe not found under {candidate} "
                    "(searched Exe/Disciple.exe, */Exe/Disciple.exe, */*/Exe/Disciple.exe)",
                )
            )
        else:
            listing = ", ".join(str(r) for r in roots)
            checks.append(
                Check(
                    "install",
                    FAIL,
                    f"multiple installs found under {candidate}; pass the exact folder: {listing}",
                )
            )

    # --- ini (presence + writability) ------------------------------------
    if root is None:
        checks.append(Check("ini", FAIL, "cannot check: install not resolved"))
    else:
        ini_path = launch.find_ini(exe_dir)
        if ini_path is None:
            checks.append(
                Check(
                    "ini",
                    FAIL,
                    f"Exe/DISCIPLE.INI not found in {exe_dir} (matched case-insensitively)",
                )
            )
        elif os.access(ini_path, os.W_OK):
            checks.append(Check("ini", PASS, f"{ini_path.name} writable ({ini_path})"))
        else:
            checks.append(
                Check(
                    "ini",
                    FAIL,
                    f"{ini_path} not writable by this user; make the install writable "
                    "or run the launcher with --ini-mode copy-tree",
                )
            )

    # --- ini-paths (the 21 installation keys -> existing directories) ----
    if root is None:
        checks.append(Check("ini-paths", FAIL, "cannot check: install not resolved"))
    elif ini_path is None:
        checks.append(Check("ini-paths", FAIL, "cannot check: DISCIPLE.INI not found"))
    else:
        checks.append(_ini_paths_check(root, ini_path))

    # --- wine -------------------------------------------------------------
    checks.append(_wine_check(wine_name))

    # --- ddraw override ---------------------------------------------------
    checks.append(_ddraw_override_check(exe_dir))

    # --- wrapper ----------------------------------------------------------
    checks.append(_wrapper_check(root, exe_dir))

    # --- ini-window (the game's own display mode) -------------------------
    checks.append(_ini_window_check(root, ini_path, exe_dir))

    # --- music / video ----------------------------------------------------
    checks.append(_music_check(root))
    checks.append(_video_check(root))

    # --- display ----------------------------------------------------------
    checks.append(_display_check())

    # --- gamescope (only --scale needs it) --------------------------------
    checks.append(_gamescope_check())

    return Report(checks=tuple(checks))


# --------------------------------------------------------------------------
# Individual checks
# --------------------------------------------------------------------------


def _ini_paths_check(root: Path, ini_path: Path) -> Check:
    """Check that every installation key points at a directory the game can use.

    The check reads each ``[Installation]``/``[InstallationClient]`` value and
    resolves it, rather than mapping key -> canonical folder and trusting the
    value implicitly. A complete, portable INI has all 15 ``[Installation]``
    keys and all 6 ``[InstallationClient]`` keys present, each holding the
    absolute Windows path the launcher writes (``<to_windows_path(root)>\\<canonical
    folder>``, matched case-insensitively). A relative or empty value is a hard
    failure: bare relative names launched from ``Exe`` die with "unable to load
    fonts" (plan R1/Q1), so a value the launcher would still need to rewrite
    must not PASS.
    """
    try:
        text = ini.read_ini(ini_path)
    except (OSError, UnicodeDecodeError) as exc:
        return Check("ini-paths", FAIL, f"cannot read {ini_path}: {exc}")

    by_section = _installation_assignments(text)
    installation = by_section.get("installation", {})
    client = by_section.get("installationclient", {})

    missing_installation = sorted(set(_INSTALLATION_FOLDERS) - set(installation))
    missing_client = sorted(set(_INSTALLATION_CLIENT_KEYS) - set(client))
    if missing_installation or missing_client:
        parts = []
        if missing_installation:
            parts.append(f"[Installation] {', '.join(missing_installation)}")
        if missing_client:
            parts.append(f"[InstallationClient] {', '.join(missing_client)}")
        return Check(
            "ini-paths",
            FAIL,
            "missing installation keys: " + "; ".join(parts) + "; "
            "re-copy DISCIPLE.INI from a complete install",
        )

    windows_root = ini.to_windows_path(root)
    relative: dict[str, str] = {}
    wrong: set[str] = set()
    missing_dir: set[str] = set()

    def _record(key: str, value: str) -> None:
        folder = _INSTALLATION_FOLDERS[key]
        verdict = _classify_installation_value(value, root, windows_root, folder)
        if verdict == "relative":
            relative.setdefault(key, value)
        elif verdict == "wrong":
            wrong.add(key)
        elif verdict == "missing-dir":
            missing_dir.add(key)

    # Both sections' values matter: [Installation] drives single-player,
    # [InstallationClient] drives the network client. The two share six keys,
    # so a per-key dict/set deduplicates rather than double-listing them.
    for key, value in installation.items():
        if key in _INSTALLATION_FOLDERS:
            _record(key, value)
    for key, value in client.items():
        if key in _INSTALLATION_FOLDERS:
            _record(key, value)

    if relative:
        items = [f"{key}={value or '(empty)'}" for key, value in sorted(relative.items())]
        return Check(
            "ini-paths",
            FAIL,
            "relative installation paths: "
            + ", ".join(items)
            + "; the game cannot load its data from relative names (plan R1); "
            "run disciples-play to rewrite them to absolute paths",
        )
    if wrong:
        return Check(
            "ini-paths",
            FAIL,
            f"{len(wrong)} installation paths do not resolve to this install: "
            + ", ".join(sorted(wrong))
            + "; run disciples-play to rewrite them",
        )
    if missing_dir:
        return Check(
            "ini-paths",
            FAIL,
            "data folders missing: "
            + ", ".join(sorted(missing_dir))
            + "; a complete install ships these directories",
        )

    extra = sorted((set(installation) | set(client)) - set(_INSTALLATION_FOLDERS))
    if extra:
        return Check(
            "ini-paths",
            WARN,
            f"found {len(extra)} extra installation keys ({', '.join(extra)}); ignoring them",
        )
    total = len(installation) + len(client)
    return Check(
        "ini-paths",
        PASS,
        f"all {total} installation paths are absolute and resolve to this install "
        "(the INI's lowercase names vs the install's title-case names is expected)",
    )


def _wine_check(wine_name: str) -> Check:
    wine_path = shutil.which(wine_name)
    if wine_path is None:
        if sys.platform == "win32":
            return Check("wine", PASS, "Windows: wine is not needed to launch")
        return Check(
            "wine",
            FAIL,
            f"{wine_name} not found on PATH; install wine to launch the game "
            "(--print-command still works without it)",
        )
    version = _wine_version(wine_path)
    if version is None:
        return Check(
            "wine",
            FAIL,
            f"{wine_name} found at {wine_path} but --version failed; check the wine installation",
        )
    return Check(
        "wine",
        PASS,
        f"{wine_name} {version} ({wine_path}); plain Wine crashed this title at start-up on "
        "the maintainer's machine, where the 640x480 8 bpp mode change was refused; the same "
        "command inside a Wine virtual desktop reached the menu there, so the launcher starts "
        "the game in one (--no-virtual-desktop opts out); a Proton runner also worked for the "
        "maintainer (see docs/wine-recipe.md)",
    )


def _ddraw_route(exe_dir: Path | None) -> tuple[str | None, str]:
    """Return ``(kind, detail)`` for a native ``ddraw`` route, or ``(None, "")``.

    ``kind`` is ``"env"`` when ``WINEDLLOVERRIDES`` routes ``ddraw`` to native and
    ``"staged"`` when a ``ddraw.dll`` sits next to ``Disciple.exe`` (which makes
    the launcher set the override itself). The doctor's ``ddraw-override`` and
    ``ini-window`` checks both read this one function, so they cannot disagree
    about whether a wrapper is in play.
    """
    env_overrides = os.environ.get("WINEDLLOVERRIDES", "")
    if launch.has_native_ddraw_override(env_overrides):
        return "env", f"WINEDLLOVERRIDES={env_overrides!r} routes ddraw to native"
    if _find_file_case_insensitive(exe_dir, "ddraw.dll") is not None:
        return "staged", "ddraw.dll staged next to Disciple.exe"
    return None, ""


def _ddraw_override_check(exe_dir: Path | None) -> Check:
    """Report the ddraw route as information, never a WARN or FAIL.

    For this title's renderer the override is inert in every route (COM, not a
    by-name ``LoadLibrary``; the video player's by-name load is untested), so no
    user action can clear it: a WARN would train users
    to ignore warnings, and a FAIL would block play on nothing. The detail
    keeps the measured wording; only the status is informational.
    """
    kind, detail = _ddraw_route(exe_dir)
    inert = (
        "inert for Disciples' renderer: it acquires DirectDraw via "
        "CoCreateInstance(CLSID_DirectDraw) -> system32\\ddraw.dll (COM), so it does "
        "not load a staged ddraw.dll and ddraw=n,b only falls back to builtin there "
        "(the video player's by-name load is untested)"
    )
    if kind in ("env", "staged"):
        return Check(
            "ddraw-override",
            INFO,
            f"{detail}, but {inert}; the override only matters for titles that "
            "LoadLibrary ddraw.dll by name (see docs/wine-recipe.md)",
        )
    return Check(
        "ddraw-override",
        INFO,
        f"no ddraw override in effect — {inert}; the override only matters for "
        "titles that LoadLibrary ddraw.dll by name",
    )


def _ini_window_check(root: Path | None, ini_path: Path | None, exe_dir: Path | None) -> Check:
    """Check ``[Disciple] InWindow`` -- whether the *game* makes its own window.

    ``InWindow`` selects the game's **own** window mode. cnc-ddraw is *not* an
    alternative here: this title acquires DirectDraw through COM, so a staged
    wrapper is never loaded by the renderer and no value of the key produces one. ``InWindow=1``
    is therefore a WARN in **every** case, wrapper or not, and only
    ``InWindow=0`` passes -- it is the recipes' baseline, not a promise of a
    window. The message follows ``_wrapper_check``'s own verdict ("installed and
    verified" only when that check passes). A missing key is a WARN too (the
    retail default is unknown).

    This is a configuration guard, **not** a crash guard. The start-up
    ``C0000005`` at ``0059559E`` that opened this work happens with
    ``InWindow=0`` as well, so display mode is not its cause; nothing here claims
    to prevent it.

    The check only reads: ``InWindow`` is the user's display choice, so neither
    the doctor nor the launcher writes it (the launcher rewrites the 21 path
    keys and nothing else).
    """
    if root is None:
        return Check("ini-window", FAIL, "cannot check: install not resolved")
    if ini_path is None:
        return Check("ini-window", FAIL, "cannot check: DISCIPLE.INI not found")
    try:
        text = ini.read_ini(ini_path)
    except (OSError, UnicodeDecodeError) as exc:
        return Check("ini-window", FAIL, f"cannot read {ini_path}: {exc}")

    value = _assignments(text).get("disciple", {}).get("inwindow")
    if value is None:
        return Check(
            "ini-window",
            WARN,
            "DISCIPLE.INI has no [Disciple] InWindow key (the retail default is "
            f"unknown); {_WINDOWED_NEEDS_WRAPPER}; set InWindow=0 in "
            "Exe/DISCIPLE.INI for the documented baseline (docs/wrapper.md)",
        )

    normalised = value.strip().lower()
    if normalised in _FALSY:
        return Check(
            "ini-window",
            PASS,
            f"[Disciple] InWindow={value.strip()} (the game fullscreen -- the baseline "
            "the Wine recipes use; the renderer never loads a wrapper, so none presents its window)",
        )
    if normalised in _TRUTHY:
        # Always a WARN: the verification precondition is InWindow=0. The wording
        # follows the wrapper check's own verdict (never a bare ddraw.dll or an
        # env override), so the two lines cannot contradict each other.
        if _wrapper_check(root, exe_dir).status == PASS:
            return Check(
                "ini-window",
                WARN,
                f"[Disciple] InWindow={value.strip()} (the game makes its own window); "
                "cnc-ddraw is installed and verified, but this title's renderer never loads it "
                "(COM -> system32\\ddraw.dll): the window is the game's own, and "
                "InWindow=0 is the documented baseline (docs/wrapper.md)",
            )
        return Check(
            "ini-window",
            WARN,
            f"[Disciple] InWindow={value.strip()} (the game makes its own window) "
            f"and no verified cnc-ddraw: {_WINDOWED_NEEDS_WRAPPER}; set "
            "InWindow=0 in Exe/DISCIPLE.INI for the documented baseline -- staging "
            "cnc-ddraw next to Disciple.exe does not give the renderer a window (it never "
            "loads it; the video player's by-name load is untested)",
        )
    return Check(
        "ini-window",
        WARN,
        f"[Disciple] InWindow={value.strip()!r} is neither 0 nor 1; use 0 in "
        "Exe/DISCIPLE.INI for the documented baseline -- no value gives the renderer "
        "a wrapper-presented window",
    )


def _wrapper_check(root: Path | None, exe_dir: Path | None) -> Check:
    if root is None:
        return Check("wrapper", FAIL, "cannot check: install not resolved")

    dll = _find_file_case_insensitive(exe_dir, "ddraw.dll")
    if dll is None:
        return Check(
            "wrapper",
            WARN,
            "cnc-ddraw not staged (no ddraw.dll next to Disciple.exe); staging "
            "it would not change the renderer, which never loads it",
        )

    marker = exe_dir / wrapper._MARKER_FILENAME
    recorded = wrapper._read_marker(marker)
    if recorded is None or not isinstance(recorded.get("ddraw_dll_sha256"), str):
        return Check(
            "wrapper",
            WARN,
            "ddraw.dll present but no valid marker; cannot verify it is ours — leaving it alone",
        )

    # Compare digests without ever printing one: only a matches/not-matches
    # verdict reaches the report (the no-game-hashes rule).
    if recorded["ddraw_dll_sha256"] != wrapper._sha256_file(dll):
        return Check(
            "wrapper",
            WARN,
            "ddraw.dll present but not ours (digest does not match the marker) — leaving it alone",
        )
    tag = recorded.get("cnc_ddraw_tag") or "unknown tag"
    return Check("wrapper", PASS, f"cnc-ddraw ddraw.dll present and matches our marker ({tag})")


def _music_check(root: Path | None) -> Check:
    if root is None:
        return Check("music", FAIL, "cannot check: install not resolved")
    music_dir = _dir_case_insensitive(root, "Music")
    if music_dir is None:
        return Check("music", FAIL, "Music/ directory not found; music will be missing")
    count, size = _count_files(music_dir, ".wav")
    if count == _EXPECTED_MUSIC_WAVS:
        return Check("music", PASS, f"{count} .wav files in Music/ ({_human_size(size)})")
    return Check(
        "music",
        FAIL,
        f"{count} .wav files in Music/ (expected {_EXPECTED_MUSIC_WAVS}; {_human_size(size)}); "
        "a full install ships 25",
    )


def _video_check(root: Path | None) -> Check:
    if root is None:
        return Check("video", FAIL, "cannot check: install not resolved")
    video_dir = _dir_case_insensitive(root, "Video")
    briefing_dir = _dir_case_insensitive(root, "Briefing")
    if video_dir is None or briefing_dir is None:
        return Check(
            "video",
            FAIL,
            "Video/ and/or Briefing/ directory not found; cutscenes will be missing",
        )
    video_count, video_size = _count_files(video_dir, ".smk")
    briefing_count, briefing_size = _count_files(briefing_dir, ".smk")
    total = video_count + briefing_count
    size = _human_size(video_size + briefing_size)
    if total == _EXPECTED_VIDEO_SMKS:
        return Check(
            "video",
            PASS,
            f"{total} .smk files (Video: {video_count}, Briefing: {briefing_count}; {size})",
        )
    return Check(
        "video",
        FAIL,
        f"{total} .smk files (expected {_EXPECTED_VIDEO_SMKS}; "
        f"Video: {video_count}, Briefing: {briefing_count}; {size}); a full install ships 41",
    )


def _display_check() -> Check:
    if sys.platform == "win32":
        return Check("display", PASS, "Windows: display is managed natively; no X display required")
    display = os.environ.get("DISPLAY")
    if display:
        return Check("display", PASS, f"DISPLAY is set ({display})")
    return Check("display", WARN, "no X display: cannot verify windowing")


def _gamescope_check() -> Check:
    """Report whether ``gamescope`` is on ``PATH`` -- always ``INFO``.

    Only ``--scale`` needs it: the default launch is a plain wine command in a
    virtual desktop, which works without it. So its absence blocks nothing, and
    the line never WARNs or FAILs -- it cannot change the exit code.
    """
    path = shutil.which(launch.GAMESCOPE_PROGRAM)
    if path is None:
        return Check(
            "gamescope",
            INFO,
            f"{launch.GAMESCOPE_PROGRAM} not found on PATH; only needed for --scale "
            "(install it: dnf install gamescope / apt install gamescope)",
        )
    return Check(
        "gamescope",
        INFO,
        f"{launch.GAMESCOPE_PROGRAM} found at {path}; only needed for --scale",
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _assignments(text: str) -> dict[str, dict[str, str]]:
    """Return ``{section: {key: value}}`` for every section, names lowercased.

    Section headers and keys are matched case-insensitively (the retail INI
    writes ``InWindow`` while the synthetic fixtures and the plan use lowercase),
    comment lines are skipped, and a value is taken verbatim after the first
    ``=``. ``[Disciple]`` is where the game keeps its own display mode; the two
    installation sections are read through :func:`_installation_assignments`.
    """
    result: dict[str, dict[str, str]] = {}
    section: str | None = None
    for line in ini.parse(text).lines:
        content = line.content.strip()
        if not content or content.startswith(";"):
            continue
        if content.startswith("[") and content.endswith("]"):
            section = content[1:-1].strip().lower()
            result.setdefault(section, {})
            continue
        if section is not None:
            key, sep, value = content.partition("=")
            if sep and key.strip():
                result[section][key.strip().lower()] = value.strip()
    return result


def _installation_assignments(text: str) -> dict[str, dict[str, str]]:
    """Return ``{section: {key: value}}`` for the two installation sections."""
    assignments = _assignments(text)
    return {name: assignments.get(name, {}) for name in ("installation", "installationclient")}


def _classify_installation_value(value: str, root: Path, windows_root: str, folder: str) -> str:
    """Classify one installation-path value: ok / relative / wrong / missing-dir."""
    stripped = value.strip()
    if not stripped:
        return "relative"
    if not _is_absolute_windows(stripped):
        return "relative"

    expected = _norm_windows_path(f"{windows_root}\\{folder}")
    if _norm_windows_path(stripped) == expected:
        target = _dir_case_insensitive(root, folder)
        return "ok" if target is not None else "missing-dir"

    # Absolute but not the canonical value. The only mapping available without
    # wine is the Z: fallback: a ``Z:\\...`` value that names the same directory
    # as ``root/<folder>`` (case-insensitively) is accepted; any other absolute
    # value is a stale path pointing somewhere else.
    posix = _z_drive_value_to_posix(stripped)
    if posix is not None:
        target = _dir_case_insensitive(root, folder)
        if target is not None and _same_dir_case_insensitive(posix, target):
            return "ok"
    return "wrong"


def _is_absolute_windows(value: str) -> bool:
    stripped = value.strip()
    return bool(re.match(r"^[A-Za-z]:[\\/]", stripped)) or stripped.startswith(("\\\\", "//"))


def _norm_windows_path(value: str) -> str:
    return value.strip().replace("/", "\\").rstrip("\\").lower()


def _z_drive_value_to_posix(value: str) -> Path | None:
    match = re.match(r"^[Zz]:[\\/](.*)$", value.strip())
    if not match:
        return None
    return Path("/" + match.group(1).replace("\\", "/"))


def _same_dir_case_insensitive(a: Path, b: Path) -> bool:
    return str(a.resolve()).lower() == str(b.resolve()).lower()


def _dir_case_insensitive(root: Path, name: str) -> Path | None:
    """Return the directory under ``root`` named ``name`` (any case), or None."""
    if not name:
        return None
    direct = root / name
    if direct.is_dir():
        return direct
    lowered = name.lower()
    for child in root.iterdir():
        if child.is_dir() and child.name.lower() == lowered:
            return child
    return None


def _find_file_case_insensitive(directory: Path | None, name: str) -> Path | None:
    if directory is None or not directory.is_dir():
        return None
    for child in directory.iterdir():
        if child.is_file() and child.name.lower() == name.lower():
            return child
    return None


def _count_files(directory: Path, suffix: str) -> tuple[int, int]:
    """Count files ending in ``suffix`` (case-insensitive) and their total bytes."""
    count = 0
    total = 0
    for child in directory.iterdir():
        if child.is_file() and child.name.lower().endswith(suffix.lower()):
            count += 1
            total += child.stat().st_size
    return count, total


def _wine_version(wine_path: str) -> str | None:
    try:
        proc = subprocess.run(
            [wine_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    for stream in (proc.stdout, proc.stderr):
        for line in (stream or "").splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
    return None


def _human_size(nbytes: int) -> str:
    size = float(nbytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TiB"  # unreachable
