"""Tests for the cnc-ddraw preset, pinned fetch and wrapper installation.

Every fixture is synthetic: a release zip is built here in memory with a fake
4-byte ``ddraw.dll``, never the real upstream asset, and no test touches a game
installation directory. The digest used by the mismatch test is computed at
runtime, so no game -- or upstream -- hash appears as a literal anywhere.
"""

from __future__ import annotations

import configparser
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import pytest

import disciples_play.wrapper as wrapper

FAKE_DLL = b"DLL!"  # 4 bytes, as the card specifies


def make_zip() -> bytes:
    """Build a synthetic release zip in memory, including entries to skip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ddraw.dll", FAKE_DLL)
        zf.writestr("ddraw.ini", "[ddraw]\nwindowed=false\n")
        zf.writestr("LICENSE.txt", "MIT (synthetic fixture)\n")
        # Entries the extractor must skip:
        zf.writestr("cnc-ddraw config.exe", b"\x00" * 8)
        zf.writestr("Shaders/interpolation/bilinear.glsl", "void main() {}\n")
    return buf.getvalue()


def make_zip_with(extra: dict[str, bytes]) -> bytes:
    """Build a synthetic release zip plus the given extra entries."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ddraw.dll", FAKE_DLL)
        zf.writestr("ddraw.ini", "[ddraw]\nwindowed=false\n")
        for name, data in extra.items():
            zf.writestr(name, data)
    return buf.getvalue()


def make_zip_with_symlink() -> bytes:
    """Build a zip whose ``ddraw.ini`` member is a symlink (``S_IFLNK``)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ddraw.dll", FAKE_DLL)
        info = zipfile.ZipInfo("ddraw.ini")
        info.external_attr = 0o120777 << 16  # S_IFLNK file type, rwxrwxrwx
        zf.writestr(info, "/etc/passwd")
    return buf.getvalue()


def make_zip_with_corrupt_payload() -> bytes:
    """Build a zip whose central directory is intact but a member's CRC is bad.

    The ``ddraw.dll`` payload is written *stored* (uncompressed) so its bytes
    appear verbatim, then one byte is flipped: reading the member fails its
    CRC-32 check with ``BadZipFile`` while the central directory still parses.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("ddraw.dll", FAKE_DLL)
        zf.writestr("ddraw.ini", "[ddraw]\nwindowed=false\n")
    data = bytearray(buf.getvalue())
    idx = data.find(FAKE_DLL)
    assert idx != -1, "FAKE_DLL not found verbatim in the stored archive"
    data[idx] ^= 0xFF
    return bytes(data)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_zip(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def staged_dir(tmp_path: Path, name: str = "staging") -> Path:
    staging = tmp_path / name
    staging.mkdir()
    (staging / "ddraw.dll").write_bytes(FAKE_DLL)
    (staging / "ddraw.ini").write_text("[ddraw]\nwindowed=false\n")
    return staging


# --- build_preset -----------------------------------------------------------


def test_preset_parses_as_ini_and_uses_only_documented_keys() -> None:
    text = wrapper.build_preset()
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(text)
    assert "ddraw" in parser
    keys = set(parser["ddraw"])
    assert wrapper.PRESET_KEYS <= keys
    assert keys <= wrapper.ALLOWED_KEYS
    section = parser["ddraw"]
    assert section["windowed"] == "1"
    assert section["maintas"] == "1"
    assert section["maxfps"] == "60"
    assert section["vsync"] == "1"
    assert section["adjmouse"] == "1"
    assert section["savesettings"] == "1"
    assert section["nonexclusive"] == "1"
    assert section["hook"] == "4"
    assert section["renderer"] == "auto"


def test_preset_documented_keys_match_constant() -> None:
    assert wrapper.PRESET_KEYS == {
        "windowed",
        "maintas",
        "maxfps",
        "vsync",
        "adjmouse",
        "savesettings",
        "nonexclusive",
        "hook",
        "renderer",
    }


def test_preset_comment_names_pack_tag_and_hotkeys() -> None:
    text = wrapper.build_preset()
    assert wrapper.__version__ in text
    assert wrapper.CNC_DDRAW_TAG in text
    assert "Alt+Enter" in text
    assert "Ctrl+Tab" in text


def test_preset_parameters_flow_through() -> None:
    text = wrapper.build_preset(scale=2, maxfps=30, vsync=False, adjmouse=False, renderer="gdi")
    assert "2x (1280x960)" in text
    assert "maxfps=30\n" in text
    assert "vsync=0\n" in text
    assert "adjmouse=0\n" in text
    assert "renderer=gdi\n" in text


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "3"])
def test_preset_rejects_bad_scale(bad) -> None:
    with pytest.raises(ValueError):
        wrapper.build_preset(scale=bad)  # type: ignore[arg-type]


