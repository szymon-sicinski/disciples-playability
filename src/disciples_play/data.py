"""Read-only ``data`` report for *Disciples: Sacred Lands Gold*.

This module walks a game install and emits a *structural* report: a directory
inventory, per-table dBase III geometry, per-container ``MQDB`` hypothesis
votes, and digests of the plain-text formats.  It deliberately stops short of
decoding any content -- no pixels, no palette entries, no audio samples, and no
file hashes -- so the whole report is safe to publish.

The report is a plain dict so it renders identically as human text or JSON.
"""

from __future__ import annotations

import os
import struct
from collections import Counter
from pathlib import Path

from .dbf import column_values, read_dbf, summarize_dbf
from .mqdb import scan_mqdb

#: Directories that hold dBase III tables.
DBF_DIRS = ("Globals", "Scens", "Scendata", "ImgData", "Campaign", "Interf")
#: Directories that hold ``MQDB`` containers (all three extensions share it).
MQDB_DIRS = ("Interf", "Imgs1", "Imgs2", "Sounds1", "Sounds2")
#: Extensions treated as ``MQDB`` containers.
MQDB_EXTENSIONS = (".dbi", ".ff", ".wdb")
#: Text formats with a known grammar, digested structurally.
TEXT_FORMATS = (".dlg",)
#: Font containers.
FONT_EXTENSIONS = (".mft",)
#: Smacker video.
SMK_EXTENSIONS = (".smk",)
#: RIFF/WAVE audio.
WAV_EXTENSIONS = (".wav",)


def _walk_files(game_dir: Path) -> list[Path]:
    """Return every regular file under ``game_dir``, recursively, sorted."""

    return sorted(p for p in game_dir.rglob("*") if p.is_file())


def inventory(game_dir: str | os.PathLike[str]) -> dict:
    """Count files by extension and by top-level directory."""

    root = Path(game_dir)
    files = _walk_files(root)
    by_ext: Counter[str] = Counter()
    by_dir: Counter[str] = Counter()
    for p in files:
        by_ext[p.suffix.lower()] += 1
        rel = p.relative_to(root)
        by_dir[rel.parts[0] if len(rel.parts) > 1 else "(root)"] += 1
    return {
        "total_files": len(files),
        "by_extension": dict(sorted(by_ext.items())),
        "by_directory": dict(sorted(by_dir.items())),
    }


def _dbf_reports(game_dir: Path) -> list[dict]:
    reports: list[dict] = []
    for d in DBF_DIRS:
        sub = game_dir / d
        if not sub.is_dir():
            continue
        for p in sorted(sub.glob("*.DBF")) + sorted(sub.glob("*.dbf")):
            if p.is_file():
                reports.append(summarize_dbf(p))
    return reports


def _mqdb_reports(game_dir: Path) -> list[dict]:
    reports: list[dict] = []
    seen: set[Path] = set()
    for d in MQDB_DIRS:
        sub = game_dir / d
        if not sub.is_dir():
            continue
        for p in sorted(sub.iterdir()):
            if p.suffix.lower() in MQDB_EXTENSIONS and p.is_file() and p not in seen:
                seen.add(p)
                reports.append(scan_mqdb(p))
    return reports


def _dlg_report(path: Path) -> dict:
    """Digest a ``.dlg`` dialog script without interpreting the grammar fully."""

    raw = path.read_bytes()
    text = raw.decode("latin-1")
    lines = text.splitlines()
    dialogs = 0
    tags: Counter[str] = Counter()
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("DIALOG"):
            dialogs += 1
        elif stripped and not stripped.startswith("BEGIN") and not stripped.startswith("END"):
            first = stripped.split(None, 1)[0].rstrip(",")
            if first:
                tags[first] += 1
    return {
        "path": path.name,
        "size": len(raw),
        "lines": len(lines),
        "dialog_blocks": dialogs,
        "element_types": dict(sorted(tags.items())),
    }


def _palanim_report(path: Path) -> dict:
    """Digest ``PALANIM.DAT`` (palette-animation script) structurally.

    The file is plain text; its body rows are palette indices and RGB triples,
    which are *not* dumped -- only the counts and block grammar are reported.
    """

    raw = path.read_bytes()
    text = raw.decode("latin-1")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Blocks are introduced by a "N -1 M" header line; body rows are "i R G B".
    block_headers = [ln for ln in lines if len(ln.split()) >= 3 and ln.split()[1] == "-1"]
    return {
        "path": path.name,
        "size": len(raw),
        "lines": len(lines),
        "first_line": lines[0] if lines else "",
        "animation_blocks": len(block_headers),
        "note": "body rows are palette index + RGB triple; values not dumped",
    }


