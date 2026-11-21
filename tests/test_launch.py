"""Unit tests for install resolution and launch assembly in ``launch.py``.

These exercise the pure parts directly; the end-to-end CLI behaviour (exit
codes, the fake-``wine`` shim, copy-tree) is covered in ``test_cli.py``. All
trees are synthetic ``tmp_path`` fixtures -- no game bytes.
"""

from __future__ import annotations

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
