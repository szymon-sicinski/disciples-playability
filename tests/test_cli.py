"""End-to-end CLI tests for ``disciples-play``.

These drive ``cli.main`` over a synthetic install tree (a 2-byte ``MZ`` stub
``Disciple.exe``, an ``Exe/DISCIPLE.INI`` fixture, optionally a stub
``ddraw.dll``) and, for the launch tests, a fake ``wine`` shim on ``PATH`` that
records its argv and environment to files. No network, no real Wine, no game
bytes. The launch tests skip on Windows -- the shim is a POSIX shell script and
Windows launch is unclaimed until a human verifies it.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import disciples_play
import disciples_play.ini as ini
from disciples_play.__main__ import main

FIXTURES = Path(__file__).parent / "fixtures"
WINDOWS = sys.platform == "win32"


def fixture_bytes(name: str = "sample-disciple.ini") -> bytes:
    return (FIXTURES / name).read_bytes()


def make_install(
    base: Path,
    *,
    wrapper: bool = False,
    ini_name: str = "DISCIPLE.INI",
    data_folder: bool = False,
) -> Path:
    """Create a synthetic install tree and return its root."""
    exe_dir = base / "Exe"
    exe_dir.mkdir(parents=True)
    (exe_dir / "Disciple.exe").write_bytes(b"MZ")
    (exe_dir / ini_name).write_bytes(fixture_bytes())
    if wrapper:
        (exe_dir / "ddraw.dll").write_bytes(b"MZ")
    if data_folder:
        (base / "Globals").mkdir()
        (base / "Globals" / "example.txt").write_text("synthetic\n")
    return base


@pytest.fixture(autouse=True)
def _no_winepath(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the Z:\\ fallback so INI assertions are deterministic even on a
    machine that happens to have ``winepath`` installed."""
    real_which = shutil.which

    def which(name: str) -> str | None:
        return None if name == "winepath" else real_which(name)

    monkeypatch.setattr(shutil, "which", which)


@pytest.fixture()
def fake_wine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, exec_tmp_root: Path):
    """A fake ``wine`` on PATH that records its argv/env to files under ``tmp_path``."""
    bindir = exec_tmp_root / f"winebin-{tmp_path.name}"
    bindir.mkdir(exist_ok=True)
    argv_file = tmp_path / "wine-record.argv"
    env_file = tmp_path / "wine-record.env"
    shim = bindir / "wine"
    shim.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" > '{argv_file}'\n"
        f"printf 'WINEDLLOVERRIDES=%s\\n' \"$WINEDLLOVERRIDES\" > '{env_file}'\n"
        f"printf 'WINEDEBUG=%s\\n' \"$WINEDEBUG\" >> '{env_file}'\n"
        f"printf 'PWD=%s\\n' \"$(pwd)\" >> '{env_file}'\n"
        "exit 0\n"
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    return SimpleNamespace(bindir=bindir, argv_file=argv_file, env_file=env_file)


def read_argv(path: Path) -> list[str]:
    return path.read_text().splitlines()


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        key, _, value = line.partition("=")
        out[key] = value
    return out


# --- happy path / launch ---------------------------------------------------


@pytest.mark.skipif(
    WINDOWS, reason="fake-wine shim is a POSIX shell script; Windows launch is unclaimed"
)
def test_happy_path_rewrites_and_launches(tmp_path: Path, fake_wine, capsys) -> None:
    root = make_install(tmp_path / "install", wrapper=True)
    code = main(["--game-dir", str(root)])
    assert code == 0

    rewritten = (root / "Exe" / "DISCIPLE.INI").read_bytes()
    expected = ini.to_windows_path(str(root)) + "\\Globals"
    assert b"globals=" + expected.encode("cp1252") in rewritten
    assert (root / "Exe" / "DISCIPLE.INI.orig").read_bytes() == fixture_bytes()

    assert read_argv(fake_wine.argv_file) == [
        "explorer",
        "/desktop=Disciples,640x480",
        str(root / "Exe" / "Disciple.exe"),
    ]
    env = read_env(fake_wine.env_file)
    assert env["WINEDLLOVERRIDES"] == "ddraw=n,b"
    assert env["WINEDEBUG"] == "-all"
    assert env["PWD"] == str(root / "Exe")

    assert "rewrote 21 installation keys" in capsys.readouterr().out


