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
        # Single iterdir pass filtered on the lower-cased suffix: globbing both
        # "*.DBF" and "*.dbf" would double-count every table on a
        # case-insensitive filesystem (Windows CI), and any non-DBF file is
        # reported per-file by summarize_dbf instead of aborting the run.
        for p in sorted(p for p in sub.iterdir() if p.is_file() and p.suffix.lower() == ".dbf"):
            reports.append(summarize_dbf(p))
    return reports


def _safe(fn, path: Path) -> dict:
    """Call ``fn(path)`` and turn an unreadable file into a per-file error dict.

    ``fn`` is a per-file reader returning a ``dict``.  On ``ValueError`` or
    ``OSError`` (an unreadable file, a truncated buffer, a decode failure) the
    result is ``{"path": <name>, "error": <message>}``, so one bad file in a
    314-file install never takes the whole report down.  This is the same
    contract ``summarize_dbf`` already honours; every other reader is wrapped
    through here so the promise holds for all of them, not just ``.DBF``.
    """

    try:
        return fn(path)
    except (ValueError, OSError) as exc:
        return {"path": Path(path).name, "error": str(exc)}


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
                reports.append(_safe(scan_mqdb, p))
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


def _dbf_column_values(path: Path, column: str, *, skip_deleted: bool = True) -> list[str] | None:
    """Read a named ``.DBF`` column as stripped strings.

    Returns ``None`` when the file cannot be read or the column does not exist,
    so the caller can distinguish "no such field" from "column present but
    empty" instead of silently rendering a missing column as zero references.
    """

    try:
        header, records = read_dbf(path)
    except (ValueError, OSError):
        return None
    if column not in {f.name for f in header.fields}:
        return None
    return column_values(header, records, column, skip_deleted=skip_deleted)


def _cross_reference_report(game_dir: Path) -> dict:
    """Verify the ``ID``-style cross-references that can be proven from the files.

    Reads only the ID columns, never the text body: the report states how many
    ``*_TXT`` references in the named tables resolve to a ``TXT_ID`` in
    ``Tglobal.dbf``, and how many ``RACE_ID`` values resolve to ``GRACE``.
    Resolution counts *live* (non-deleted) rows only; records flagged deleted
    are excluded because their deletion flag marks them as not live data.
    """

    def _resolve(ref: str, keys: set[str]) -> bool:
        return ref.lower() in keys

    tglobal = game_dir / "Globals" / "Tglobal.dbf"
    text_ids: set[str] = set()
    text_id_distinct_all: int | None = None
    if tglobal.is_file():
        live = _dbf_column_values(tglobal, "TXT_ID")
        text_ids = {v.lower() for v in (live or []) if v}
        all_rows = _dbf_column_values(tglobal, "TXT_ID", skip_deleted=False)
        text_id_distinct_all = len({v.lower() for v in (all_rows or []) if v})

    def _text_link(table: str, field: str) -> dict:
        values = _dbf_column_values(game_dir / "Globals" / table, field)
        if values is None:
            return {
                "table": table,
                "field": field,
                "field_missing": True,
                "nonempty": None,
                "resolved": None,
            }
        nonempty = [v for v in values if v]
        resolved = sum(1 for v in nonempty if _resolve(v, text_ids))
        return {
            "table": table,
            "field": field,
            "field_missing": False,
            "nonempty": len(nonempty),
            "resolved": resolved,
        }

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
        race_ids = {v.lower() for v in (_dbf_column_values(grace, "RACE_ID") or []) if v}
        unit_races_values = _dbf_column_values(game_dir / "Globals" / "GUNITS.DBF", "RACE_ID")
        if unit_races_values is None:
            race_link = {
                "table": "GUNITS.DBF",
                "field": "RACE_ID",
                "target": "GRACE.DBF.RACE_ID",
                "field_missing": True,
                "nonempty": None,
                "resolved": None,
            }
        else:
            unit_races = [v.lower() for v in unit_races_values if v]
            resolved = sum(1 for v in unit_races if v in race_ids)
            race_link = {
                "table": "GUNITS.DBF",
                "field": "RACE_ID",
                "target": "GRACE.DBF.RACE_ID",
                "field_missing": False,
                "nonempty": len(unit_races),
                "resolved": resolved,
            }

    return {
        "text_id_table": "Globals/Tglobal.dbf",
        "text_id_count": len(text_ids),
        "text_id_distinct_all": text_id_distinct_all,
        "text_links": links,
        "race_link": race_link,
    }


def _id_type_report(game_dir: Path) -> dict:
    """Histogram of the 2-letter ID type codes across the 10-char ID columns.

    Reads only the identifier strings (the same ``ID``-style columns the
    cross-reference report already reads, no text bodies), lower-cases the
    prefix and the two-letter type code, and counts ``(prefix, type)`` pairs
    over live rows.  The result feeds the ID-type table in
    ``docs/data-layout.md``.
    """

    counts: Counter[tuple[str, str]] = Counter()
    for d in DBF_DIRS:
        sub = game_dir / d
        if not sub.is_dir():
            continue
        for p in sorted(sub.iterdir()):
            if not (p.is_file() and p.suffix.lower() == ".dbf"):
                continue
            try:
                header, records = read_dbf(p)
            except (ValueError, OSError):
                continue
            for f in header.fields:
                if f.type != "C" or f.length != 10:
                    continue
                for value in column_values(header, records, f.name, skip_deleted=True):
                    value = value.strip()
                    if len(value) != 10:
                        continue
                    prefix = value[0].lower()
                    type_code = value[4:6].lower()
                    if prefix in ("g", "x") and value[1:4].isdigit() and type_code.isalpha():
                        counts[(prefix, type_code)] += 1
    return {
        "types": [
            {"prefix": prefix, "type": type_code, "count": n}
            for (prefix, type_code), n in sorted(counts.items(), key=lambda kv: -kv[1])
        ]
    }