def test_preset_rejects_unknown_renderer() -> None:
    with pytest.raises(ValueError):
        wrapper.build_preset(renderer="vulkan")


@pytest.mark.parametrize("renderer", sorted(wrapper._RENDERERS))
def test_preset_accepts_every_upstream_renderer(renderer: str) -> None:
    text = wrapper.build_preset(renderer=renderer)
    assert f"renderer={renderer}\n" in text


def test_preset_rejects_bad_maxfps() -> None:
    with pytest.raises(ValueError):
        wrapper.build_preset(maxfps=-2)


# --- fetch_wrapper ----------------------------------------------------------


def test_fetch_extracts_only_wanted_files(tmp_path: Path) -> None:
    data = make_zip()
    staged = tmp_path / "staging"
    result = wrapper.fetch_wrapper(
        staged,
        offline_zip=write_zip(tmp_path / "asset.zip", data),
        expected_sha256=digest(data),
        expected_size=len(data),
    )
    assert sorted(result) == ["LICENSE.txt", "ddraw.dll", "ddraw.ini"]
    assert (staged / "ddraw.dll").read_bytes() == FAKE_DLL
    assert (staged / "ddraw.ini").exists()
    assert (staged / "LICENSE.txt").exists()
    # Entries that must be skipped:
    assert not (staged / "cnc-ddraw config.exe").exists()
    assert not (staged / "Shaders").exists()


def test_fetch_digest_mismatch_raises_and_extracts_nothing(tmp_path: Path) -> None:
    data = make_zip()
    staged = tmp_path / "staging"
    with pytest.raises(wrapper.WrapperFetchError):
        wrapper.fetch_wrapper(
            staged,
            offline_zip=write_zip(tmp_path / "asset.zip", data),
            expected_sha256="0" * 64,
            expected_size=len(data),
        )
    assert not staged.exists()  # nothing staged on mismatch


def test_fetch_rejects_zip_slip_entry(tmp_path: Path) -> None:
    data = make_zip_with({"../../evil.dll": b"EVIL"})
    staged = tmp_path / "staging"
    with pytest.raises(wrapper.WrapperFetchError):
        wrapper.fetch_wrapper(
            staged,
            offline_zip=write_zip(tmp_path / "asset.zip", data),
            expected_sha256=digest(data),
            expected_size=len(data),
        )
    assert not (tmp_path / "evil.dll").exists()
    assert not (tmp_path.parent / "evil.dll").exists()


def test_fetch_rejects_absolute_entry(tmp_path: Path) -> None:
    data = make_zip_with({"/tmp/evil.dll": b"EVIL"})
    with pytest.raises(wrapper.WrapperFetchError):
        wrapper.fetch_wrapper(
            tmp_path / "staging",
            offline_zip=write_zip(tmp_path / "asset.zip", data),
            expected_sha256=digest(data),
            expected_size=len(data),
        )


def test_fetch_rejects_missing_offline_zip(tmp_path: Path) -> None:
    with pytest.raises(wrapper.WrapperFetchError):
        wrapper.fetch_wrapper(tmp_path / "staging", offline_zip=tmp_path / "nope.zip")


def test_fetch_rejects_invalid_zip(tmp_path: Path) -> None:
    data = b"this is not a zip"
    with pytest.raises(wrapper.WrapperFetchError):
        wrapper.fetch_wrapper(
            tmp_path / "staging",
            offline_zip=write_zip(tmp_path / "asset.zip", data),
            expected_sha256=digest(data),
            expected_size=len(data),
        )


def test_fetch_rejects_size_mismatch(tmp_path: Path) -> None:
    data = make_zip()
    staged = tmp_path / "staging"
    with pytest.raises(wrapper.WrapperFetchError, match="unexpected size"):
        wrapper.fetch_wrapper(
            staged,
            offline_zip=write_zip(tmp_path / "asset.zip", data),
            expected_sha256=digest(data),
            expected_size=len(data) + 1,
        )
    assert not staged.exists()  # nothing staged on size mismatch


def test_fetch_rejects_symlink_entry(tmp_path: Path) -> None:
    data = make_zip_with_symlink()
    staged = tmp_path / "staging"
    with pytest.raises(wrapper.WrapperFetchError, match="symlink"):
        wrapper.fetch_wrapper(
            staged,
            offline_zip=write_zip(tmp_path / "asset.zip", data),
            expected_sha256=digest(data),
            expected_size=len(data),
        )
    assert not (staged / "ddraw.ini").exists()  # symlink refused, nothing written


