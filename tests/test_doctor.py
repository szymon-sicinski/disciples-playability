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
import disciples_play.ini as ini
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

_VIDEO_CLIPS = 6
_BRIEFING_CLIPS = 35

_HEX_64 = re.compile(r"[0-9a-fA-F]{64}")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ini_bytes() -> bytes:
    return (FIXTURES / "sample-disciple.ini").read_bytes()


def _with_inwindow(data: bytes, value: str | None) -> bytes:
    """Return the fixture INI with ``[Disciple] InWindow=<value>`` inserted.

    The shared fixture reproduces the synthetic shape the earlier cards tested,
    which predates this key -- the retail ``DISCIPLE.INI`` carries ``InWindow``
    but the fixture does not. Writing it here keeps every other test's fixture
    byte-identical; ``value=None`` leaves the key absent, which is its own WARN.

    The key is inserted under ``[Disciple]`` with CRLF, matching the fixture.
    """
    if value is None:
        return data
    text = data.decode("cp1252")
    marker = "[Disciple]"
    index = text.index(marker) + len(marker)
    return (text[:index] + "\r\nInWindow=" + value + text[index:]).encode("cp1252")


def _relative_ini_bytes() -> bytes:
    """A complete INI whose installation values are bare relative names -- the
    shape plan R1/Q1 records as failing in-game ("unable to load fonts")."""
    lines = ["[Installation]"]
    for key, folder in ini._INSTALLATION_FOLDERS.items():
        lines.append(f"{key}={folder}")
    lines.append("[InstallationClient]")
    for key in doctor._INSTALLATION_CLIENT_KEYS:
        lines.append(f"{key}={ini._INSTALLATION_FOLDERS[key]}")
    return ("\r\n".join(lines) + "\r\n").encode("cp1252")


