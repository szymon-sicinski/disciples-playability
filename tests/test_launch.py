"""Unit tests for install resolution and launch assembly in ``launch.py``.

These exercise the pure parts directly; the end-to-end CLI behaviour (exit
codes, the fake-``wine`` shim, copy-tree) is covered in ``test_cli.py``. All
trees are synthetic ``tmp_path`` fixtures -- no game bytes.
"""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest

import disciples_play.ini as ini
from disciples_play import launch


def make_install(base: Path, *, ini_name: str = "DISCIPLE.INI") -> Path:
    exe_dir = base / "Exe"
    exe_dir.mkdir(parents=True)
    (exe_dir / "Disciple.exe").write_bytes(b"MZ")
    (exe_dir / ini_name).write_text("[Installation]\r\nglobals=X:\\\\old\\\\globals\r\n")
    return base


def test_find_install_roots_direct(tmp_path: Path) -> None:
    root = make_install(tmp_path / "game")
    assert launch.find_install_roots(root) == [root]


def test_find_install_roots_one_level_down(tmp_path: Path) -> None:
    make_install(tmp_path / "Games" / "Disciples Gold")
    assert launch.find_install_roots(tmp_path / "Games") == [tmp_path / "Games" / "Disciples Gold"]


def test_find_install_roots_two_levels_down(tmp_path: Path) -> None:
    make_install(tmp_path / "Games" / "a" / "b")
    assert launch.find_install_roots(tmp_path / "Games") == [tmp_path / "Games" / "a" / "b"]


def test_find_install_roots_not_a_directory(tmp_path: Path) -> None:
    assert launch.find_install_roots(tmp_path / "nope") == []


def test_find_install_roots_multiple_sorted(tmp_path: Path) -> None:
    make_install(tmp_path / "Games" / "b")
    make_install(tmp_path / "Games" / "a")
    assert launch.find_install_roots(tmp_path / "Games") == [
        tmp_path / "Games" / "a",
        tmp_path / "Games" / "b",
    ]


def test_find_ini_case_insensitive(tmp_path: Path) -> None:
    root = make_install(tmp_path / "game", ini_name="DISCIPLE.ini")
    found = launch.find_ini(root / "Exe")
    assert found is not None and found.name == "DISCIPLE.ini"


def test_find_ini_prefers_canonical_name(tmp_path: Path) -> None:
    root = make_install(tmp_path / "game")
    (root / "Exe" / "disciple.INI").write_text("other\r\n")
    found = launch.find_ini(root / "Exe")
    assert found is not None and found.name == "DISCIPLE.INI"


def test_find_ini_missing(tmp_path: Path) -> None:
    root = make_install(tmp_path / "game")
    (root / "Exe" / "DISCIPLE.INI").unlink()
    assert launch.find_ini(root / "Exe") is None