def _capital_report(path: Path) -> dict:
    """Digest ``CAPITAL.DAT`` (INI-like text) structurally, no values."""

    raw = path.read_bytes()
    text = raw.decode("latin-1")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    sections = [ln for ln in lines if ln.startswith("[") and ln.endswith("]")]
    keys = [ln for ln in lines if "=" in ln]
    return {
        "path": path.name,
        "size": len(raw),
        "lines": len(lines),
        "sections": sections,
        "key_value_lines": len(keys),
    }


def _mft_report(path: Path) -> dict:
    """Report the ``MFT`` font header: magic, version and size only."""

    raw = path.read_bytes()
    magic = raw[:4]
    version = struct.unpack_from("<I", raw, 4)[0] if len(raw) >= 8 else None
    return {
        "path": path.name,
        "size": len(raw),
        "magic": magic.decode("latin-1"),
        "version": version,
    }


def _smk_report(path: Path) -> dict:
    """Report a Smacker header: magic and the first three geometry u32s."""

    with open(path, "rb") as fh:
        raw = fh.read(16)
    magic = raw[:4]
    if len(raw) >= 16 and magic[:3] == b"SMK":
        width, height, frames = struct.unpack_from("<III", raw, 4)
    else:
        width = height = frames = None
    return {
        "path": path.name,
        "size": os.path.getsize(path),
        "magic": magic.decode("latin-1"),
        "width": width,
        "height": height,
        "frames": frames,
    }


def _wav_report(path: Path) -> dict:
    """Report a RIFF/WAVE header: format tag, channels and sample rate."""

    with open(path, "rb") as fh:
        raw = fh.read(40)
    riff = raw[:4]
    wave = raw[8:12] if len(raw) >= 12 else b""
    fmt = None
    channels = None
    rate = None
    if riff == b"RIFF" and wave == b"WAVE" and len(raw) >= 40:
        fmt, channels, rate = struct.unpack_from("<HHI", raw, 20)
    return {
        "path": path.name,
        "size": os.path.getsize(path),
        "magic": riff.decode("latin-1"),
        "format_tag": fmt,
        "channels": channels,
        "sample_rate": rate,
    }


def _dbf_column_values(path: Path, column: str) -> list[str]:
    """Read a named ``.DBF`` column as stripped strings (empty list if absent)."""

    try:
        header, records = read_dbf(path)
    except (ValueError, OSError):
        return []
    return column_values(header, records, column)


def _cross_reference_report(game_dir: Path) -> dict:
    """Verify the ``ID``-style cross-references that can be proven from the files.

    Reads only the ID columns, never the text body: the report states how many
    ``*_TXT`` references in the named tables resolve to a ``TXT_ID`` in
    ``Tglobal.dbf``, and how many ``RACE_ID`` values resolve to ``GRACE``.
    """

    def _resolve(ref: str, keys: set[str]) -> bool:
        return ref.lower() in keys

    tglobal = game_dir / "Globals" / "Tglobal.dbf"
    text_ids: set[str] = set()
    if tglobal.is_file():
        text_ids = {v.lower() for v in _dbf_column_values(tglobal, "TXT_ID") if v}

    def _text_link(table: str, field: str) -> dict:
        values = _dbf_column_values(game_dir / "Globals" / table, field)
        nonempty = [v for v in values if v]
        resolved = sum(1 for v in nonempty if _resolve(_strip_count_prefix(v), text_ids))
        return {"table": table, "field": field, "nonempty": len(nonempty), "resolved": resolved}

    links = []
    for table, field in (
        ("GACTION.DBF", "NAME_TXT"),
        ("GUNITS.DBF", "NAME_TXT"),
        ("GUNITS.DBF", "DESC_TXT"),
        ("GBUILD.DBF", "NAME_TXT"),
        ("GSPELLS.DBF", "NAME_TXT"),
    ):
        path = game_dir / "Globals" / table
        if path.is_file():
            links.append(_text_link(table, field))

    grace = game_dir / "Globals" / "GRACE.DBF"
    race_link = None
    if grace.is_file():
        race_ids = {v.lower() for v in _dbf_column_values(grace, "RACE_ID") if v}
        unit_races = [
            _strip_count_prefix(v).lower()
            for v in _dbf_column_values(game_dir / "Globals" / "GUNITS.DBF", "RACE_ID")
            if v
        ]
        resolved = sum(1 for v in unit_races if v in race_ids)
        race_link = {
            "table": "GUNITS.DBF",
            "field": "RACE_ID",
            "target": "GRACE.DBF.RACE_ID",
            "nonempty": len(unit_races),
            "resolved": resolved,
        }

    return {
        "text_id_table": "Globals/Tglobal.dbf",
        "text_id_count": len(text_ids),
        "text_links": links,
        "race_link": race_link,
    }


