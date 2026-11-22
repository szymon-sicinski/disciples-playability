"""cnc-ddraw preset, pinned fetch and wrapper installation.

Disciples: Sacred Lands Gold does not import DirectDraw itself: it calls
``CoCreateInstance(CLSID_DirectDraw)``, and COM resolves that through the
prefix's ``HKCR\\CLSID\\{D7B70EE0-...}\\InprocServer32`` -- a registry path to
``system32\\ddraw.dll``, **not** the application-directory search. A
``ddraw.dll`` dropped next to ``Disciple.exe`` is therefore not what the renderer
loads, and ``WINEDLLOVERRIDES="ddraw=n,b"`` can only fall back to builtin
(measured; see ``docs/wine-recipe.md``). `cnc-ddraw
<https://github.com/FunkyFr3sh/cnc-ddraw>`_ (MIT) supplies the DLL and the
windowed, upscaled presentation this pack is built to deliver -- the mechanism
below is exercised and tested, but the renderer does not load it until the game's
COM server is redirected, which the pack does not do.

This module turns the hand-unzip-and-configure dance into three reproducible
pieces:

* :func:`build_preset` -- the ``ddraw.ini`` the plan calls "the preset".
* :func:`fetch_wrapper` -- download (or hand in) the pinned release zip, verify
  its SHA-256 *before* touching anything, and extract only the files we ship.
* :func:`install_wrapper` -- copy the DLL and write the preset **next to
  ``Disciple.exe``** (never into the install root), refusing to clobber a DLL we
  did not write and backing up any ``ddraw.ini`` the user edited.

The binary is never vendored in this repository: it is fetched from the pinned
tag and checked against a digest that was measured once and recorded in
``third_party/cnc-ddraw-PROVENANCE.md``. The upstream MIT licence text ships as
``third_party/cnc-ddraw-LICENSE.txt``.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import __version__

__all__ = [
    "ALLOWED_KEYS",
    "CNC_DDRAW_ASSET",
    "CNC_DDRAW_REPO",
    "CNC_DDRAW_SHA256",
    "CNC_DDRAW_TAG",
    "CNC_DDRAW_URL",
    "InstallResult",
    "PRESET_KEYS",
    "WrapperError",
    "WrapperFetchError",
    "WrapperInstallError",
    "build_preset",
    "fetch_wrapper",
    "install_wrapper",
    "resolve_exe_dir",
]

logger = logging.getLogger(__name__)

#: Upstream repository and pinned release. The digest is the SHA-256 of the
#: release asset, measured 2026-11-21 against the real ``v7.1.0.0`` zip (see
#: ``third_party/cnc-ddraw-PROVENANCE.md``). This is a third_party archive
#: digest, not a game hash.
CNC_DDRAW_REPO = "FunkyFr3sh/cnc-ddraw"
CNC_DDRAW_TAG = "v7.1.0.0"
CNC_DDRAW_ASSET = "cnc-ddraw.zip"
#: Byte size of the pinned asset. ``fetch_wrapper`` compares ``len(data)``
#: against this *before* the digest, so a truncated download fails with a clear
#: size error instead of a generic "SHA-256 mismatch".
CNC_DDRAW_SIZE = 2_688_079
CNC_DDRAW_URL = (
    f"https://github.com/{CNC_DDRAW_REPO}/releases/download/{CNC_DDRAW_TAG}/{CNC_DDRAW_ASSET}"
)
CNC_DDRAW_SHA256 = (
    "0b13ab89a64c9918189b1dadd449ef6ed3cb3b7b19cabd96d8adbd95505bb908"  # third_party digest
)

#: Every key this preset is allowed to write. Each name was verified against
#: upstream ``src/config.c`` at tag ``v7.1.0.0`` (``GET_BOOL``/``GET_INT``/
#: ``GET_STRING`` calls); nothing else may appear in the preset.
ALLOWED_KEYS = frozenset(
    {
        "windowed",
        "maintas",
        "boxing",
        "aspect_ratio",
        "maxfps",
        "vsync",
        "adjmouse",
        "renderer",
        "shader",
        "savesettings",
        "singlecpu",
        "noactivateapp",
        "nonexclusive",
        "hook",
        "border",
        "resizable",
        "center_window",
        "inject_resolution",
    }
)

#: The keys the preset actually writes -- the plan's preset, nothing more.
PRESET_KEYS = frozenset(
    {
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
)

#: Values ``renderer`` accepts, exactly upstream ``src/config.c``'s generated
#: ini list: ``auto``, ``opengl``, ``openglcore``, ``gdi``, ``direct3d9``,
#: ``direct3d9on12``. ``auto`` tries direct3d9/opengl and falls back to gdi.
_RENDERERS = frozenset({"auto", "gdi", "opengl", "openglcore", "direct3d9", "direct3d9on12"})

#: The game's fixed internal resolution, used to state the target upscale.
_BASE_WIDTH = 640
_BASE_HEIGHT = 480

#: Marker file recording the digest of the ``ddraw.dll`` this pack installed.
_MARKER_FILENAME = ".disciples-play-wrapper.json"

#: The executable whose *directory* is where a wrapper would be loaded from, for
#: titles that resolve ``ddraw.dll`` by name against the running executable's
#: directory. Disciples does not: it asks COM for ``CLSID_DirectDraw``, which
#: resolves through the registry to ``system32``. Spelled and matched as
#: :func:`disciples_play.launch.resolve_install` finds it, so the names match.
#: The two differ by design on an ambiguous tree: ``launch`` picks ``Exe/`` silently,
#: :func:`resolve_exe_dir` refuses it rather than installing in either place.
_EXE_NAME = "Disciple.exe"

#: The GOG layout's subdirectory holding the executable, under the install root
#: that holds ``Globals/``, ``Imgs1/``, ... (same name ``launch`` resolves).
_EXE_SUBDIR = "Exe"

#: Zip entries we copy out of the release archive. Everything else (the config
#: GUI, the shader packs) is deliberately skipped.
_WANTED_FILES = frozenset({"ddraw.dll", "ddraw.ini"})

#: Filename prefixes treated as "LICENSE-ish" (case-insensitive), so the
#: licence/notice travels with the wrapper when upstream ships one in the zip.
_LEGAL_PREFIXES = ("license", "copying", "notice")

#: Hosts a release-asset download may resolve to. GitHub redirects the release
#: URL to its asset CDN; anything outside this set is refused.
_ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
        "codeload.github.com",
        "raw.githubusercontent.com",
    }
)

_USER_AGENT = f"disciples-play/{__version__}"
_DOWNLOAD_TIMEOUT = 60.0


class WrapperError(Exception):
    """Base error for the cnc-ddraw wrapper."""


class WrapperFetchError(WrapperError):
    """Download, digest or extraction of the release archive failed."""


class WrapperInstallError(WrapperError):
    """The wrapper refused to write into the game directory."""


@dataclass(frozen=True)
class InstallResult:
    """What :func:`install_wrapper` wrote, and what it had to protect first."""

    ddraw_dll: Path
    ddraw_ini: Path
    marker: Path
    ini_backed_up: bool
    ini_written: bool


def build_preset(
    scale: int = 3,
    maxfps: int = 60,
    vsync: bool = True,
    adjmouse: bool = True,
    renderer: str = "auto",
) -> str:
    """Return the ``ddraw.ini`` preset for Disciples: Sacred Lands Gold.

    The preset pins the plan's nine keys and nothing else: ``windowed=1``,
    ``maintas=1``, ``maxfps``, ``vsync``, ``adjmouse``, ``savesettings=1``,
    ``nonexclusive=1``, ``hook=4`` and ``renderer``. A leading comment block
    names the pack version, the cnc-ddraw tag and the two hotkeys a user needs
    (Alt+Enter toggles, Ctrl+Tab releases the cursor).

    ``hook=4`` (upstream's own default) is deliberate for this game:
    ``Disciple.exe`` does not import ``ddraw`` -- it asks COM for
    ``CLSID_DirectDraw`` -- so the narrow ``hook=1`` (patch only the main
    executable's import table) would patch nothing that draws, and for this
    title no hook mode applies at all: the renderer never loads the DLL. Mode 4 enumerates the
    loaded modules
    and patches every *local* one, which is what carries ``adjmouse``, cursor
    clipping and the ``PeekMessage`` filter to the DLL that owns the window.

    ``scale`` is the plan's target integer upscale (3 -> 1920x1440). Upstream
    has no ``scale=`` key: the scaling itself comes from ``windowed=1`` plus
    ``maintas=1`` (aspect-preserving) as the user resizes the window, so
    ``scale`` is recorded in the comment header as the documented target and
    used only for that. ``boxing=true`` (integer scaling) or
    ``shader=Nearest neighbor`` are the crisp-pixel knobs; see
    ``docs/wrapper.md``.

    Every key written is one upstream actually reads (``src/config.c``); booleans
    are emitted as ``1``/``0``, which upstream's ``cfg_get_bool`` accepts.
    """
    _check_scale(scale)
    if isinstance(maxfps, bool) or not isinstance(maxfps, int) or maxfps < -1:
        raise ValueError(f"maxfps must be an int >= -1, got {maxfps!r}")
    if renderer not in _RENDERERS:
        raise ValueError(f"unknown renderer {renderer!r}; expected one of {sorted(_RENDERERS)}")

    width, height = _BASE_WIDTH * scale, _BASE_HEIGHT * scale
    header = (
        "; cnc-ddraw preset for Disciples: Sacred Lands Gold\n"
        f"; generated by disciples-play {__version__}\n"
        f"; cnc-ddraw {CNC_DDRAW_TAG} (MIT) - https://github.com/{CNC_DDRAW_REPO}\n"
        ";\n"
        "; Written for titles that load ddraw.dll by name: there the preset owns\n"
        "; the window and the game stays fullscreen (InWindow=0). Disciples\n"
        "; acquires DirectDraw through COM (system32\\ddraw.dll), so this file is\n"
        "; not loaded by it - see docs/wine-recipe.md.\n"
        f"; Target upscale: {scale}x ({width}x{height}). Resize the window to taste.\n"
        "; Hotkeys: Alt+Enter toggles windowed/fullscreen, Ctrl+Tab releases the cursor.\n"
        "\n"
        "[ddraw]\n"
    )
    body = "".join(
        [
            "windowed=1\n",
            "maintas=1\n",
            f"maxfps={maxfps}\n",
            f"vsync={_bool(vsync)}\n",
            f"adjmouse={_bool(adjmouse)}\n",
            "savesettings=1\n",
            "nonexclusive=1\n",
            "hook=4\n",
            f"renderer={renderer}\n",
        ]
    )
    return header + body


def fetch_wrapper(
    dest: str | os.PathLike[str],
    tag: str = CNC_DDRAW_TAG,
    expected_sha256: str = CNC_DDRAW_SHA256,
    expected_size: int | None = CNC_DDRAW_SIZE,
    offline_zip: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Fetch the pinned cnc-ddraw release and stage the files we ship.

    The release asset is downloaded with :mod:`urllib` (or read from
    ``offline_zip`` for air-gapped machines) and verified *before* anything is
    extracted: its byte size is compared against ``expected_size``, then its
    SHA-256 against ``expected_sha256``. A size or digest mismatch, a failed
    download or a redirect to a non-GitHub host raises :class:`WrapperFetchError`.
    Only ``ddraw.dll``, ``ddraw.ini`` and LICENSE-ish files are extracted into
    ``dest`` (created only after verification), with path-traversal entries
    (``..``, absolute) and symlink entries rejected.

    Returns the list of entry names written, relative to the archive.
    """
    if not isinstance(expected_sha256, str) or not expected_sha256:
        raise ValueError("expected_sha256 is required (64-hex SHA-256 of the release zip)")

    if offline_zip is not None:
        try:
            data = Path(offline_zip).read_bytes()
        except OSError as exc:
            raise WrapperFetchError(f"cannot read offline zip {offline_zip!r}: {exc}") from exc
    else:
        data, _ = _download(_release_url(tag))

    if expected_size is not None and len(data) != expected_size:
        raise WrapperFetchError(
            f"unexpected size for cnc-ddraw {tag}: expected {expected_size} bytes, "
            f"got {len(data)} (download refused, nothing extracted)"
        )

    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise WrapperFetchError(
            f"SHA-256 mismatch for cnc-ddraw {tag}: "
            f"expected {expected_sha256.lower()}, got {digest} (download refused, nothing extracted)"
        )

    return _extract(data, Path(dest))


def resolve_exe_dir(target: str | os.PathLike[str]) -> Path:
    """Return the directory holding ``Disciple.exe`` -- where the wrapper goes.

    For a title that loads ``ddraw.dll`` by name, it resolves against the
    *running executable's directory*: ``Exe/``
    on the GOG layout, not the install root that holds ``Globals/`` and
    ``Imgs1/``. A wrapper written anywhere else is inert, so this never invents
    a directory -- it resolves one of two shapes and refuses everything else:

    * ``target`` itself holds ``Disciple.exe`` -> ``target``;
    * ``target/Exe/Disciple.exe`` exists -> ``target/Exe``, i.e. the install
      root that :func:`disciples_play.launch.resolve_install` hands out.

    An *ambiguous* tree -- ``target`` holds ``Disciple.exe`` **and**
    ``target/Exe/Disciple.exe`` -- raises
    :class:`WrapperInstallError` naming both paths. Preferring ``target`` would
    install the wrapper in the root while ``launch`` uses ``<root>/Exe`` as the
    exe directory and looks for ``ddraw.dll`` there, leaving it inert; guessing
    is worse than asking, so the caller passes the intended directory's exact
    path: ``target/Exe`` works with the stray still in the root; if the stray
    copy is the wrong one, remove it and re-run with the root.

    Anything else raises :class:`WrapperInstallError` naming both paths that
    were tried.
    """
    path = Path(target)
    nested = path / _EXE_SUBDIR
    here = path.is_dir() and (path / _EXE_NAME).is_file()
    there = nested.is_dir() and (nested / _EXE_NAME).is_file()
    if here and there:
        raise WrapperInstallError(
            f"ambiguous: both {path / _EXE_NAME} and {nested / _EXE_NAME} exist; "
            f"the launcher uses {nested}, so pass that directory explicitly (or "
            f"remove the stray {_EXE_NAME}) -- refusing to guess where the wrapper goes"
        )
    if here:
        return path
    if there:
        return nested
    raise WrapperInstallError(
        f"no {_EXE_NAME} in {path} (looked for {path / _EXE_NAME} and "
        f"{nested / _EXE_NAME}); pass the install root or the directory that holds "
        f"{_EXE_NAME} -- the wrapper only loads from next to the executable"
    )


def install_wrapper(
    game_dir: str | os.PathLike[str],
    staging: str | os.PathLike[str],
    preset: str | None = None,
) -> InstallResult:
    """Install the staged wrapper next to ``Disciple.exe``, on an explicit call.

    ``game_dir`` is the game directory you have at hand, in either of the two
    shapes :func:`resolve_exe_dir` accepts -- the install root, or the directory
    that holds ``Disciple.exe`` itself. It is *not* "whatever path you pass":
    the destination is always resolved to the executable's directory first, so
    the install root cannot become a home for a DLL the launcher will never
    load. A directory that holds ``Disciple.exe`` in neither shape raises
    :class:`WrapperInstallError` and nothing is written, and so does an
    *ambiguous* tree -- the executable in both the root and ``Exe/`` -- because
    :func:`resolve_exe_dir` refuses the ambiguity rather than guessing.

    * ``ddraw.dll`` is copied from ``staging``. An existing ``ddraw.dll`` that
      was not written by this pack -- judged by comparing its SHA-256 against
      the marker file ``.disciples-play-wrapper.json`` -- is refused with
      :class:`WrapperInstallError`; our own file is overwritten freely.
    * ``ddraw.ini`` is written from ``preset``, or :func:`build_preset` when
      ``preset`` is ``None``. A file that differs from the text being written
      is backed up to ``ddraw.ini.pre-pack`` (created once, never overwritten)
      before ours is written; a byte-identical file is left untouched.

    All three files -- the DLL, the preset and the marker -- land in that one
    directory, which is exactly where ``doctor`` and
    :func:`disciples_play.launch.wrapper_staged` look.

    The ``ddraw.ini`` staged by :func:`fetch_wrapper` is upstream's reference
    template and is *not* installed: the game's ``ddraw.ini`` is always our
    preset (or the caller's ``preset=``).

    One wrinkle worth naming: because the preset sets ``savesettings=1``,
    cnc-ddraw writes its own geometry back into ``[ddraw]`` on exit, so a file
    that "differs from the preset" on a later install is usually cnc-ddraw's
    saved state rather than a human edit -- the backup preserves it either way.
    """
    staging = Path(staging)

    dll_src = staging / "ddraw.dll"
    if not dll_src.is_file():
        raise WrapperInstallError(f"staging directory has no ddraw.dll: {staging}")

    exe_dir = resolve_exe_dir(game_dir)

    new_digest = _sha256_file(dll_src)
    target_dll = exe_dir / "ddraw.dll"
    marker = exe_dir / _MARKER_FILENAME

    if target_dll.exists():
        current_digest = _sha256_file(target_dll)
        recorded = _read_marker(marker)
        if recorded is None or recorded.get("ddraw_dll_sha256") != current_digest:
            raise WrapperInstallError(
                f"refusing to overwrite {target_dll}: it was not written by this pack. "
                "Move it away (or delete it) and re-run."
            )

    shutil.copyfile(dll_src, target_dll)
    _write_marker(marker, new_digest)
    logger.info("installed ddraw.dll into %s", exe_dir)

    ini_text = preset if preset is not None else build_preset()
    ini_backed_up, ini_written = _install_ini(exe_dir / "ddraw.ini", ini_text)
    return InstallResult(
        ddraw_dll=target_dll,
        ddraw_ini=exe_dir / "ddraw.ini",
        marker=marker,
        ini_backed_up=ini_backed_up,
        ini_written=ini_written,
    )


# --- helpers ---------------------------------------------------------------


def _check_scale(scale: int) -> None:
    if isinstance(scale, bool) or not isinstance(scale, int) or scale < 1:
        raise ValueError(f"scale must be a positive int, got {scale!r}")


def _bool(value: bool) -> str:
    return "1" if value else "0"


def _release_url(tag: str) -> str:
    return f"https://github.com/{CNC_DDRAW_REPO}/releases/download/{tag}/{CNC_DDRAW_ASSET}"


def _download(url: str) -> tuple[bytes, str]:
    """Download ``url`` following only GitHub hosts; return ``(bytes, final_url)``."""
    opener = urllib.request.build_opener(_HostAllowlistRedirectHandler())
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with opener.open(request, timeout=_DOWNLOAD_TIMEOUT) as response:
            return response.read(), response.geturl()
    except (urllib.error.URLError, OSError) as exc:
        raise WrapperFetchError(f"failed to download {url}: {exc}") from exc


def _is_allowed_host(url: str) -> bool:
    """True when ``url``'s host is one of GitHub's download hosts."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host in _ALLOWED_DOWNLOAD_HOSTS


class _HostAllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects only within GitHub's download hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_allowed_host(newurl):
            host = urllib.parse.urlsplit(newurl).hostname or "(none)"
            raise WrapperFetchError(f"refusing to follow redirect to non-GitHub host {host!r}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _extract(data: bytes, dest: Path) -> list[str]:
    """Extract the wanted entries from ``data`` into ``dest``, safely.

    Every entry name is validated (and symlink entries refused) and every
    wanted member is read fully into memory -- which validates its CRC-32 --
    *before* any byte is written, so a hostile entry, a symlink or a corrupt
    member (bad CRC with an intact central directory) can neither escape
    ``dest`` nor leave a half-written file behind. ``BadZipFile`` and
    ``OSError`` anywhere on that path are mapped to :class:`WrapperFetchError`.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise WrapperFetchError(f"release asset is not a valid zip: {exc}") from exc

    with archive:
        # Pass 1: validate every entry name and read the wanted members fully
        # into memory (reading validates each member's CRC-32), writing nothing.
        # A zip-slip/absolute entry, a symlink, or a corrupt member is rejected
        # before any byte reaches disk, so a bad archive cannot leave a partial
        # file behind.
        wanted: list[tuple[Path, str, bytes]] = []
        for member in archive.infolist():
            name = member.filename
            if name.endswith(("/", "\\")):
                continue  # directory entry
            target = _safe_target(dest, name)  # raises on traversal/absolute
            if _is_symlink(member):
                raise WrapperFetchError(f"refusing symlink zip entry {name!r}")
            base = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
            if base not in _WANTED_FILES and not base.startswith(_LEGAL_PREFIXES):
                continue
            try:
                with archive.open(member) as src:
                    content = src.read()
            except (zipfile.BadZipFile, OSError) as exc:
                raise WrapperFetchError(
                    f"failed to read {name!r} from the release archive: {exc}"
                ) from exc
            wanted.append((target, name, content))

        if not wanted:
            return []

        # Pass 2: write. The destination is only created once every wanted
        # entry has been validated and read successfully.
        dest.mkdir(parents=True, exist_ok=True)
        extracted: list[str] = []
        for target, name, content in wanted:
            try:
                target.write_bytes(content)
            except OSError as exc:
                raise WrapperFetchError(f"failed to write {name!r} into {dest}: {exc}") from exc
            extracted.append(name)
    return extracted


def _is_symlink(member: zipfile.ZipInfo) -> bool:
    """True when the zip entry is a symlink (Unix ``S_IFLNK`` file type)."""
    mode = (member.external_attr >> 16) & 0o170000
    return mode == 0o120000


def _safe_target(dest: Path, name: str) -> Path:
    """Map a zip entry name to a path inside ``dest``, rejecting traversal."""
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise WrapperFetchError(f"refusing absolute zip entry {name!r}")
    parts = normalized.split("/")
    if ".." in parts:
        raise WrapperFetchError(f"refusing path-traversal zip entry {name!r}")
    clean = [part for part in parts if part not in ("", ".")]
    if not clean:
        raise WrapperFetchError(f"refusing empty zip entry {name!r}")
    target = dest.joinpath(*clean).resolve()
    if target != dest.resolve() and dest.resolve() not in target.parents:
        raise WrapperFetchError(f"refusing zip entry escaping destination: {name!r}")
    return target


def _install_ini(target: Path, text: str) -> tuple[bool, bool]:
    """Write ``text`` to ``target``, backing up a differing file once.

    Returns ``(ini_backed_up, ini_written)``. A byte-identical file is left
    untouched; a differing one is copied to ``<target>.pre-pack`` first (only
    if that backup does not already exist, matching the INI model's ``.orig``
    convention).
    """
    new_bytes = text.encode("utf-8")
    if target.exists():
        if target.read_bytes() == new_bytes:
            return False, False
        backup = Path(str(target) + ".pre-pack")
        backed_up = False
        if not backup.exists():
            shutil.copyfile(target, backup)
            backed_up = True
        target.write_bytes(new_bytes)
        return backed_up, True
    target.write_bytes(new_bytes)
    return False, True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_marker(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_marker(path: Path, digest: str) -> None:
    payload = {
        "ddraw_dll_sha256": digest,
        "cnc_ddraw_tag": CNC_DDRAW_TAG,
        "pack_version": __version__,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
