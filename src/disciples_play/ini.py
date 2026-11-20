"""Lossless INI reader/writer and the installation-path normaliser.

``EXE\\DISCIPLE.INI`` in Disciples: Sacred Lands Gold stores where the game's
data lives under two sections, ``[Installation]`` (15 keys) and
``[InstallationClient]`` (6 keys). GOG / Steam / Heroic builds hard-code those
values as absolute ``X:\\Games\\...`` paths, so moving the install -- or
changing the Wine drive mapping -- breaks the game.

The maintainer's E1 experiment established that the game resolves those 21
values *relative to its own ``EXE`` directory* when they are written as bare
folder names (``globals=Globals``), and then confirmed that every resource --
music, sound effects, the intro video and the briefing screens -- loads from
those relative names, so no key needs to stay absolute. This module therefore
*normalises* the two sections to relative form: the primary operation rewrites
every absolute path to the canonical on-disk folder name, leaving every other
byte of the file untouched. Absolute Windows-path emission remains available
via ``path_style="wine"`` for installs or keys that need it.

The model is line-oriented and verbatim: the parser records each physical line
*with* its newline terminator, so serialising an untouched document returns the
exact input bytes (CRLF included). Nothing here uses ``configparser``, which
normalises key case and drops comments.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "IniDocument",
    "IniLine",
    "parse",
    "rewrite_installation_paths",
    "to_windows_path",
    "write_ini",
]

logger = logging.getLogger(__name__)

#: Sections whose values are installation data paths.
_INSTALLATION_SECTIONS = ("installation", "installationclient")

#: Accepted values for ``path_style``.
_PATH_STYLES = ("relative", "wine")

#: Accepted values for ``mode`` in :func:`write_ini`.
_WRITE_MODES = ("backup", "inplace", "copy-tree")

#: Canonical on-disk folder name for each INI key, from the maintainer's E1
#: result (2026-11-20). The INI keys are lowercase; the real folders are not a
#: plain capitalisation in every case (``scenarios`` -> ``Scens``,
#: ``imgdata`` -> ``ImgData``), which is why this is a table rather than a
#: ``str.title()`` call. ``[InstallationClient]`` reuses six of these names, so
#: one table serves both sections.
_INSTALLATION_FOLDERS: dict[str, str] = {
    "globals": "Globals",
    "imgs1": "Imgs1",
    "imgs2": "Imgs2",
    "interf": "Interf",
    "scenarios": "Scens",
    "sounds1": "Sounds1",
    "sounds2": "Sounds2",
    "music": "Music",
    "video": "Video",
    "imgdata": "ImgData",
    "campaign": "Campaign",
    "exports": "Exports",
    "savegame": "Savegame",
    "briefing": "Briefing",
    "scendata": "Scendata",
}


@dataclass
class IniLine:
    """One physical line of an INI document, kept verbatim.

    ``raw`` includes the newline terminator (``\\r\\n`` or ``\\n``) when the
    line has one; the final line of a file that does not end with a newline has
    no terminator. Nothing is normalised, so joining every ``raw`` reproduces
    the input exactly.
    """

    raw: str

    @property
    def content(self) -> str:
        """The line without its newline terminator."""
        return self.raw.rstrip("\r\n")

    @property
    def terminator(self) -> str:
        """The ``\\r\\n`` / ``\\n`` suffix, or ``""`` for a newline-less last line."""
        return self.raw[len(self.content) :]


class IniDocument:
    """An INI document as an ordered list of verbatim lines."""

    def __init__(self, lines: list[IniLine]) -> None:
        self.lines = lines

    def to_text(self) -> str:
        """Reassemble the document byte-for-byte."""
        return "".join(line.raw for line in self.lines)


def parse(text: str) -> IniDocument:
    """Parse INI text into an :class:`IniDocument` without losing a byte."""
    return IniDocument([IniLine(part) for part in text.splitlines(keepends=True)])


def _section_name(content: str) -> str | None:
    stripped = content.strip()
    if len(stripped) >= 2 and stripped.startswith("[") and stripped.endswith("]"):
        return stripped[1:-1]
    return None


@dataclass(frozen=True)
class _Assignment:
    """A ``key=value`` line, split so only the value is ever replaced.

    ``prefix`` is the original text up to and including the ``=`` and any
    spaces that follow it (so ``key = value`` stays ``key = `` on rewrite),
    and ``value`` is the left-stripped value.
    """

    key: str
    prefix: str
    value: str


def _split_assignment(content: str) -> _Assignment | None:
    eq = content.find("=")
    if eq < 0:
        return None
    key_text = content[:eq]
    after_eq = content[eq + 1 :]
    leading = after_eq[: len(after_eq) - len(after_eq.lstrip())]
    return _Assignment(
        key=key_text.strip(),
        prefix=key_text + "=" + leading,
        value=after_eq.lstrip(),
    )


def _last_path_component(value: str) -> str:
    """Return the final component of a Windows or POSIX path value."""
    stripped = value.strip().rstrip("/\\")
    if not stripped:
        return ""
    sep = max(stripped.rfind("/"), stripped.rfind("\\"))
    return stripped if sep < 0 else stripped[sep + 1 :]


def to_windows_path(posix_path: str | os.PathLike[str]) -> str:
    """Convert a POSIX path to the Windows form the game expects.

    When a ``winepath`` binary is on ``PATH`` it is used (``winepath -w <dir>``),
    because it also resolves the real drive mapping for a non-default Wine
    prefix. Otherwise the path is mapped onto Wine's default ``Z:`` drive:
    ``/home/u/Game`` becomes ``Z:\\home\\u\\Game``.
    """
    path = os.fspath(posix_path)
    winepath = shutil.which("winepath")
    if winepath is not None:
        converted = _run_winepath(winepath, path)
        if converted:
            return converted
    return _z_drive_fallback(path)


def _run_winepath(winepath: str, posix_path: str) -> str | None:
    try:
        proc = subprocess.run(
            [winepath, "-w", posix_path],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        logger.debug("winepath failed; falling back to the Z: mapping", exc_info=True)
        return None
    if proc.returncode != 0:
        logger.debug("winepath exited %d; falling back to the Z: mapping", proc.returncode)
        return None
    out = proc.stdout.strip()
    return out or None


def _z_drive_fallback(posix_path: str) -> str:
    stripped = posix_path.rstrip("/\\") or "/"
    win = stripped.replace("/", "\\")
    return "Z:" + win if win.startswith("\\") else "Z:\\" + win


def rewrite_installation_paths(
    text: str,
    install_dir: str | os.PathLike[str] | None = None,
    path_style: str = "relative",
) -> str:
    """Normalise the 21 installation paths in ``text``.

    Only assignment lines inside ``[Installation]`` and ``[InstallationClient]``
    are touched; every other line -- other sections, comments, blanks, CRLF -- is
    returned exactly as found.

    ``path_style`` controls how each key's value is written:

    * ``"relative"`` (default): the bare canonical folder name (``Globals``,
      ``Scens``, ``ImgData``, ...). This is the repair form -- the game resolves
      it relative to its own ``EXE`` directory, so the INI survives the install
      moving. ``install_dir`` is ignored.
    * ``"wine"``: an absolute Windows path, ``<install_dir>\\<folder>``, with
      ``install_dir`` converted via :func:`to_windows_path`. Requires
      ``install_dir``.

    A key that is not in the canonical table falls back to the title-cased last
    path component of its old value and logs a warning, so an unexpected key
    never crashes the rewrite.
    """
    if path_style not in _PATH_STYLES:
        raise ValueError(f"unknown path_style {path_style!r}; expected one of {_PATH_STYLES}")

    windows_root: str | None
    if path_style == "wine":
        if install_dir is None:
            raise ValueError("install_dir is required when path_style='wine'")
        windows_root = to_windows_path(install_dir)
    else:
        windows_root = None

    document = parse(text)
    current_section: str | None = None
    seen_sections: set[str] = set()

    for line in document.lines:
        content = line.content
        stripped = content.strip()
        if not stripped or stripped.startswith(";"):
            continue
        section = _section_name(content)
        if section is not None:
            current_section = section
            seen_sections.add(section.lower())
            continue
        if current_section is not None and current_section.lower() in _INSTALLATION_SECTIONS:
            assignment = _split_assignment(content)
            if assignment is not None and assignment.value.strip():
                folder = _folder_for(assignment.key, assignment.value)
                new_value = folder if windows_root is None else windows_root + "\\" + folder
                line.raw = assignment.prefix + new_value + line.terminator

    missing = [s for s in _INSTALLATION_SECTIONS if s not in seen_sections]
    if missing:
        logger.warning(
            "installation-path sections missing from the INI (%s); nothing was rewritten there",
            ", ".join(missing),
        )

    return document.to_text()


def _folder_for(key: str, value: str) -> str:
    """Resolve the canonical folder name for an installation key."""
    folder = _INSTALLATION_FOLDERS.get(key.lower())
    if folder is not None:
        return folder
    guessed = _last_path_component(value).title()
    logger.warning(
        "no canonical folder for key %r; guessed %r from its current value %r",
        key,
        guessed,
        value,
    )
    return guessed


def write_ini(
    path: str | os.PathLike[str],
    text: str,
    mode: str = "backup",
) -> bool:
    """Write ``text`` to ``path`` honouring the backup ``mode``.

    Returns ``True`` when the file was written and ``False`` when it already
    held the exact bytes -- a no-op run never touches the file, so its mtime is
    preserved.

    ``mode``:

    * ``"backup"`` (default): before the first change, save the current bytes to
      ``<path>.orig`` exactly once -- only if that file does not already exist --
      then write in place. Re-runs never overwrite the original.
    * ``"inplace"``: write in place, never back up.
    * ``"copy-tree"``: not implemented here; the launcher (M2) owns it.
    """
    if mode not in _WRITE_MODES:
        raise ValueError(f"unknown ini mode {mode!r}; expected one of {_WRITE_MODES}")
    if mode == "copy-tree":
        raise NotImplementedError(
            "copy-tree mode is implemented by the launcher (M2); use 'backup' or 'inplace'"
        )

    target = Path(path)
    new_bytes = text.encode("utf-8")

    try:
        current = target.read_bytes()
    except FileNotFoundError:
        current = None

    if current == new_bytes:
        return False

    if mode == "backup" and current is not None:
        backup = Path(str(target) + ".orig")
        if not backup.exists():
            backup.write_bytes(current)

    target.write_bytes(new_bytes)
    return True
