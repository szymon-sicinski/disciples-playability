"""Tests for the lossless INI model and the installation-path rewriter.

Every fixture is synthetic -- generated for these tests, never read from a game
install -- and no test touches a real installation directory.

The 21 installation keys use the measured key names, and the fixture reproduces
the measured shape of the real file (4 sections, 41 keys, CRLF, lowercase keys,
``key=value`` with no spacing) with invented, scrubbed values. The default
operation rewrites a stale absolute INI to the install's actual location as
absolute Windows paths (``path_style="wine"``); relative emission is kept behind
an explicit flag and covered separately.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

import disciples_play.ini as ini

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Read a fixture verbatim (``newline=""`` keeps CRLF intact)."""
    return (FIXTURES / name).open(encoding="utf-8", newline="").read()


def crlf(*lines: str) -> str:
    """Join lines with CRLF and a trailing CRLF, like a Windows INI."""
    return "\r\n".join(lines) + "\r\n"


def path_assignments(text: str) -> list[tuple[str, str]]:
    """Return (key, value) for assignments in the two installation sections."""
    out: list[tuple[str, str]] = []
    section: str | None = None
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        stripped = content.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].lower()
            continue
        if section in ("installation", "installationclient"):
            if "=" in content:
                key, _, value = content.partition("=")
                out.append((key.strip(), value.lstrip()))
    return out


def section_block(text: str, name: str) -> str:
    """Return the text of one ``[name]`` section, header included."""
    lines = text.splitlines(keepends=True)
    start: int | None = None
    end: int | None = None
    for i, line in enumerate(lines):
        stripped = line.rstrip("\r\n").strip()
        if stripped == f"[{name}]":
            start = i
        elif start is not None and stripped.startswith("[") and stripped.endswith("]"):
            end = i
            break
    if start is None:
        return ""
    return "".join(lines[start : end if end is not None else len(lines)])


def test_round_trip_is_byte_identical() -> None:
    text = crlf(
        "; a comment",
        "",
        "[Disciple]",
        "language = english",
        "musicvolume=5",
        "",
        "[Installation]",
        "globals=X:\\Games\\Heroic\\Disciples Gold\\globals",
    )
    assert ini.parse(text).to_text() == text


def test_round_trip_preserves_missing_trailing_newline() -> None:
    text = "[Disciple]\r\nlanguage=english"  # no final CRLF
    assert ini.parse(text).to_text() == text


def test_fixture_has_expected_shape() -> None:
    text = load_fixture("sample-disciple.ini")
    assert text.count("\r\n") == text.count("\n")  # every newline is CRLF
    assert len(path_assignments(text)) == 21
    for name in ("[Disciple]", "[CDROM]", "[Installation]", "[InstallationClient]"):
        assert name in text
    assert section_block(text, "Disciple").count("=") == 19
    assert section_block(text, "CDROM").count("=") == 1


def test_relative_style_normalises_all_21_keys() -> None:
    rewritten = ini.rewrite_installation_paths(
        load_fixture("sample-disciple.ini"), path_style="relative"
    )
    assignments = path_assignments(rewritten)
    assert len(assignments) == 21
    folders = {key: value for key, value in assignments}
    assert folders["globals"] == "Globals"
    assert folders["imgs1"] == "Imgs1"
    assert folders["imgs2"] == "Imgs2"
    assert folders["interf"] == "Interf"
    assert folders["scenarios"] == "Scens"
    assert folders["sounds1"] == "Sounds1"
    assert folders["sounds2"] == "Sounds2"
    assert folders["music"] == "Music"
    assert folders["video"] == "Video"
    assert folders["imgdata"] == "ImgData"
    assert folders["campaign"] == "Campaign"
    assert folders["exports"] == "Exports"
    assert folders["savegame"] == "Savegame"
    assert folders["briefing"] == "Briefing"
    assert folders["scendata"] == "Scendata"
    assert all(":" not in value and "\\" not in value for value in folders.values())


def test_absolute_wine_is_the_default_style(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda _name: None)
    text = crlf("[Installation]", "globals=X:\\Games\\Disciples Gold\\globals")
    out = ini.rewrite_installation_paths(text, "/home/user/Disciples Gold")  # no style
    assert "globals=Z:\\home\\user\\Disciples Gold\\Globals" in out