def test_resolve_install_missing_exe_lists_search(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(launch.CliError) as exc:
        launch.resolve_install(empty)
    assert exc.value.exit_code == 2
    assert "Disciple.exe not found" in exc.value.message
    assert "*/*/Exe/Disciple.exe" in exc.value.message


def test_resolve_install_missing_ini_exit_2(tmp_path: Path) -> None:
    root = tmp_path / "game"
    (root / "Exe").mkdir(parents=True)
    (root / "Exe" / "Disciple.exe").write_bytes(b"MZ")
    with pytest.raises(launch.CliError) as exc:
        launch.resolve_install(root)
    assert exc.value.exit_code == 2
    assert "DISCIPLE.INI not found" in exc.value.message


def test_resolve_install_ambiguous_lists_candidates(tmp_path: Path) -> None:
    make_install(tmp_path / "Games" / "one")
    make_install(tmp_path / "Games" / "two")
    with pytest.raises(launch.CliError) as exc:
        launch.resolve_install(tmp_path / "Games")
    assert exc.value.exit_code == 2
    assert "multiple installs found" in exc.value.message
    assert "one" in exc.value.message and "two" in exc.value.message


def test_resolve_install_absolutises_relative_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_install(tmp_path / "install")
    monkeypatch.chdir(tmp_path)
    install = launch.resolve_install(Path("install"))
    assert install.root == root.resolve()
    assert install.root.is_absolute()


def test_resolve_install_absolutises_dot_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_install(tmp_path / "install")
    monkeypatch.chdir(root)
    install = launch.resolve_install(Path("."))
    assert install.root == root.resolve()
    assert install.root.is_absolute()


def test_wrapper_staged_is_case_insensitive(tmp_path: Path) -> None:
    root = make_install(tmp_path / "game")
    exe_dir = root / "Exe"
    assert not launch.wrapper_staged(exe_dir)
    (exe_dir / "DDRAW.DLL").write_bytes(b"MZ")
    assert launch.wrapper_staged(exe_dir)


def test_build_env_sets_override_only_when_staged(tmp_path: Path) -> None:
    root = make_install(tmp_path / "game")
    install = launch.resolve_install(root)
    env = launch.build_env(install, verbose=False)
    assert "WINEDLLOVERRIDES" not in env
    assert env["WINEDEBUG"] == "-all"

    (root / "Exe" / "ddraw.dll").write_bytes(b"MZ")
    env = launch.build_env(install, verbose=False)
    assert env["WINEDLLOVERRIDES"] == "ddraw=n,b"


def test_build_env_verbose_keeps_wine_debug(tmp_path: Path) -> None:
    root = make_install(tmp_path / "game")
    install = launch.resolve_install(root)
    env = launch.build_env(install, verbose=True)
    assert "WINEDEBUG" not in env


def test_build_env_appends_to_existing_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WINEDLLOVERRIDES", "msvcr120=b")
    root = make_install(tmp_path / "game")
    (root / "Exe" / "ddraw.dll").write_bytes(b"MZ")
    install = launch.resolve_install(root)
    env = launch.build_env(install, verbose=False)
    assert env["WINEDLLOVERRIDES"] == "msvcr120=b;ddraw=n,b"


def test_build_env_keeps_existing_native_ddraw_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WINEDLLOVERRIDES", "ddraw=n,b")
    root = make_install(tmp_path / "game")
    (root / "Exe" / "ddraw.dll").write_bytes(b"MZ")
    install = launch.resolve_install(root)
    env = launch.build_env(install, verbose=False)
    assert env["WINEDLLOVERRIDES"] == "ddraw=n,b"  # not duplicated


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ddraw=n,b", True),
        ("ddraw=n", True),
        ("msvcr120=b;ddraw=n,b", True),
        ("ddraw,dsound=n", True),
        ("ddraw=b", False),
        ("ddraw=d", False),
        ("ddraw=", False),
        ("notddraw=n", False),
        ("*=n", False),
        ("", False),
    ],
)
def test_has_native_ddraw_override(value: str, expected: bool) -> None:
    assert launch.has_native_ddraw_override(value) is expected


def test_build_env_appends_when_ddraw_is_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ddraw=d disables native ddraw; the launcher must still add ddraw=n,b
    # (a bare "ddraw" substring match would wrongly leave it alone).
    monkeypatch.setenv("WINEDLLOVERRIDES", "ddraw=d")
    root = make_install(tmp_path / "game")
    (root / "Exe" / "ddraw.dll").write_bytes(b"MZ")
    install = launch.resolve_install(root)
    env = launch.build_env(install, verbose=False)
    assert env["WINEDLLOVERRIDES"] == "ddraw=d;ddraw=n,b"


def test_resolve_wine_bare_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        launch.shutil, "which", lambda name: "/opt/wine/bin/wine" if name == "wine" else None
    )
    assert launch.resolve_wine("wine") == "/opt/wine/bin/wine"
    assert launch.resolve_wine(None) == "/opt/wine/bin/wine"


def test_resolve_wine_explicit_path(exec_tmp_root: Path, tmp_path: Path) -> None:
    shim = exec_tmp_root / "wine-explicit"
    shim.write_text("#!/bin/sh\n")
    shim.chmod(0o755)
    assert launch.resolve_wine(str(shim)) == str(shim)
    assert launch.resolve_wine(str(tmp_path / "missing")) is None


def _launch_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **kwargs):
    monkeypatch.setattr(launch.shutil, "which", lambda name: "/fake/wine")
    install = launch.resolve_install(make_install(tmp_path / "install"))
    return install, launch.build_launch(install, "wine", False, **kwargs)


def test_build_launch_default_argv_uses_virtual_desktop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install, cmd = _launch_for(tmp_path, monkeypatch)
    assert cmd.argv == [
        "/fake/wine",
        "explorer",
        "/desktop=Disciples,640x480",
        str(install.exe_path),
    ]
    assert cmd.argv[-1] == str(install.exe_path)


def test_build_launch_custom_virtual_desktop_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cmd = _launch_for(tmp_path, monkeypatch, virtual_desktop=(1024, 768))
    assert cmd.argv[1:3] == ["explorer", "/desktop=Disciples,1024x768"]