def _strip_count_prefix(value: str) -> str:
    """Strip a leading count digit / marker from an ID reference.

    ``1g000rr000`` and ``g000rr000`` both refer to race ``g000rr000``; a
    leading ``0``-``9`` or ``*`` is an occurrence count or marker, not part of
    the ID.  See ``docs/data-layout.md``.
    """

    return value.lstrip("0123456789*")


def build_report(game_dir: str | os.PathLike[str]) -> dict:
    """Build the full structural report for a game directory.

    Read-only: every file is opened ``rb`` and never written.  The returned
    dict is JSON-serialisable and contains no pixels, no palette entries and no
    hashes.
    """

    root = Path(game_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    dlg_reports = []
    palanim_reports = []
    mft_reports = []
    smk_reports = []
    wav_reports = []
    capital_reports = []
    for p in _walk_files(root):
        ext = p.suffix.lower()
        if ext == ".dlg":
            dlg_reports.append(_dlg_report(p))
        elif p.name.upper() == "PALANIM.DAT":
            palanim_reports.append(_palanim_report(p))
        elif ext in FONT_EXTENSIONS:
            mft_reports.append(_mft_report(p))
        elif ext in SMK_EXTENSIONS:
            smk_reports.append(_smk_report(p))
        elif ext in WAV_EXTENSIONS:
            wav_reports.append(_wav_report(p))
        elif p.name.upper() == "CAPITAL.DAT":
            capital_reports.append(_capital_report(p))

    return {
        "game_dir": str(root),
        "inventory": inventory(root),
        "dbf": _dbf_reports(root),
        "mqdb": _mqdb_reports(root),
        "cross_references": _cross_reference_report(root),
        "dlg": dlg_reports,
        "palanim": palanim_reports,
        "capital_dat": capital_reports,
        "mft": mft_reports,
        "smk": smk_reports,
        "wav": wav_reports,
    }


def render_text(report: dict) -> str:
    """Render a :func:`build_report` report as human-readable text."""

    inv = report["inventory"]
    lines: list[str] = []
    lines.append(f"game dir: {report['game_dir']}")
    lines.append(f"files: {inv['total_files']} total")
    lines.append("  by extension: " + ", ".join(f"{k}:{v}" for k, v in inv["by_extension"].items()))
    lines.append("  by directory: " + ", ".join(f"{k}:{v}" for k, v in inv["by_directory"].items()))

    lines.append("")
    lines.append(f"dBase III tables ({len(report['dbf'])}):")
    for d in report["dbf"]:
        ok = "OK" if d["arithmetic_ok"] else "MISMATCH"
        lines.append(
            f"  {d['path']}: v{d['version']} {d['records']} rec, "
            f"hdr={d['header_len']} rec={d['record_len']} {ok} "
            f"[{', '.join(f['name'] for f in d['fields'])}]"
        )

    lines.append("")
    lines.append(f"MQDB containers ({len(report['mqdb'])}):")
    for m in report["mqdb"]:
        w = m["winner"]
        lines.append(
            f"  {m['path']}: {m['size']} B, magic={m['magic']!r}, "
            f"version_le={m['version_le']}, {w['chunks']} chunks "
            f"(winner start={w['start_offset']} {w['endian']}, tiles={w['tiles_exactly']})"
        )

    lines.append("")
    lines.append("cross-references (ID columns only, no text bodies):")
    xref = report["cross_references"]
    lines.append(f"  text IDs: {xref['text_id_table']} -> {xref['text_id_count']} distinct TXT_IDs")
    for link in xref["text_links"]:
        lines.append(
            f"  {link['table']}.{link['field']}: {link['resolved']}/{link['nonempty']} "
            f"resolve to a TXT_ID"
        )
    if xref["race_link"]:
        r = xref["race_link"]
        lines.append(
            f"  {r['table']}.{r['field']}: {r['resolved']}/{r['nonempty']} resolve to {r['target']}"
        )

    lines.append("")
    lines.append(f"dialog scripts ({len(report['dlg'])}):")
    for d in report["dlg"]:
        lines.append(
            f"  {d['path']}: {d['dialog_blocks']} DIALOG blocks, "
            f"{d['lines']} lines, elements={d['element_types']}"
        )

    for section, label in (
        ("palanim", "palette-animation scripts"),
        ("capital_dat", "CAPITAL.DAT text configs"),
        ("mft", "font files"),
        ("smk", "Smacker videos"),
        ("wav", "wave audio"),
    ):
        if report[section]:
            lines.append("")
            lines.append(f"{label} ({len(report[section])}):")
            for r in report[section]:
                lines.append(f"  {r}")
    return "\n".join(lines)