@pytest.mark.skipif(
    WINDOWS, reason="fake-wine shim is a POSIX shell script; Windows launch is unclaimed"
)
def test_second_run_is_noop(tmp_path: Path, fake_wine, capsys) -> None:
    root = make_install(tmp_path / "install", wrapper=True)
    ini_path = root / "Exe" / "DISCIPLE.INI"

    assert main(["--game-dir", str(root)]) == 0
    mtime = ini_path.stat().st_mtime_ns
    orig = (root / "Exe" / "DISCIPLE.INI.orig").read_bytes()

    assert main(["--game-dir", str(root)]) == 0
    assert ini_path.stat().st_mtime_ns == mtime  # no rewrite happened
    assert (root / "Exe" / "DISCIPLE.INI.orig").read_bytes() == orig  # backup not clobbered

    out = capsys.readouterr().out
    assert "already up to date" in out


# --- dry-run / print-command ----------------------------------------------


def test_dry_run_writes_nothing(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "install")
    ini_path = root / "Exe" / "DISCIPLE.INI"
    before = ini_path.read_bytes()
    mtime = ini_path.stat().st_mtime_ns

    assert main(["--game-dir", str(root), "--dry-run"]) == 0

    assert ini_path.read_bytes() == before
    assert ini_path.stat().st_mtime_ns == mtime
    assert not (root / "Exe" / "DISCIPLE.INI.orig").exists()

    out = capsys.readouterr().out
    assert "would change" in out
    assert "- globals=X:\\Games\\Heroic\\Disciples Gold\\globals" in out
    assert "command:" in out
    assert "cwd:" in out


def test_print_command_is_copy_pasteable(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "install")
    before = (root / "Exe" / "DISCIPLE.INI").read_bytes()

    assert main(["--game-dir", str(root), "--print-command"]) == 0

    out = capsys.readouterr().out.strip()
    assert shlex.split(out) == [
        "wine",
        "explorer",
        "/desktop=Disciples,640x480",
        str(root / "Exe" / "Disciple.exe"),
    ]
    assert (root / "Exe" / "DISCIPLE.INI").read_bytes() == before  # no rewrite
    assert not (root / "Exe" / "DISCIPLE.INI.orig").exists()


def test_print_command_custom_virtual_desktop(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "install")
    assert main(["--game-dir", str(root), "--print-command", "--virtual-desktop", "800x600"]) == 0
    out = capsys.readouterr().out.strip()
    assert "/desktop=Disciples,800x600" in shlex.split(out)


def test_print_command_no_virtual_desktop(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "install")
    assert main(["--game-dir", str(root), "--print-command", "--no-virtual-desktop"]) == 0
    out = capsys.readouterr().out.strip()
    assert shlex.split(out) == ["wine", str(root / "Exe" / "Disciple.exe")]


def test_dry_run_command_line_carries_virtual_desktop(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "install")
    assert main(["--game-dir", str(root), "--dry-run"]) == 0
    lines = capsys.readouterr().out.splitlines()
    command = next(line for line in lines if line.startswith("command:"))
    assert "explorer /desktop=Disciples,640x480" in command