def test_build_launch_without_virtual_desktop_is_plain_wine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install, cmd = _launch_for(tmp_path, monkeypatch, virtual_desktop=None)
    assert cmd.argv == ["/fake/wine", str(install.exe_path)]
    assert "explorer" not in cmd.argv
    assert cmd.display == shlex.join(["wine", str(install.exe_path)])


def test_build_launch_display_shows_virtual_desktop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install, cmd = _launch_for(tmp_path, monkeypatch)
    assert cmd.display == shlex.join(
        ["wine", "explorer", "/desktop=Disciples,640x480", str(install.exe_path)]
    )


# --- --scale N (gamescope) ---------------------------------------------------


def _scale_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    scale: int,
    virtual_desktop: tuple[int, int] | None = launch.DEFAULT_VIRTUAL_DESKTOP,
    gamescope: str | None = "/fake/gamescope",
):
    """Build a launch with ``scale``, resolving wine and gamescope synthetically."""

    def which(name: str) -> str | None:
        if name == launch.GAMESCOPE_PROGRAM:
            return gamescope
        return "/fake/wine" if name == "wine" else None

    monkeypatch.setattr(launch.shutil, "which", which)
    install = launch.resolve_install(make_install(tmp_path / "install"))
    return install, launch.build_launch(install, "wine", False, virtual_desktop, scale=scale)


@pytest.mark.parametrize("scale", [2, 3, 4])
def test_scale_wraps_the_virtual_desktop_command_in_gamescope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scale: int
) -> None:
    install, cmd = _scale_launch(tmp_path, monkeypatch, scale=scale)
    # The whole argv is pinned: dropping ``-S integer`` or the ``--`` separator
    # must fail this test, not just change the picture.
    assert cmd.argv == [
        "/fake/gamescope",
        "-w",
        "640",
        "-h",
        "480",
        "-W",
        str(640 * scale),
        "-H",
        str(480 * scale),
        "-S",
        "integer",
        "--",
        "/fake/wine",
        "explorer",
        "/desktop=Disciples,640x480",
        str(install.exe_path),
    ]


