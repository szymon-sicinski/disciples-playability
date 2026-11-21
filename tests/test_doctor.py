"""End-to-end tests for the ``doctor`` subcommand.

Every tree is a synthetic ``tmp_path`` install -- a 2-byte ``MZ`` stub for
``Disciple.exe``, the shared INI fixture, invented folder contents -- never
game bytes. The ``ddraw.dll`` stub is 4 bytes, and its marker digest is
computed at runtime, so no game (or upstream) hash appears as a literal.

The ``wine`` presence is controlled by monkeypatching the lookup and the
``--version`` probe rather than shipping a fake binary, so the status
transitions are tested on both ubuntu and windows. One POSIX-only test drives
the real subprocess path with a shell shim.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

import disciples_play.doctor as doctor
from disciples_play import wrapper
from disciples_play.__main__ import main

WINDOWS = sys.platform == "win32"
FIXTURES = Path(__file__).parent / "fixtures"

FAKE_DLL = b"DLL!"  # 4-byte stub, not the real cnc-ddraw

#: The 15 on-disk folders the installation keys point at, in canonical case.
INSTALLATION_FOLDERS = [
    "Globals",
    "Imgs1",
    "Imgs2",
    "Interf",
    "Scens",
    "Sounds1",
    "Sounds2",
    "Music",
    "Video",
    "ImgData",
    "Campaign",
    "Exports",
    "Savegame",
    "Briefing",
    "Scendata",
]

_HEX_64 = re.compile(r"[0-9a-fA-F]{64}")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ini_bytes() -> bytes:
    return (FIXTURES / "sample-disciple.ini").read_bytes()


def make_install(
    base: Path,
    *,
    exe: bool = True,
    with_wrapper: bool = False,
    wrapper_digest: str | None = None,
    music: int = 25,
    videos: int = 1,
) -> Path:
    """Build a full synthetic install tree under ``base`` and return it."""
    exe_dir = base / "Exe"
    exe_dir.mkdir(parents=True)
    if exe:
        (exe_dir / "Disciple.exe").write_bytes(b"MZ")
    (exe_dir / "DISCIPLE.INI").write_bytes(_ini_bytes())

    for folder in INSTALLATION_FOLDERS:
        (base / folder).mkdir(exist_ok=True)
    for i in range(music):
        (base / "Music" / f"track{i:02d}.wav").write_bytes(b"\x00" * 100)
    for i in range(videos):
        (base / "Video" / f"clip{i:02d}.smk").write_bytes(b"\x00" * 200)
        (base / "Briefing" / f"brief{i:02d}.smk").write_bytes(b"\x00" * 200)

    if with_wrapper:
        (exe_dir / "ddraw.dll").write_bytes(FAKE_DLL)
        recorded = wrapper_digest if wrapper_digest is not None else _sha256(FAKE_DLL)
        marker = {
            "ddraw_dll_sha256": recorded,
            "cnc_ddraw_tag": wrapper.CNC_DDRAW_TAG,
            "pack_version": "0.0.0-test",
        }
        (exe_dir / ".disciples-play-wrapper.json").write_text(json.dumps(marker), encoding="utf-8")
    return base


@pytest.fixture()
def no_wine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``wine`` unresolvable, so the check degrades to WARN."""
    real_which = doctor.shutil.which

    def which(name: str) -> str | None:
        return None if name == "wine" else real_which(name)

    monkeypatch.setattr(doctor.shutil, "which", which)