def build_report(game_dir: str | os.PathLike[str]) -> dict:
    """Build the full structural report for a game directory.

    Read-only: every file is opened ``rb`` and never written.  The returned
    dict is JSON-serialisable and contains no pixels, no palette entries and no
    hashes.
    """

    root = Path(game_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    if not (root / "Globals").is_dir() and not (root / "Exe").is_dir():
        raise NotADirectoryError(
            f"not a Disciples install: {root} has neither Globals/ nor Exe/; "
            "point --game-dir at the folder that contains them"
        )

    dlg_reports = []
    palanim_reports = []
    mft_reports = []
    smk_reports = []
    wav_reports = []
    capital_reports = []
    for p in _walk_files(root):
        ext = p.suffix.lower()
        if ext == ".dlg":
            dlg_reports.append(_safe(_dlg_report, p))
        elif p.name.upper() == "PALANIM.DAT":
            palanim_reports.append(_safe(_palanim_report, p))
        elif ext in FONT_EXTENSIONS:
            mft_reports.append(_safe(_mft_report, p))
        elif ext in SMK_EXTENSIONS:
            smk_reports.append(_safe(_smk_report, p))
        elif ext in WAV_EXTENSIONS:
            wav_reports.append(_safe(_wav_report, p))
        elif p.name.upper() == "CAPITAL.DAT":
            capital_reports.append(_safe(_capital_report, p))

    return {
        "game_dir": str(root),
        "inventory": inventory(root),
        "dbf": _dbf_reports(root),
        "mqdb": _mqdb_reports(root),
        "cross_references": _cross_reference_report(root),
        "id_types": _id_type_report(root),
        "dlg": dlg_reports,
        "palanim": palanim_reports,
        "capital_dat": capital_reports,
        "mft": mft_reports,
        "smk": smk_reports,
        "wav": wav_reports,
    }


def report_error_count(report: dict) -> int:
    """Count per-file error entries across every section of a report.

    Each per-file reader emits ``{"path": ..., "error": ...}`` on failure; this
    is the single source of truth for whether the ``data`` command should exit
    ``1`` (``EXIT_DATA_INCOMPLETE``), regardless of which reader failed.
    """

    sections = ("dbf", "mqdb", "dlg", "palanim", "capital_dat", "mft", "smk", "wav")
    return sum(
        1
        for section in sections
        for item in report.get(section, [])
        if isinstance(item, dict) and "error" in item
    )


def render_text(report: dict) -> str:
    """Render a :func:`build_report` report as human-readable text."""

    inv = report["inventory"]
    lines: list[str] = []
    lines.append(f"game dir: {report['game_dir']}")
    lines.append(f"files: {inv['total_files']} total")
    lines.append("  by extension: " + ", ".join(f"{k}:{v}" for k, v in inv["by_extension"].items()))
    lines.append("  by directory: " + ", ".join(f"{k}:{v}" for k, v in inv["by_directory"].items()))

    lines.append("")
    parsed = [d for d in report["dbf"] if "error" not in d]
    dbf_errors = [d for d in report["dbf"] if "error" in d]
    lines.append(f"dBase III tables ({len(parsed)}):")
    for d in parsed:
        ok = "OK" if d["arithmetic_ok"] else "MISMATCH"
        lines.append(
            f"  {d['path']}: v{d['version']} {d['records']} rec "
            f"({d['live_records']} live, {d['deleted_records']} deleted), "
            f"hdr={d['header_len']} rec={d['record_len']} {ok} "
            f"[{', '.join(f['name'] for f in d['fields'])}]"
        )
    if dbf_errors:
        lines.append("  unreadable files:")
        for d in dbf_errors:
            lines.append(f"    {d['path']}: {d['error']}")

    lines.append("")
    lines.append(f"MQDB containers ({len(report['mqdb'])}):")
    for m in report["mqdb"]:
        if "error" in m:
            lines.append(f"  {m['path']}: {m['error']}")
            continue
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
        if link["field_missing"]:
            lines.append(f"  {link['table']}.{link['field']}: n/a (field missing)")
        else:
            lines.append(
                f"  {link['table']}.{link['field']}: {link['resolved']}/{link['nonempty']} "
                f"resolve to a TXT_ID"
            )
    if xref["race_link"]:
        r = xref["race_link"]
        if r["field_missing"]:
            lines.append(f"  {r['table']}.{r['field']}: n/a (field missing)")
        else:
            lines.append(
                f"  {r['table']}.{r['field']}: {r['resolved']}/{r['nonempty']} resolve to {r['target']}"
            )

    lines.append("")
    lines.append("ID type codes (prefix/type counts over live rows):")
    for row in report["id_types"]["types"]:
        lines.append(f"  {row['prefix']}/{row['type']}: {row['count']}")

    lines.append("")
    lines.append(f"dialog scripts ({len(report['dlg'])}):")
    for d in report["dlg"]:
        if "error" in d:
            lines.append(f"  {d['path']}: {d['error']}")
            continue
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