def test_default_style_requires_install_dir() -> None:
    with pytest.raises(ValueError):
        ini.rewrite_installation_paths("[Installation]\r\nglobals=Globals\r\n")


def test_repairs_a_stale_absolute_ini_to_new_root(monkeypatch: pytest.MonkeyPatch) -> None:
    # The failure mode in the field: a GOG/Heroic install with X:\ paths.
    monkeypatch.setattr(ini.shutil, "which", lambda _name: None)
    text = crlf(
        "[Installation]",
        "globals=X:\\Games\\Heroic\\Disciples Gold\\globals",
        "scenarios=X:\\Games\\Heroic\\Disciples Gold\\scenarios",
        "[InstallationClient]",
        "music=X:\\Games\\Heroic\\Disciples Gold\\music",
    )
    out = ini.rewrite_installation_paths(text, "/new/root", "wine")
    assert "globals=Z:\\new\\root\\Globals\r\n" in out
    assert "scenarios=Z:\\new\\root\\Scens\r\n" in out
    assert "music=Z:\\new\\root\\Music\r\n" in out


def test_move_installment_only_the_21_values_differ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda _name: None)
    original = load_fixture("sample-disciple.ini")
    rewritten = ini.rewrite_installation_paths(original, "/new/root", "wine")
    before = original.splitlines(keepends=True)
    after = rewritten.splitlines(keepends=True)
    assert len(before) == len(after)
    changed = [(left, right) for left, right in zip(before, after, strict=True) if left != right]
    assert len(changed) == 21
    for left, right in changed:
        eq = left.find("=")
        assert eq >= 0
        assert right[: eq + 1] == left[: eq + 1]  # only the value part differs
        assert right[eq + 1 :].lstrip().startswith("Z:\\new\\root\\")


def test_disciple_and_cdrom_sections_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda _name: None)
    original = load_fixture("sample-disciple.ini")
    rewritten = ini.rewrite_installation_paths(original, "/new/root")
    for name in ("Disciple", "CDROM"):
        assert section_block(rewritten, name) == section_block(original, name)


def test_unknown_section_preserved() -> None:
    text = crlf(
        "[Weird]",
        "key=value",
        "[Installation]",
        "globals=X:\\Games\\Disciples Gold\\globals",
    )
    out = ini.rewrite_installation_paths(text, path_style="relative")
    assert "[Weird]\r\nkey=value\r\n" in out


def test_missing_section_tolerated_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    text = crlf("[Disciple]", "language=english")
    with caplog.at_level("WARNING"):
        out = ini.rewrite_installation_paths(text, path_style="relative")
    assert out == text
    assert "installation-path sections missing" in caplog.text


def test_equals_and_equals_space_both_read() -> None:
    text = crlf(
        "[Installation]",
        "globals=X:\\old\\globals",
        "imgs1 = X:\\old\\imgs1",
    )
    out = ini.rewrite_installation_paths(text, path_style="relative")
    assert "globals=Globals\r\n" in out
    assert "imgs1 = Imgs1\r\n" in out  # spacing preserved


def test_comment_only_and_empty_value_lines_kept() -> None:
    text = crlf(
        "[Installation]",
        "; a comment on its own line",
        "globals=X:\\old\\globals",
        "",
        "empty=",
        "[Disciple]",
        "language=english",
    )
    out = ini.rewrite_installation_paths(text, path_style="relative")
    assert "; a comment on its own line\r\n" in out
    assert "empty=\r\n" in out  # empty value preserved, not rewritten


def test_crlf_preserved_across_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda _name: None)
    original = load_fixture("sample-disciple.ini")
    rewritten = ini.rewrite_installation_paths(original, "/new/root")
    assert rewritten.count("\r\n") == original.count("\r\n")
    assert rewritten.count("\n") == rewritten.count("\r\n")  # no bare LF introduced