@pytest.mark.parametrize("value", ["", "0x0", "640", "axb", "-640x480", "99999x99999"])
def test_bad_virtual_desktop_exits_2_one_line(tmp_path: Path, capsys, value: str) -> None:
    root = make_install(tmp_path / "install")
    # `=` form: a leading `-` value would otherwise be read as an option.
    assert main(["--game-dir", str(root), "--print-command", f"--virtual-desktop={value}"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    err_lines = captured.err.splitlines()
    assert len(err_lines) == 1
    assert err_lines[0].startswith("disciples-play: ")
    assert "Traceback" not in captured.err


def test_virtual_desktop_and_opt_out_are_mutually_exclusive(tmp_path: Path) -> None:
    root = make_install(tmp_path / "install")
    argv = ["--game-dir", str(root), "--print-command", "--virtual-desktop", "640x480"]
    assert main([*argv, "--no-virtual-desktop"]) == 2


# --- install resolution ----------------------------------------------------


def test_nested_install_one_level_resolves(tmp_path: Path, capsys) -> None:
    inner = tmp_path / "Games" / "Disciples Gold"
    make_install(inner)
    assert main(["--game-dir", str(tmp_path / "Games"), "--print-command"]) == 0
    out = capsys.readouterr().out.strip()
    assert shlex.split(out) == [
        "wine",
        "explorer",
        "/desktop=Disciples,640x480",
        str(inner / "Exe" / "Disciple.exe"),
    ]


def test_nested_install_two_levels_resolves(tmp_path: Path, capsys) -> None:
    inner = tmp_path / "Games" / "a" / "b"
    make_install(inner)
    assert main(["--game-dir", str(tmp_path / "Games"), "--print-command"]) == 0
    out = capsys.readouterr().out.strip()
    assert shlex.split(out) == [
        "wine",
        "explorer",
        "/desktop=Disciples,640x480",
        str(inner / "Exe" / "Disciple.exe"),
    ]


def test_relative_game_dir_produces_absolute_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_install(tmp_path / "install")
    monkeypatch.chdir(tmp_path)
    assert main(["--game-dir", "install", "--ini-mode", "inplace", "--no-launch"]) == 0
    rewritten = (root / "Exe" / "DISCIPLE.INI").read_text()
    assert "globals=" + ini.to_windows_path(str(root.resolve())) + "\\Globals" in rewritten
    assert "Z:\\.\\" not in rewritten  # the D1 defect: a relative root leaking into values


def test_dot_game_dir_produces_absolute_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_install(tmp_path / "install")
    monkeypatch.chdir(root)
    assert main(["--game-dir", ".", "--ini-mode", "inplace", "--no-launch"]) == 0
    rewritten = (root / "Exe" / "DISCIPLE.INI").read_text()
    assert "globals=" + ini.to_windows_path(str(root.resolve())) + "\\Globals" in rewritten
    assert "Z:\\.\\" not in rewritten


def test_missing_exe_exit_2(tmp_path: Path, capsys) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["--game-dir", str(empty)]) == 2
    assert "Disciple.exe not found" in capsys.readouterr().err


def test_not_a_directory_exit_2(tmp_path: Path, capsys) -> None:
    assert main(["--game-dir", str(tmp_path / "does-not-exist")]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_ambiguous_install_exit_2_lists_candidates(tmp_path: Path, capsys) -> None:
    make_install(tmp_path / "Games" / "one")
    make_install(tmp_path / "Games" / "two")
    assert main(["--game-dir", str(tmp_path / "Games")]) == 2
    err = capsys.readouterr().err
    assert "multiple installs found" in err
    assert "one" in err and "two" in err


def test_missing_ini_exit_2(tmp_path: Path, capsys) -> None:
    root = tmp_path / "install"
    (root / "Exe").mkdir(parents=True)
    (root / "Exe" / "Disciple.exe").write_bytes(b"MZ")
    assert main(["--game-dir", str(root)]) == 2
    assert "DISCIPLE.INI not found" in capsys.readouterr().err


# --- exit codes 3 and 4 ----------------------------------------------------


def test_unwritable_ini_exit_3(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "install")
    ini_path = root / "Exe" / "DISCIPLE.INI"
    ini_path.chmod(0o444)
    try:
        assert main(["--game-dir", str(root), "--ini-mode", "inplace"]) == 3
        assert "cannot rewrite" in capsys.readouterr().err
    finally:
        ini_path.chmod(0o644)


def test_non_ascii_install_path_exit_3(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "gra-\u0142\u00f3d\u017a")  # Polish, not cp1252
    assert main(["--game-dir", str(root), "--ini-mode", "inplace", "--no-launch"]) == 3
    err = capsys.readouterr().err
    assert "cannot rewrite" in err
    assert "cp1252" in err


def test_missing_wine_exit_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    root = make_install(tmp_path / "install")
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))  # no wine anywhere
    assert main(["--game-dir", str(root)]) == 4
    assert "wine not found" in capsys.readouterr().err