def make_install(
    base: Path,
    *,
    exe: bool = True,
    with_wrapper: bool = False,
    wrapper_digest: str | None = None,
    music: int = 25,
    video: int = _VIDEO_CLIPS,
    briefing: int = _BRIEFING_CLIPS,
    rewritten: bool = False,
    inwindow: str | None = "0",
) -> Path:
    """Build a full synthetic install tree under ``base`` and return it.

    ``rewritten=True`` writes the INI the launcher would produce (absolute
    Windows paths), so the ``ini-paths`` check PASSes; the default (False)
    keeps the fixture's stale ``X:\\Games\\Heroic\\…`` values, which the check
    must FAIL.

    ``inwindow`` is the ``[Disciple] InWindow`` value written into the INI
    (``"0"`` by default -- the fullscreen baseline); ``None`` leaves the key
    out, and ``"1"`` asks the game for its own window, which needs a staged
    cnc-ddraw to be supported.
    """
    exe_dir = base / "Exe"
    exe_dir.mkdir(parents=True)
    if exe:
        (exe_dir / "Disciple.exe").write_bytes(b"MZ")
    ini_source = _with_inwindow(_ini_bytes(), inwindow)
    if rewritten:
        ini_text = ini.rewrite_installation_paths(ini_source, base.resolve(), "wine")
        (exe_dir / "DISCIPLE.INI").write_bytes(ini_text.encode("cp1252"))
    else:
        (exe_dir / "DISCIPLE.INI").write_bytes(ini_source)

    for folder in INSTALLATION_FOLDERS:
        (base / folder).mkdir(exist_ok=True)
    for i in range(music):
        (base / "Music" / f"track{i:02d}.wav").write_bytes(b"\x00" * 100)
    for i in range(video):
        (base / "Video" / f"clip{i:02d}.smk").write_bytes(b"\x00" * 200)
    for i in range(briefing):
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
    """Make ``wine`` unresolvable, so the check FAILs on POSIX."""
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
    root = make_install(tmp_path / "install", with_wrapper=True, rewritten=True)
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
        "ini-window": "PASS",
        "music": "PASS",
        "video": "PASS",
        "display": "PASS",
    }
    assert "25 .wav files in Music/" in out
    assert "wine-9.0 (synthetic)" in out
    assert "41 .smk files" in out


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
    root = make_install(tmp_path / "install", music=0, rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1

    out = capsys.readouterr().out
    assert "FAIL music:" in out
    assert "0 .wav files in Music/" in out
    assert "PASS install:" in out  # the install itself is fine


def test_missing_video_is_a_fail(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", video=0, briefing=0, rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1

    out = capsys.readouterr().out
    assert "FAIL video:" in out
    assert "0 .smk files" in out
    assert "PASS install:" in out


def test_partial_video_count_is_a_fail(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    """2 of 41 cutscenes must FAIL.

    A truncated install is the case this check exists for, so ``total`` being
    non-zero is not enough: only the exact count is a PASS.
    """
    root = make_install(tmp_path / "install", video=2, briefing=0, rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1

    out = capsys.readouterr().out
    assert "FAIL video:" in out
    assert "2 .smk files" in out
    assert "expected 41" in out
    assert "PASS install:" in out  # the install itself is fine


def test_partial_music_count_is_a_fail(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    """24 of 25 tracks must FAIL, symmetric with the video check."""
    root = make_install(tmp_path / "install", music=24, rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1

    out = capsys.readouterr().out
    assert "FAIL music:" in out
    assert "24 .wav files in Music/" in out
    assert "expected 25" in out
    assert "PASS install:" in out


def test_wrapper_digest_mismatch_is_a_warn(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    # Marker records a *different* digest than the dll on disk -> not ours.
    root = make_install(
        tmp_path / "install", with_wrapper=True, wrapper_digest="0" * 64, rewritten=True
    )
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0  # WARN does not fail the run

    out = capsys.readouterr().out
    assert "WARN wrapper:" in out
    assert "not ours" in out
    assert "PASS ddraw-override:" in out  # the DLL being staged still counts


@pytest.mark.skipif(WINDOWS, reason="wine check PASSes on Windows (not needed to launch)")
def test_no_wine_is_a_fail(
    tmp_path: Path, no_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1  # no wine on POSIX blocks launch

    out = capsys.readouterr().out
    assert "FAIL wine:" in out
    assert "not found on PATH" in out
    assert "--print-command still works" in out


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


def test_game_dir_before_subcommand_is_honored(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", with_wrapper=True, rewritten=True)
    code = main(["--game-dir", str(root), "doctor"])
    assert code == 0  # was exit 2 "no install specified" before the fix
    assert "PASS install:" in capsys.readouterr().out


# --- the JSON schema ----------------------------------------------------------


def test_json_schema_is_stable(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", with_wrapper=True, rewritten=True)
    code = main(["doctor", "--game-dir", str(root), "--json"])
    assert code == 0

    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"checks", "ok"}
    assert payload["ok"] is True
    assert isinstance(payload["checks"], list)
    assert len(payload["checks"]) == 10

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
        "ini-window",
        "music",
        "video",
        "display",
    ]


def test_json_ok_is_false_when_something_fails(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", music=0, rewritten=True)
    code = main(["doctor", "--game-dir", str(root), "--json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


def test_json_ok_true_when_only_warnings(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(
        tmp_path / "install", with_wrapper=True, wrapper_digest="0" * 64, rewritten=True
    )
    code = main(["doctor", "--game-dir", str(root), "--json"])
    assert code == 0  # only a WARN, not a FAIL
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True


# --- no 64-hex string may leak, on any fixture -------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rewritten": True},
        {"exe": False},
        {"music": 0, "rewritten": True},
        {"with_wrapper": True, "wrapper_digest": "0" * 64, "rewritten": True},
        {"with_wrapper": True, "rewritten": True},
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


# --- ini-paths: values are resolved, not key -> folder mapped -----------------


def test_ini_paths_resolves_folder_case_insensitively(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", rewritten=True)
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
    root = make_install(tmp_path / "install", rewritten=True)
    (root / "Scens").rmdir()  # the scenarios key's on-disk folder
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1
    out = capsys.readouterr().out
    assert "FAIL ini-paths:" in out
    assert "scenarios" in out


def test_ini_paths_stale_values_are_a_fail(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    # The raw fixture's values point at X:\Games\Heroic\… (a drive that does
    # not exist here): the defect the launcher exists to fix must not PASS.
    root = make_install(tmp_path / "install")  # rewritten=False
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1
    out = capsys.readouterr().out
    assert "FAIL ini-paths:" in out
    assert "do not resolve to this install" in out
    assert "run disciples-play" in out


def test_ini_paths_relative_values_are_a_fail(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install")
    (root / "Exe" / "DISCIPLE.INI").write_bytes(_relative_ini_bytes())
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1
    out = capsys.readouterr().out
    assert "FAIL ini-paths:" in out
    assert "relative installation paths" in out
    assert "unable to load fonts" not in out  # no prose about fonts leaks; the hint is the rewrite


def test_ini_paths_missing_key_is_a_fail(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", rewritten=True)
    text = (root / "Exe" / "DISCIPLE.INI").read_bytes().decode("cp1252")
    lines = [ln for ln in text.split("\r\n") if not ln.startswith("scenarios=")]
    (root / "Exe" / "DISCIPLE.INI").write_bytes("\r\n".join(lines).encode("cp1252"))
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1
    out = capsys.readouterr().out
    assert "FAIL ini-paths:" in out
    assert "missing installation keys" in out
    assert "scenarios" in out


def test_ini_paths_missing_client_section_is_a_fail(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", rewritten=True)
    # Strip the whole [InstallationClient] section: the six client keys vanish.
    text = (
        (root / "Exe" / "DISCIPLE.INI")
        .read_bytes()
        .decode("cp1252")
        .split("[InstallationClient]")[0]
    )
    (root / "Exe" / "DISCIPLE.INI").write_bytes(text.encode("cp1252"))
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1
    out = capsys.readouterr().out
    assert "FAIL ini-paths:" in out
    assert "missing installation keys" in out
    assert "[InstallationClient]" in out


def test_ini_paths_extra_key_is_a_warn(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", rewritten=True)
    text = (root / "Exe" / "DISCIPLE.INI").read_bytes().decode("cp1252")
    text = text.replace("globals=", "foobar=\r\nglobals=", 1)
    (root / "Exe" / "DISCIPLE.INI").write_bytes(text.encode("cp1252"))
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0  # extra keys are a WARN, not a FAIL
    out = capsys.readouterr().out
    assert "WARN ini-paths:" in out
    assert "extra installation keys" in out
    assert "foobar" in out


def test_ini_paths_client_section_value_is_checked(
    tmp_path: Path, fake_wine, with_display, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_install(tmp_path / "install", rewritten=True)
    # Corrupt only the [InstallationClient] globals value to a bare relative
    # name; the [Installation] value stays correct. The check must catch it.
    lines = (root / "Exe" / "DISCIPLE.INI").read_bytes().decode("cp1252").split("\r\n")
    in_client = False
    for i, line in enumerate(lines):
        if line == "[InstallationClient]":
            in_client = True
            continue
        if in_client and line.startswith("globals="):
            lines[i] = "globals=Globals"
            break
    (root / "Exe" / "DISCIPLE.INI").write_bytes("\r\n".join(lines).encode("cp1252"))
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 1
    out = capsys.readouterr().out
    assert "FAIL ini-paths:" in out
    assert "relative installation paths" in out
    assert "globals=Globals" in out


# --- ddraw override: parse the value, don't substring-match --------------------


@pytest.mark.parametrize("override", ["ddraw=b", "ddraw=d", "ddraw=", "notddraw=n", "*=n"])
def test_ddraw_override_rejects_non_native(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    override: str,
) -> None:
    monkeypatch.setenv("WINEDLLOVERRIDES", override)
    root = make_install(tmp_path / "install", rewritten=True)  # no wrapper staged
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0  # a missing override is a WARN, not a FAIL
    out = capsys.readouterr().out
    assert "PASS ddraw-override:" not in out
    assert "WARN ddraw-override:" in out


def test_ddraw_override_reads_env(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("WINEDLLOVERRIDES", "ddraw=n,b")
    root = make_install(tmp_path / "install", rewritten=True)  # no wrapper staged
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0
    out = capsys.readouterr().out
    assert "PASS ddraw-override:" in out
    assert "WINEDLLOVERRIDES" in out


# --- ini-window: the game's own display mode ----------------------------------
#
# ``InWindow`` selects the game's own window mode; windowed presentation comes
# from cnc-ddraw. So ``InWindow=1`` without a staged wrapper is an unsupported
# configuration -- a WARN -- but it is NOT the cause of the start-up crash at
# 0059559E (that crash happens with InWindow=0 as well; display mode was tested
# and falsified). These tests pin the verdicts and the wording, and the last one
# asserts the check never claims to prevent a crash.

WINDOWED_NEEDS_WRAPPER = (
    "windowed presentation needs cnc-ddraw; the launcher does not write this key"
)


def _line_for(out: str, check_id: str) -> str:
    """Return the single output line for ``check_id``."""
    (line,) = [ln for ln in out.splitlines() if ln.split(":", 1)[0].endswith(f" {check_id}")]
    return line


def test_ini_window_windowed_without_wrapper_is_a_warn(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("WINEDLLOVERRIDES", raising=False)  # no env route either
    root = make_install(tmp_path / "install", inwindow="1", rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0  # a WARN does not fail the run

    out = capsys.readouterr().out
    assert "WARN ini-window:" in out
    assert WINDOWED_NEEDS_WRAPPER in out
    assert "InWindow=0" in out  # and how to set it
    assert "PASS ini-window:" not in out


def test_ini_window_windowed_without_wrapper_claims_no_crash(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The display-mode theory of the start-up crash was falsified: say nothing."""
    monkeypatch.delenv("WINEDLLOVERRIDES", raising=False)
    root = make_install(tmp_path / "install", inwindow="1", rewritten=True)
    assert main(["doctor", "--game-dir", str(root)]) == 0

    line = _line_for(capsys.readouterr().out, "ini-window").lower()
    assert "warn ini-window" in line
    for forbidden in ("crash", "0059559e", "c0000005", "start-up"):
        assert forbidden not in line


def test_ini_window_fullscreen_is_a_pass(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("WINEDLLOVERRIDES", raising=False)
    root = make_install(tmp_path / "install", inwindow="0", rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0

    out = capsys.readouterr().out
    assert "PASS ini-window: [Disciple] InWindow=0" in out
    assert "WARN ini-window:" not in out


def test_ini_window_missing_key_is_a_warn(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("WINEDLLOVERRIDES", raising=False)
    root = make_install(tmp_path / "install", inwindow=None, rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0  # unknown, not a defect

    out = capsys.readouterr().out
    assert "WARN ini-window:" in out
    assert "no [Disciple] InWindow key" in out
    assert "retail default is unknown" in out
    assert WINDOWED_NEEDS_WRAPPER in out
    assert "InWindow=0" in out


def test_ini_window_windowed_with_wrapper_is_a_pass(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With cnc-ddraw staged, windowed presentation is supported -- no WARN."""
    monkeypatch.delenv("WINEDLLOVERRIDES", raising=False)
    root = make_install(tmp_path / "install", with_wrapper=True, inwindow="1", rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0

    out = capsys.readouterr().out
    assert "PASS ini-window:" in out
    assert "with cnc-ddraw staged" in out
    assert "WARN ini-window:" not in out


def test_ini_window_windowed_with_env_override_is_a_pass(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The env override is the other way a ddraw route exists; it counts too."""
    monkeypatch.setenv("WINEDLLOVERRIDES", "ddraw=n,b")
    root = make_install(tmp_path / "install", inwindow="1", rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0

    out = capsys.readouterr().out
    assert "PASS ini-window:" in out
    assert "WINEDLLOVERRIDES=" in out
    assert "WARN ini-window:" not in out


def test_ini_window_key_is_matched_case_insensitively(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The retail INI writes ``InWindow``; a lowercased hand edit means the same."""
    monkeypatch.delenv("WINEDLLOVERRIDES", raising=False)
    root = make_install(tmp_path / "install", inwindow="1", rewritten=True)
    ini_file = root / "Exe" / "DISCIPLE.INI"
    ini_file.write_bytes(ini_file.read_bytes().replace(b"InWindow=1", b"inwindow=1"))
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0

    out = capsys.readouterr().out
    assert "WARN ini-window:" in out
    assert WINDOWED_NEEDS_WRAPPER in out


def test_ini_window_unrecognised_value_is_a_warn(
    tmp_path: Path,
    fake_wine,
    with_display,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("WINEDLLOVERRIDES", raising=False)
    root = make_install(tmp_path / "install", inwindow="2", rewritten=True)
    code = main(["doctor", "--game-dir", str(root)])
    assert code == 0

    out = capsys.readouterr().out
    assert "WARN ini-window:" in out
    assert "neither 0 nor 1" in out
    assert "PASS ini-window:" not in out


# --- read-only: the doctor never writes into the install ---------------------


def test_doctor_writes_nothing(tmp_path: Path, fake_wine, with_display) -> None:
    root = make_install(tmp_path / "install", with_wrapper=True, rewritten=True)
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