def test_scale_argv_pins_integer_scaling_and_the_separator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A named assertion for the two flags a mutation would otherwise only blur."""
    _, cmd = _scale_launch(tmp_path, monkeypatch, scale=3)
    assert cmd.argv[9:11] == ["-S", "integer"]
    assert cmd.argv[11] == "--"  # everything after it is the wrapped wine command
    assert cmd.argv[12] == "/fake/wine"


def test_scale_1_is_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install, cmd = _scale_launch(tmp_path, monkeypatch, scale=1, gamescope=None)
    assert cmd.argv == [
        "/fake/wine",
        "explorer",
        "/desktop=Disciples,640x480",
        str(install.exe_path),
    ]
    assert cmd.display == shlex.join(
        ["wine", "explorer", "/desktop=Disciples,640x480", str(install.exe_path)]
    )


def test_scale_uses_the_virtual_desktop_size_as_the_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cmd = _scale_launch(tmp_path, monkeypatch, scale=2, virtual_desktop=(800, 600))
    assert cmd.argv[1:11] == ["-w", "800", "-h", "600", "-W", "1600", "-H", "1200", "-S", "integer"]
    assert "/desktop=Disciples,800x600" in cmd.argv


def test_scale_without_virtual_desktop_uses_the_game_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install, cmd = _scale_launch(tmp_path, monkeypatch, scale=3, virtual_desktop=None)
    assert cmd.argv[1:11] == ["-w", "640", "-h", "480", "-W", "1920", "-H", "1440", "-S", "integer"]
    assert cmd.argv[11] == "--"
    assert cmd.argv[12:] == ["/fake/wine", str(install.exe_path)]


def test_scale_display_shows_gamescope_and_the_wine_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install, cmd = _scale_launch(tmp_path, monkeypatch, scale=3)
    assert shlex.split(cmd.display) == [
        "gamescope",
        "-w",
        "640",
        "-h",
        "480",
        "-W",
        "1920",
        "-H",
        "1440",
        "-S",
        "integer",
        "--",
        "wine",
        "explorer",
        "/desktop=Disciples,640x480",
        str(install.exe_path),
    ]


def test_scale_without_gamescope_is_exit_2_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(launch.CliError) as exc:
        _scale_launch(tmp_path, monkeypatch, scale=2, gamescope=None)
    assert exc.value.exit_code == 2
    assert "gamescope not found" in exc.value.message
    assert "dnf install gamescope" in exc.value.message
    assert "apt install gamescope" in exc.value.message
    assert "\n" not in exc.value.message


def test_build_launch_rejects_an_out_of_range_scale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(launch.CliError) as exc:
        _scale_launch(tmp_path, monkeypatch, scale=5)
    assert exc.value.exit_code == 2
    assert "--scale" in exc.value.message


@pytest.mark.parametrize(("value", "expected"), [("1", 1), ("2", 2), ("4", 4), ("03", 3)])
def test_parse_scale_accepts(value: str, expected: int) -> None:
    assert launch.parse_scale(value) == expected


@pytest.mark.parametrize("value", ["", "0", "5", "-1", "a", "1.5", " 3", "+3", "٣"])
def test_parse_scale_rejects(value: str) -> None:
    with pytest.raises(launch.CliError) as excinfo:
        launch.parse_scale(value)
    assert excinfo.value.exit_code == 2
    assert "\n" not in excinfo.value.message
    assert repr(value) in excinfo.value.message


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("640x480", (640, 480)),
        ("640X480", (640, 480)),
        ("1x1", (1, 1)),
        ("16384x16384", (16384, 16384)),
        ("0640x0480", (640, 480)),
    ],
)
def test_parse_virtual_desktop_accepts(value: str, expected: tuple[int, int]) -> None:
    assert launch.parse_virtual_desktop(value) == expected


@pytest.mark.parametrize(
    "value",
    ["0x0", "640", "axb", "-640x480", "640x", "x480", "640x480x600", "99999x99999", "640x 480"],
)
def test_parse_virtual_desktop_rejects(value: str) -> None:
    with pytest.raises(launch.CliError) as excinfo:
        launch.parse_virtual_desktop(value)
    assert excinfo.value.exit_code == 2
    assert "\n" not in excinfo.value.message
    assert repr(value) in excinfo.value.message


@pytest.mark.parametrize("value", ["640x480", "640X480", "1x1", "16384x16384"])
def test_parse_virtual_desktop_round_trips(value: str) -> None:
    w, h = launch.parse_virtual_desktop(value)
    assert f"{w}x{h}" == value.lower()


def test_compute_rewrite_reports_changed_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda name: None)
    root = make_install(tmp_path / "game")
    install = launch.resolve_install(root)
    result = launch.compute_rewrite(install, "wine")
    assert result.changed == 1  # the single globals key
    assert "Z:" in result.after


def test_apply_rewrite_backup_creates_orig_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda name: None)
    root = make_install(tmp_path / "game")
    install = launch.resolve_install(root)
    first = launch.apply_rewrite(install, "wine", "backup")
    assert first.changed == 1
    orig = root / "Exe" / "DISCIPLE.INI.orig"
    assert orig.exists()
    original_bytes = orig.read_bytes()
    second = launch.apply_rewrite(install, "wine", "backup")
    assert second.changed == 0
    assert orig.read_bytes() == original_bytes  # never overwritten


def test_apply_rewrite_inplace_never_backs_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda name: None)
    root = make_install(tmp_path / "game")
    install = launch.resolve_install(root)
    launch.apply_rewrite(install, "wine", "inplace")
    assert not (root / "Exe" / "DISCIPLE.INI.orig").exists()


def test_apply_rewrite_copy_tree_leaves_original_pristine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda name: None)
    root = make_install(tmp_path / "game")
    (root / "Globals").mkdir()
    (root / "Globals" / "data.txt").write_text("synthetic\n")
    original_ini = (root / "Exe" / "DISCIPLE.INI").read_bytes()

    install = launch.resolve_install(root)
    result = launch.apply_rewrite(install, "wine", "copy-tree")

    assert (root / "Exe" / "DISCIPLE.INI").read_bytes() == original_ini
    copy_root = Path(str(root) + ".copy")
    assert copy_root.exists()
    assert (copy_root / "Globals" / "data.txt").exists()
    assert result.install.root == copy_root
    rewritten = (copy_root / "Exe" / "DISCIPLE.INI").read_text()
    assert ini.to_windows_path(str(copy_root)) + "\\Globals" in rewritten


def test_apply_rewrite_non_cp1252_path_raises_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda name: None)
    root = make_install(tmp_path / "gra-\u0142\u00f3d\u017a")  # Polish, not cp1252
    install = launch.resolve_install(root)
    with pytest.raises(launch.CliError) as exc:
        launch.apply_rewrite(install, "wine", "inplace")
    assert exc.value.exit_code == 3
    assert "cannot rewrite" in exc.value.message