def test_unknown_key_falls_back_and_warns(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda _name: None)
    text = crlf("[Installation]", "somesuch=X:\\old\\somefolder")
    with caplog.at_level("WARNING"):
        out = ini.rewrite_installation_paths(text, "/new", "wine")
    assert "somesuch=Z:\\new\\Somefolder" in out
    assert "no canonical folder for key 'somesuch'" in caplog.text


def test_wine_style_emits_absolute_z_drive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda _name: None)
    text = crlf("[Installation]", "globals=X:\\old\\globals")
    out = ini.rewrite_installation_paths(text, "/home/user/Disciples Gold", "wine")
    assert "globals=Z:\\home\\user\\Disciples Gold\\Globals" in out


def test_wine_style_uses_winepath_shim(monkeypatch: pytest.MonkeyPatch) -> None:
    # A "fake winepath shim on PATH" is simulated by patching the two seams --
    # discovery (shutil.which) and invocation (subprocess.run) -- rather than
    # executing a real script: CI has no winepath, and this sandbox mounts
    # /tmp noexec, so a real shim could neither be found nor run portably.
    captured: list[list[str]] = []

    def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess:
        captured.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="C:\\Prefix\\game\n", stderr="")

    monkeypatch.setattr(ini.shutil, "which", lambda _name: "/usr/bin/winepath")
    monkeypatch.setattr(ini.subprocess, "run", fake_run)
    out = ini.rewrite_installation_paths(
        crlf("[Installation]", "globals=X:\\old\\globals"),
        "/any/posix/dir",
        "wine",
    )
    assert captured == [["/usr/bin/winepath", "-w", "/any/posix/dir"]]
    assert "globals=C:\\Prefix\\game\\Globals" in out