def test_fetch_corrupt_payload_raises_and_leaves_nothing(tmp_path: Path) -> None:
    data = make_zip_with_corrupt_payload()
    staged = tmp_path / "staging"
    with pytest.raises(wrapper.WrapperFetchError):
        wrapper.fetch_wrapper(
            staged,
            offline_zip=write_zip(tmp_path / "asset.zip", data),
            expected_sha256=digest(data),
            expected_size=len(data),
        )
    # The corrupt member (bad CRC) must not leave a half-written ddraw.dll.
    assert not (staged / "ddraw.dll").exists()


def test_allowed_host_accepts_github_and_rejects_foreign() -> None:
    assert wrapper._is_allowed_host("https://github.com/a/b.zip")
    assert wrapper._is_allowed_host("https://objects.githubusercontent.com/x/y.zip")
    assert not wrapper._is_allowed_host("https://evil.example.com/payload.zip")


def test_redirect_handler_refuses_foreign_host() -> None:
    handler = wrapper._HostAllowlistRedirectHandler()
    req = urllib.request.Request(wrapper.CNC_DDRAW_URL)
    with pytest.raises(wrapper.WrapperFetchError):
        handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example.com/x.zip")


# --- install_wrapper --------------------------------------------------------


def test_install_writes_dll_and_marker(tmp_path: Path) -> None:
    staging = staged_dir(tmp_path)
    game = tmp_path / "game"
    result = wrapper.install_wrapper(game, staging)
    assert (game / "ddraw.dll").read_bytes() == FAKE_DLL
    marker = json.loads((game / ".disciples-play-wrapper.json").read_text())
    assert marker["ddraw_dll_sha256"] == digest(FAKE_DLL)
    assert marker["cnc_ddraw_tag"] == wrapper.CNC_DDRAW_TAG
    assert result.ini_written is True


def test_install_reinstalls_over_own_dll(tmp_path: Path) -> None:
    staging = staged_dir(tmp_path)
    game = tmp_path / "game"
    wrapper.install_wrapper(game, staging)
    # second install must succeed: the existing dll is ours (marker matches)
    result = wrapper.install_wrapper(game, staging)
    assert (game / "ddraw.dll").read_bytes() == FAKE_DLL
    assert result.ini_written is False  # ini already ours -> no-op


def test_install_refuses_unmanaged_dll(tmp_path: Path) -> None:
    staging = staged_dir(tmp_path)
    game = tmp_path / "game"
    game.mkdir()
    (game / "ddraw.dll").write_bytes(b"SOMEONE-ELSES-DLL")
    with pytest.raises(wrapper.WrapperInstallError):
        wrapper.install_wrapper(game, staging)
    assert (game / "ddraw.dll").read_bytes() == b"SOMEONE-ELSES-DLL"  # untouched


def test_install_refuses_when_marker_disagrees(tmp_path: Path) -> None:
    staging = staged_dir(tmp_path)
    game = tmp_path / "game"
    game.mkdir()
    (game / "ddraw.dll").write_bytes(FAKE_DLL)
    # marker exists but records a *different* digest -> not ours
    (game / ".disciples-play-wrapper.json").write_text(
        json.dumps({"ddraw_dll_sha256": "0" * 64}), encoding="utf-8"
    )
    with pytest.raises(wrapper.WrapperInstallError):
        wrapper.install_wrapper(game, staging)


def test_install_preserves_user_edited_ini(tmp_path: Path) -> None:
    staging = staged_dir(tmp_path)
    game = tmp_path / "game"
    game.mkdir()
    edited = "; my tweaks\nwindowed=0\n"
    (game / "ddraw.ini").write_text(edited)
    result = wrapper.install_wrapper(game, staging)
    assert (game / "ddraw.ini.pre-pack").read_text() == edited
    assert (game / "ddraw.ini").read_text() == wrapper.build_preset()
    assert result.ini_backed_up is True
    assert result.ini_written is True


def test_install_backup_created_once(tmp_path: Path) -> None:
    staging = staged_dir(tmp_path)
    game = tmp_path / "game"
    game.mkdir()
    (game / "ddraw.ini").write_text("; v1\n")
    wrapper.install_wrapper(game, staging)
    # simulate a later user edit, then re-install: pre-pack keeps the first version
    (game / "ddraw.ini").write_text("; v2\n")
    wrapper.install_wrapper(game, staging)
    assert (game / "ddraw.ini.pre-pack").read_text() == "; v1\n"
    assert (game / "ddraw.ini").read_text() == wrapper.build_preset()


def test_install_requires_dll_in_staging(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(wrapper.WrapperInstallError):
        wrapper.install_wrapper(tmp_path / "game", empty)


def test_install_respects_custom_preset(tmp_path: Path) -> None:
    staging = staged_dir(tmp_path)
    game = tmp_path / "game"
    custom = "[ddraw]\nwindowed=1\nrenderer=gdi\n"
    result = wrapper.install_wrapper(game, staging, preset=custom)
    assert (game / "ddraw.ini").read_text() == custom
    assert result.ini_written is True