@pytest.fixture()
def fake_wine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``wine`` resolve and report a synthetic version string."""
    monkeypatch.setattr(
        doctor.shutil, "which", lambda name: "/fake/wine" if name == "wine" else None
    )
    monkeypatch.setattr(doctor, "_wine_version", lambda _path: "wine-9.0 (synthetic)")


@pytest.fixture()
def with_display(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPLAY", ":0")


def _run(root: Path, *extra: str) -> tuple[int, str, str]:
    """Run ``disciples-play doctor`` and return ``(exit_code, stdout, stderr)``."""
    import contextlib
    import io

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(["doctor", "--game-dir", str(root), *extra])
    return code, out.getvalue(), err.getvalue()


def _statuses(out: str) -> dict[str, str]:
    """Map check id -> STATUS from the human one-line-per-check output."""
    result: dict[str, str] = {}
    for line in out.splitlines():
        status, _, rest = line.partition(" ")
        check_id = rest.split(":", 1)[0]
        result[check_id] = status
    return result


# --- fixtures from the card --------------------------------------------------


def test_all_pass_exits_zero(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", with_wrapper=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0

    out = capsys.readouterr().out
    statuses = _statuses(out)
    assert statuses == {
        "install": "PASS",
        "ini": "PASS",
        "ini-paths": "PASS",
        "wine": "PASS",
        "ddraw-override": "PASS",
        "wrapper": "PASS",
        "music": "PASS",
        "video": "PASS",
        "display": "PASS",
    }
    assert "25 .wav files in Music/" in out
    assert "wine-9.0 (synthetic)" in out


def test_missing_exe_is_a_fail(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", exe=False)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1

    out = capsys.readouterr().out
    assert "FAIL install:" in out
    assert "Disciple.exe not found" in out
    # Dependent checks degrade to "cannot check" and also FAIL.
    assert "FAIL ini: cannot check: install not resolved" in out
    assert "FAIL music: cannot check: install not resolved" in out


def test_missing_music_is_a_fail(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", music=0)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1

    out = capsys.readouterr().out
    assert "FAIL music:" in out
    assert "0 .wav files in Music/" in out
    assert "PASS install:" in out  # the install itself is fine


def test_wrapper_digest_mismatch_is_a_warn(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    # Marker records a *different* digest than the dll on disk -> not ours.
    root = make_install(tmp_path / "install", with_wrapper=True, wrapper_digest="0" * 64)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0  # WARN does not fail the run

    out = capsys.readouterr().out
    assert "WARN wrapper:" in out
    assert "not ours" in out
    assert "PASS ddraw-override:" in out  # the DLL being staged still counts


def test_no_wine_is_a_warn(
    tmp_path: Path, no_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install")
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0  # WARN does not fail the run

    out = capsys.readouterr().out
    assert "WARN wine:" in out
    assert "not found on PATH" in out


# --- exit code 2 (bad arguments) --------------------------------------------


def test_no_install_source_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DISCIPLES_GAME_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "no-config"))
    code = main(["doctor"])
    assert code == 2
    assert "no install specified" in capsys.readouterr().err


def test_unknown_doctor_flag_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor", "--bogus"]) == 2


# --- the JSON schema ----------------------------------------------------------


def test_json_schema_is_stable(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", with_wrapper=True)
    code = main(["doctor", "--game-dir", str(root), "--json"])
    assert code == 0

    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"checks", "ok"}
    assert payload["ok"] is True
    assert isinstance(payload["checks"], list)
    assert len(payload["checks"]) == 9

    ids = []
    for check in payload["checks"]:
        assert set(check) == {"id", "status", "detail"}
        assert check["status"] in ("pass", "fail", "warn")
        ids.append(check["id"])
    assert ids == [
        "install",
        "ini",
        "ini-paths",
        "wine",
        "ddraw-override",
        "wrapper",
        "music",
        "video",
        "display",
    ]


def test_json_ok_is_false_when_something_fails(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", music=0)
    code = main(["doctor", "--game-dir", str(root), "--json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


# --- no 64-hex string may leak, on any fixture -------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"exe": False},
        {"music": 0},
        {"with_wrapper": True, "wrapper_digest": "0" * 64},  # a real 64-hex sits in the marker
        {"with_wrapper": True},
    ],
)
def test_output_never_contains_a_64_hex_string(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str], kwargs: dict
) -> None:
    root = make_install(tmp_path / "install", **kwargs)

    for extra in ([], ["--json"]):
        code = main(["doctor", "--game-dir", str(root), *extra])
        out = capsys.readouterr().out
        assert _HEX_64.search(out) is None, f"64-hex leaked in {extra or 'human'} output: {out}"
        assert code in (0, 1)


# --- case-insensitive directory resolution -----------------------------------


def test_ini_paths_resolves_folder_case_insensitively(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install")
    # Re-create one folder with a different case than the INI's canonical name;
    # the check must resolve it rather than report it missing.
    (root / "Globals").rmdir()
    (root / "globals").mkdir()
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0
    assert "PASS ini-paths:" in capsys.readouterr().out


def test_ini_paths_missing_folder_is_a_fail(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install")
    (root / "Scens").rmdir()  # the scenarios key's on-disk folder
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1
    out = capsys.readouterr().out
    assert "FAIL ini-paths:" in out
    assert "scenarios" in out


def test_ini_paths_incomplete_section_is_a_warn(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install")
    # Strip the [InstallationClient] section: only 15 of 21 keys remain.
    text = _ini_bytes().decode("cp1252").split("[InstallationClient]")[0]
    (root / "Exe" / "DISCIPLE.INI").write_bytes(text.encode("cp1252"))
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0  # WARN does not fail the run
    out = capsys.readouterr().out
    assert "WARN ini-paths:" in out
    assert "15 of 21" in out


# --- ddraw override from the environment --------------------------------------


def test_ddraw_override_reads_env(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("WINEDLLOVERRIDES", "ddraw=n,b")
    root = make_install(tmp_path / "install")  # no wrapper staged
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0
    out = capsys.readouterr().out
    assert "PASS ddraw-override:" in out
    assert "WINEDLLOVERRIDES" in out


# --- read-only: the doctor never writes into the install ---------------------


def test_doctor_writes_nothing(tmp_path: Path, fake_wine, with_display) -> None:
    root = make_install(tmp_path / "install", with_wrapper=True)
    before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    ini_before = (root / "Exe" / "DISCIPLE.INI").read_bytes()

    assert main(["doctor", "--game-dir", str(root)]) == 0

    after = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    assert after == before  # no new file (e.g. no DISCIPLE.INI.orig) appeared
    assert (root / "Exe" / "DISCIPLE.INI").read_bytes() == ini_before


# --- the real subprocess path for wine --version (POSIX only) -----------------


@pytest.mark.skipif(
    WINDOWS, reason="fake-wine shim is a POSIX shell script; the monkeypatched path covers windows"
)
def test_wine_version_runs_the_real_probe(tmp_path: Path, exec_tmp_root: Path) -> None:
    bindir = exec_tmp_root / f"winebin-{tmp_path.name}"
    bindir.mkdir(exist_ok=True)
    shim = bindir / "wine"
    shim.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo wine-9.0; exit 0; fi\nexit 1\n')
    shim.chmod(0o755)

    assert doctor._wine_version(str(shim)) == "wine-9.0"