def test_winepath_failure_falls_back_to_z_drive(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_run(args: list[str], **_: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="boom")

    monkeypatch.setattr(ini.shutil, "which", lambda _name: "/usr/bin/winepath")
    monkeypatch.setattr(ini.subprocess, "run", failing_run)
    out = ini.rewrite_installation_paths(
        crlf("[Installation]", "globals=X:\\old\\globals"),
        "/home/user/Disciples Gold",
        "wine",
    )
    assert "globals=Z:\\home\\user\\Disciples Gold\\Globals" in out


def test_wine_style_requires_install_dir() -> None:
    with pytest.raises(ValueError):
        ini.rewrite_installation_paths("[Installation]\r\nglobals=Globals\r\n", path_style="wine")


def test_relative_style_warns_when_install_dir_passed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    text = crlf("[Installation]", "globals=X:\\old\\globals")
    with caplog.at_level("WARNING"):
        out = ini.rewrite_installation_paths(text, "/ignored", "relative")
    assert "install_dir is ignored" in caplog.text
    assert "globals=Globals\r\n" in out


def test_unknown_path_style_raises() -> None:
    with pytest.raises(ValueError):
        ini.rewrite_installation_paths("x", path_style="nope")


def test_parse_accepts_bytes_and_decodes_cp1252() -> None:
    raw = b"[Disciple]\r\nDefPlayer=Szymon M\xfcller\r\n"
    assert ini.parse(raw).to_text() == "[Disciple]\r\nDefPlayer=Szymon Müller\r\n"


def test_parse_rejects_other_types() -> None:
    with pytest.raises(TypeError):
        ini.parse(42)  # type: ignore[arg-type]


def test_read_ini_preserves_crlf_and_cp1252(tmp_path: Path) -> None:
    target = tmp_path / "DISCIPLE.INI"
    target.write_bytes(b"[Disciple]\r\nDefPlayer=Szymon M\xfcller\r\n")
    text = ini.read_ini(target)
    assert text == "[Disciple]\r\nDefPlayer=Szymon Müller\r\n"
    assert text.count("\r\n") == 2
    assert text.replace("\r\n", "").count("\n") == 0  # no bare LF survived


def test_write_ini_encodes_cp1252_by_default(tmp_path: Path) -> None:
    target = tmp_path / "DISCIPLE.INI"
    ini.write_ini(target, "DefPlayer=Szymon Müller\r\n", mode="inplace")
    assert target.read_bytes() == b"DefPlayer=Szymon M\xfcller\r\n"


def test_write_ini_encoding_override(tmp_path: Path) -> None:
    target = tmp_path / "DISCIPLE.INI"
    ini.write_ini(target, "DefPlayer=Szymon Müller\r\n", mode="inplace", encoding="utf-8")
    # ü is 0xFC in cp1252 but 0xC3 0xBC in UTF-8, so this proves the override
    assert target.read_bytes() == b"DefPlayer=Szymon M\xc3\xbcller\r\n"


def test_unknown_mode_raises(tmp_path: Path) -> None:
    target = tmp_path / "DISCIPLE.INI"
    target.write_bytes(b"old\r\n")
    with pytest.raises(ValueError):
        ini.write_ini(target, "new\r\n", mode="nope")


def test_copy_tree_raises(tmp_path: Path) -> None:
    target = tmp_path / "DISCIPLE.INI"
    target.write_bytes(b"old\r\n")
    with pytest.raises(NotImplementedError):
        ini.write_ini(target, "new\r\n", mode="copy-tree")


def test_backup_orig_created_once_not_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "DISCIPLE.INI"
    target.write_bytes(b"[Disciple]\r\nlanguage=english\r\n")
    ini.write_ini(target, "[Disciple]\r\nlanguage=french\r\n", mode="backup")
    orig = tmp_path / "DISCIPLE.INI.orig"
    assert orig.read_bytes() == b"[Disciple]\r\nlanguage=english\r\n"
    # a second, different write must not overwrite the original
    ini.write_ini(target, "[Disciple]\r\nlanguage=german\r\n", mode="backup")
    assert orig.read_bytes() == b"[Disciple]\r\nlanguage=english\r\n"
    assert target.read_bytes() == b"[Disciple]\r\nlanguage=german\r\n"


def test_inplace_never_backs_up(tmp_path: Path) -> None:
    target = tmp_path / "DISCIPLE.INI"
    target.write_bytes(b"old\r\n")
    ini.write_ini(target, "new\r\n", mode="inplace")
    assert target.read_bytes() == b"new\r\n"
    assert not (tmp_path / "DISCIPLE.INI.orig").exists()


def test_idempotent_second_write_no_mtime_change(tmp_path: Path) -> None:
    target = tmp_path / "DISCIPLE.INI"
    target.write_bytes(b"[Disciple]\r\nlanguage=english\r\n")
    new_text = "[Disciple]\r\nlanguage=french\r\n"
    assert ini.write_ini(target, new_text, mode="backup") is True
    mtime_before = target.stat().st_mtime_ns
    time.sleep(0.02)
    assert ini.write_ini(target, new_text, mode="backup") is False
    assert target.stat().st_mtime_ns == mtime_before


def test_rewrite_is_idempotent() -> None:
    once = ini.rewrite_installation_paths(
        load_fixture("sample-disciple.ini"), path_style="relative"
    )
    twice = ini.rewrite_installation_paths(once, path_style="relative")
    assert twice == once


def test_absolute_rewrite_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ini.shutil, "which", lambda _name: None)
    once = ini.rewrite_installation_paths(load_fixture("sample-disciple.ini"), "/new/root", "wine")
    twice = ini.rewrite_installation_paths(once, "/new/root", "wine")
    assert twice == once


def test_rewritten_key_count_counts_only_changed_install_values() -> None:
    before = crlf(
        "[Installation]",
        "globals=X:\\\\old\\\\globals",
        "imgs1=X:\\\\old\\\\imgs1",
        "[Disciple]",
        "language=english",
    )
    after = crlf(
        "[Installation]",
        "globals=Z:\\\\new\\\\Globals",
        "imgs1=X:\\\\old\\\\imgs1",  # already at the target: unchanged
        "[Disciple]",
        "language=english",
    )
    assert ini.rewritten_key_count(before, after) == 1


def test_rewritten_key_count_idempotent_is_zero() -> None:
    text = crlf("[Installation]", "globals=X:\\\\old\\\\globals")
    once = ini.rewrite_installation_paths(text, path_style="relative")
    assert ini.rewritten_key_count(text, once) == 1
    assert ini.rewritten_key_count(once, once) == 0