# --- modes and styles ------------------------------------------------------


def test_inplace_mode_never_backs_up(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "install")
    assert main(["--game-dir", str(root), "--ini-mode", "inplace", "--no-launch"]) == 0
    assert not (root / "Exe" / "DISCIPLE.INI.orig").exists()
    assert "rewrote 21 installation keys" in capsys.readouterr().out


def test_copy_tree_mode_leaves_original_pristine(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "install", data_folder=True)
    original_ini = (root / "Exe" / "DISCIPLE.INI").read_bytes()

    assert main(["--game-dir", str(root), "--ini-mode", "copy-tree", "--no-launch"]) == 0

    assert (root / "Exe" / "DISCIPLE.INI").read_bytes() == original_ini
    copy_root = Path(str(root) + ".copy")
    assert (copy_root / "Globals" / "example.txt").exists()
    rewritten = (copy_root / "Exe" / "DISCIPLE.INI").read_text()
    assert ini.to_windows_path(str(copy_root)) + "\\Globals" in rewritten
    out = capsys.readouterr().out
    assert "copied install to" in out
    assert "rewrote 21 installation keys" in out


def test_copy_tree_refuses_existing_target(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "install")
    Path(str(root) + ".copy").mkdir()
    assert main(["--game-dir", str(root), "--ini-mode", "copy-tree", "--no-launch"]) == 3
    assert "already exists" in capsys.readouterr().err


def test_relative_path_style_dry_run(tmp_path: Path, capsys) -> None:
    root = make_install(tmp_path / "install")
    assert main(["--game-dir", str(root), "--path-style", "relative", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "+ globals=Globals" in out


# --- argument sources and meta ---------------------------------------------


def test_env_var_install_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    root = make_install(tmp_path / "install")
    monkeypatch.setenv("DISCIPLES_GAME_DIR", str(root))
    assert main(["--print-command"]) == 0
    assert shlex.split(capsys.readouterr().out.strip()) == [
        "wine",
        "explorer",
        "/desktop=Disciples,640x480",
        str(root / "Exe" / "Disciple.exe"),
    ]


def test_config_file_install_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    root = make_install(tmp_path / "install")
    config_dir = tmp_path / "config"
    # config_path() reads XDG_CONFIG_HOME on POSIX and APPDATA on Windows; set
    # both so the test is platform-agnostic (only the relevant one is read).
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))
    monkeypatch.setenv("APPDATA", str(config_dir))
    (config_dir / "disciples-play").mkdir(parents=True)
    (config_dir / "disciples-play" / "config.ini").write_text(f"game_dir = {root}\n")

    assert main(["--print-command"]) == 0
    assert shlex.split(capsys.readouterr().out.strip()) == [
        "wine",
        "explorer",
        "/desktop=Disciples,640x480",
        str(root / "Exe" / "Disciple.exe"),
    ]


def test_game_dir_flag_beats_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    flag_root = make_install(tmp_path / "flag")
    make_install(tmp_path / "env")
    monkeypatch.setenv("DISCIPLES_GAME_DIR", str(tmp_path / "env"))
    assert main(["--game-dir", str(flag_root), "--print-command"]) == 0
    assert shlex.split(capsys.readouterr().out.strip()) == [
        "wine",
        "explorer",
        "/desktop=Disciples,640x480",
        str(flag_root / "Exe" / "Disciple.exe"),
    ]


def test_no_install_specified_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.delenv("DISCIPLES_GAME_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "no-config"))
    assert main(["--print-command"]) == 2
    assert "no install specified" in capsys.readouterr().err


def test_help_and_version(capsys) -> None:
    assert main(["--help"]) == 0
    assert "usage: disciples-play" in capsys.readouterr().out

    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"disciples-play {disciples_play.__version__}"


def test_python_dash_m_matches_console_script() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "disciples_play", "--version"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == f"disciples-play {disciples_play.__version__}"
