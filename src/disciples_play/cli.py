"""Command-line interface for ``disciples-play``.

Parses arguments and drives :mod:`disciples_play.launch`. The exit codes are a
contract, documented here and in ``docs/cli.md``:

* ``0`` -- success (also ``--help``/``--version``, ``--dry-run``,
  ``--print-command``, ``--no-launch``)
* ``1`` -- ``data``: at least one file could not be parsed (the report still
  prints, with per-file ``error`` entries)
* ``2`` -- bad command line, or a bad/missing install
* ``3`` -- rewrite refused (INI not writable, copy-tree target exists)
* ``4`` -- wine not found (launch only)

The ``doctor`` subcommand has its own contract: ``0`` all checks passed, ``1``
any check failed, ``2`` bad arguments (see ``docs/cli.md``).

The install may be given three ways, in priority order: ``--game-dir``, the
``DISCIPLES_GAME_DIR`` environment variable, or a config file at
``<config-dir>/disciples-play/config.ini`` (``game_dir=...`` and optional
``wine=...`` keys).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from . import __version__, doctor, ini, launch

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_USAGE_OR_INSTALL = 2
EXIT_REWRITE_REFUSED = 3
EXIT_WINE_MISSING = 4
EXIT_DATA_INCOMPLETE = 1  # `data`: at least one file could not be parsed


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--game-dir",
        metavar="DIR",
        help=(
            "the install directory, or a parent of it (a retail folder copied in "
            "as a folder one or two levels down is found automatically)"
        ),
    )

    parser = argparse.ArgumentParser(
        prog="disciples-play",
        parents=[common],
        description=(
            "Make a Disciples: Sacred Lands Gold install portable and launch it "
            "under Wine. Requires the game files you already own."
        ),
        epilog=(
            "exit codes: 0 success; 1 data parse errors; 2 bad/missing install; "
            "3 rewrite refused; 4 wine not found. See docs/cli.md."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="show the INI diff and the launch command without writing or launching",
    )
    mode.add_argument(
        "--print-command",
        action="store_true",
        help="print the shell-quoted launch command and exit (no writes, no launch)",
    )
    parser.add_argument(
        "--wine",
        metavar="PATH",
        help="wine binary to use (default: wine on PATH)",
    )
    desktop = parser.add_mutually_exclusive_group()
    desktop.add_argument(
        "--virtual-desktop",
        metavar="WxH",
        default=None,
        help=(
            "start the game in a Wine virtual desktop of this size (default: 640x480); "
            "on by default because plain Wine on a display without a 640x480 mode "
            "has been seen to crash the game at start-up"
        ),
    )
    desktop.add_argument(
        "--no-virtual-desktop",
        action="store_true",
        help="exec wine directly, without a virtual desktop (the pre-change behaviour)",
    )
    parser.add_argument(
        "--path-style",
        choices=("wine", "relative"),
        default="wine",
        help=(
            "how installation paths are written (default: wine = absolute Windows "
            "paths; relative is experimental and known to fail in-game)"
        ),
    )
    parser.add_argument(
        "--ini-mode",
        choices=("backup", "inplace", "copy-tree"),
        default="backup",
        help=(
            "how DISCIPLE.INI is updated (default: backup = in place, saving "
            "<name>.orig once; copy-tree = operate on a pristine sibling copy)"
        ),
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="rewrite the INI but do not launch the game",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="keep wine's debug output and log more",
    )
    verbosity.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress the rewrite summary line",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    data_parser = subparsers.add_parser(
        "data",
        help="print a read-only structural report of the game's data files",
        description="Read-only structural report of the game's data files.",
    )
    data_parser.add_argument(
        "--game-dir",
        metavar="DIR",
        default=argparse.SUPPRESS,
        help=(
            "the install directory, or a parent of it (defaults to "
            "$DISCIPLES_GAME_DIR, then the config file)"
        ),
    )
    data_parser.add_argument(
        "--json", action="store_true", help="emit the report as JSON instead of text"
    )
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="check this machine and install, one PASS/FAIL/WARN line per check",
        description=(
            "Check that this machine and install have what the pack needs, one "
            "line per check. Exit codes: 0 all pass, 1 any fail, 2 bad arguments."
        ),
    )
    # ``--game-dir`` is accepted here too (``disciples-play doctor --game-dir …``),
    # but with ``default=argparse.SUPPRESS``: when it is given *before* the
    # subcommand (``disciples-play --game-dir … doctor``) the parent parser has
    # already stored it, and a plain ``default=None`` would overwrite that value
    # with ``None``. SUPPRESS leaves the parent's value untouched.
    doctor_parser.add_argument(
        "--game-dir",
        metavar="DIR",
        default=argparse.SUPPRESS,
        help="the install directory, or a parent of it",
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help='emit a stable JSON schema ({"checks": [{"id","status","detail"}...], "ok": bool})',
    )
    return parser


def config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "disciples-play" / "config.ini"


def load_config() -> dict[str, str]:
    """Read ``game_dir``/``wine`` from the config file, if present."""
    path = config_path()
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    values: dict[str, str] = {}
    for line in ini.parse(text).lines:
        content = line.content
        if not content or content.lstrip().startswith((";", "#", "[")):
            continue
        if "=" not in content:
            continue
        key, _, value = content.partition("=")
        key = key.strip().lower()
        if key in ("game_dir", "wine") and value.strip():
            values[key] = value.strip()
    return values


def resolve_game_dir(ns: argparse.Namespace) -> str:
    # ``getattr`` rather than ``ns.game_dir``: the ``doctor`` subparser declares
    # ``--game-dir`` with ``default=argparse.SUPPRESS``, so when it is not given
    # there the attribute may be absent entirely and falls through to env/config.
    game_dir = getattr(ns, "game_dir", None)
    if game_dir:
        return game_dir
    env = os.environ.get("DISCIPLES_GAME_DIR")
    if env:
        return env
    configured = load_config().get("game_dir")
    if configured:
        return configured
    raise launch.CliError(
        EXIT_USAGE_OR_INSTALL,
        "no install specified: pass --game-dir, set $DISCIPLES_GAME_DIR, "
        f"or write game_dir= in {config_path()}",
    )


def _print_dry_run(
    install: launch.Install,
    ns: argparse.Namespace,
    virtual_desktop: tuple[int, int] | None,
) -> None:
    result = launch.compute_rewrite(install, ns.path_style)
    if result.changed == 0:
        print(f"{install.ini_path}: already up to date; nothing to rewrite")
    else:
        print(f"{install.ini_path}: {result.changed} of 21 installation keys would change:")
        print(launch.format_ini_diff(result.before, result.after))

    cmd = launch.build_launch(install, ns.wine or "wine", ns.verbose, virtual_desktop)
    print(f"command: {cmd.display}")
    print(f"cwd: {cmd.cwd}")
    overrides = launch.env_overrides(cmd)
    if overrides:
        print(f"env: {' '.join(overrides)}")


def run(ns: argparse.Namespace) -> int:
    virtual_desktop: tuple[int, int] | None
    if ns.no_virtual_desktop:
        virtual_desktop = None
    elif ns.virtual_desktop is None:  # option absent; an empty value must still be rejected
        virtual_desktop = launch.DEFAULT_VIRTUAL_DESKTOP
    else:
        virtual_desktop = launch.parse_virtual_desktop(ns.virtual_desktop)
    install = launch.resolve_install(Path(resolve_game_dir(ns)))

    if ns.print_command:
        cmd = launch.build_launch(install, ns.wine or "wine", ns.verbose, virtual_desktop)
        print(cmd.display)
        return EXIT_OK

    if ns.dry_run:
        _print_dry_run(install, ns, virtual_desktop)
        return EXIT_OK

    result = launch.apply_rewrite(install, ns.path_style, ns.ini_mode)
    if not ns.quiet:
        print(launch.summary_line(result, ns.ini_mode))

    if ns.no_launch:
        return EXIT_OK

    cmd = launch.build_launch(result.install, ns.wine or "wine", ns.verbose, virtual_desktop)
    return launch.launch(cmd)


def run_doctor_cli(ns: argparse.Namespace) -> int:
    """Run the ``doctor`` subcommand and return its exit code (0/1/2)."""
    try:
        candidate = resolve_game_dir(ns)
    except launch.CliError as exc:  # no install source specified -> bad arguments
        print(f"disciples-play: {exc.message}", file=sys.stderr)
        return exc.exit_code

    report = doctor.run_doctor(candidate)
    if ns.json:
        print(json.dumps(report.to_dict()))
    else:
        for check in report.checks:
            print(f"{check.status.upper()} {check.id}: {check.detail}")
    return report.exit_code()


def _configure_logging(verbose: bool, quiet: bool) -> None:
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.ERROR
    else:
        level = logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    logging.getLogger().setLevel(level)


def _data_main(ns: argparse.Namespace) -> int:
    """``disciples-play data`` -- the read-only structural report (M5).

    Resolves the install the same way the launcher does (``--game-dir``, then
    ``$DISCIPLES_GAME_DIR``, then the config file, then the parent-directory
    search in :func:`launch.resolve_install`), so the two subcommands agree on
    what ``--game-dir`` means and a parent directory resolves to the same root.
    """

    from .data import build_report, render_text, report_error_count

    try:
        game_dir = resolve_game_dir(ns)
        install = launch.resolve_install(Path(game_dir))
        report = build_report(install.root)
    except launch.CliError as exc:
        print(f"disciples-play data: {exc.message}", file=sys.stderr)
        return exc.exit_code
    except NotADirectoryError as exc:
        print(f"disciples-play data: {exc}", file=sys.stderr)
        return EXIT_USAGE_OR_INSTALL

    if ns.json:
        _emit(json.dumps(report, indent=2))
    else:
        _emit(render_text(report))

    errors = report_error_count(report)
    if errors:
        print(
            f"disciples-play data: {errors} file(s) could not be parsed "
            "(see the report's 'error' entries)",
            file=sys.stderr,
        )
        return EXIT_DATA_INCOMPLETE
    return EXIT_OK


def _emit(text: str) -> None:
    """Write ``text`` to stdout, tolerating an early-closed pipe (``| head``)."""

    try:
        print(text)
        sys.stdout.flush()
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    if not argv:
        parser.print_help()
        return EXIT_OK
    try:
        ns = parser.parse_args(argv)
    except SystemExit as exc:  # --help/--version exit 0; bad arguments exit 2
        return int(exc.code or EXIT_OK)

    command = getattr(ns, "command", None)
    if command == "data":
        return _data_main(ns)
    if command == "doctor":
        return run_doctor_cli(ns)

    _configure_logging(ns.verbose, ns.quiet)
    try:
        return run(ns)
    except launch.CliError as exc:
        print(f"disciples-play: {exc.message}", file=sys.stderr)
        return exc.exit_code
